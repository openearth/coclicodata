# %%
# ## Load software
import sys

branch = "dev"
sys.path.insert(0, "../src")

from coastmonitor.io.drive_config import configure_instance

is_local_instance = configure_instance(branch=branch)

import dataclasses
import datetime
import logging
import os
import cv2
import pathlib
import re
import json
import pyarrow
import gcsfs
import geopandas as gpd
import pandas as pd
import numpy as np
from typing import Any

import fsspec
import pystac
import stac_geoparquet
from typing import List
from posixpath import join as urljoin
from dotenv import load_dotenv
from pystac.stac_io import DefaultStacIO

from coclicodata.etl.cloud_utils import (
    load_google_credentials,
    dir_to_google_cloud,
    file_to_google_cloud,
)
from coclicodata.drive_config import p_drive
from coclicodata.coclico_stac.reshape_im import reshape_aspectratio_image

from coastmonitor import stac_table
from coastmonitor.stac.layouts import ParquetLayout

# %%
# ## Define variablestemplate
# hard-coded input params at project level
GCS_PROTOCOL = "https://storage.googleapis.com"
GCS_PROJECT = "coclico-11207608-002"
BUCKET_NAME = "coclico-data-public"
BUCKET_PROJ = "coclico"
PROJ_NAME = "cfhp_all_stats"

# hard-coded STAC templates
STAC_DIR = pathlib.Path.cwd().parent.parent / "current"  # .parent.parent

# hard-coded input params which differ per dataset
DATASET_DIR = "cfhp_all_stats"
# CF_FILE = "Global_merit_coastal_mask_landwards.tif"
COLLECTION_ID = "cfhp_all_stats"  # name of stac collection
MAX_FILE_SIZE = 500  # max file size in MB

# define local directories
home = pathlib.Path().home()
tmp_dir = home.joinpath("data", "tmp")
coclico_data_dir = p_drive.joinpath(
    "11207608-coclico", "FULLTRACK_DATA"
)  # remote p drive
cred_data_dir = p_drive.joinpath("11207608-coclico", "FASTTRACK_DATA")

# use local or remote data dir
use_local_data = False

if use_local_data:
    ds_dir = tmp_dir
else:
    ds_dir = coclico_data_dir

if not ds_dir.exists():
    raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

# # directory to export result
# cog_dirs = ds_dir.joinpath("cogs")
ds_path = ds_dir.joinpath("WP4", "front_end_data")  # path to directory with data
ds_fp = ds_path.joinpath("cfhp_all_stats.parquet")  # path to dataset

# # load metadata template
metadata_fp = ds_fp.with_suffix(".json")
with open(metadata_fp, "r") as f:
    metadata = json.load(f)
metadata["TITLE"] = "Flood perspectives - statistics"

# # extend keywords
metadata["KEYWORDS"].extend(["Full-Track"])

# # data output configurations
HREF_PREFIX = urljoin(
    GCS_PROTOCOL, BUCKET_NAME, BUCKET_PROJ, PROJ_NAME
)  # cloud export directory
TMP_DIR = pathlib.Path.home() / "tmp"

PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"

# CONTAINER_NAME = "transects"
# PREFIX = f"gcts-{TRANSECT_LENGTH}m.parquet"
# BASE_URL = f"gs://{CONTAINER_NAME}/{PREFIX}"
GEOPARQUET_STAC_ITEMS_HREF = (
    f"gs://{BUCKET_NAME}/{BUCKET_PROJ}/{COLLECTION_ID}/{ds_fp.name}"
)


# %%
# %%
def read_parquet_schema_df(uri: str) -> List:  # pd.DataFrame:
    """Return a Pandas dataframe corresponding to the schema of a local URI of a parquet file.

    The returned dataframe has the columns: column, pa_dtype
    """
    # Ref: https://stackoverflow.com/a/64288036/
    # Ref: https://stackoverflow.com/questions/41567081/get-schema-of-parquet-file-in-python
    schema = pyarrow.parquet.read_schema(uri, memory_map=True)
    # schema = pd.DataFrame(({"name": name, "type": str(pa_dtype)} for name, pa_dtype in zip(schema.names, schema.types)))
    schema = [
        {
            "name": name,
            "type": str(pa_dtype),
            "description": "",
        }  # TODO: add column descriptions once received from the VU
        for name, pa_dtype in zip(schema.names, schema.types)
    ]
    # schema = schema.reindex(columns=["name", "type"], fill_value=pd.NA)  # Ensures columns in case the parquet file has an empty dataframe.
    return schema


def partition_dataframe(df: pd.DataFrame, batch_size: int) -> list[pd.DataFrame]:
    """
    Splits a DataFrame into partitions approximately equal to or smaller than the specified batch size.

    Args:
        df (pd.DataFrame): The DataFrame to be partitioned.
        batch_size (int): The maximum number of rows each partition should have.

    Returns:
        List[pd.DataFrame]: A list of DataFrames, each with a size up to the specified batch size.
    """
    n_rows = len(df)
    if n_rows <= batch_size:
        return [df]

    num_partitions = (n_rows + batch_size - 1) // batch_size
    partition_size = (n_rows + num_partitions - 1) // num_partitions

    partitions = [
        df.iloc[i : i + partition_size] for i in range(0, n_rows, partition_size)
    ]
    return partitions


@dataclasses.dataclass
class PathParts:
    """
    Parses a path into its component parts, supporting variations with and without hive partitioning,
    and with and without geographical bounds.
    """

    path: str
    container: str | None = None
    prefix: str | None = None
    name: str | None = None
    stac_item_id: str | None = None

    def __post_init__(self) -> None:
        # Strip any protocol pattern like "xyz://"
        stripped_path = re.sub(r"^\w+://", "", self.path)
        split = stripped_path.rstrip("/").split("/")

        # Extract container
        self.container = split[0]

        # Determine if there is hive partitioning and extract it
        hive_partition_info = [
            "_".join(part.split("=")) for part in split[1:-1] if "=" in part
        ]

        # Extract name, which is the filename with the .parquet extension
        self.name = split[-1]

        # Construct the stac_item_id
        # Include hive partitioning info if present, then add the file name, replacing ".parquet" and ensuring underscores
        parts_to_join = hive_partition_info + [self.name.replace(".parquet", "")]
        self.stac_item_id = "_".join(parts_to_join)


def create_collection(
    description: str | None = None, extra_fields: dict[str, Any] | None = None
) -> pystac.Collection:

    # NOTE: 2 providers, fixed quickly
    providers = [
        pystac.Provider(
            name=metadata["PROVIDERS"][0]["name"],
            roles=[
                pystac.provider.ProviderRole.PRODUCER,
                pystac.provider.ProviderRole.LICENSOR,
            ],
            url=metadata["PROVIDERS"][0]["url"],
        ),
        pystac.Provider(
            name=metadata["PROVIDERS"][1]["name"],
            roles=[
                pystac.provider.ProviderRole.PRODUCER,
                pystac.provider.ProviderRole.LICENSOR,
            ],
            url=metadata["PROVIDERS"][1]["url"],
        ),
        pystac.Provider(
            name="Deltares",
            roles=[
                pystac.provider.ProviderRole.PROCESSOR,
                pystac.provider.ProviderRole.HOST,
            ],
            url="https://deltares.nl",
        ),
    ]

    start_datetime = datetime.datetime.strptime(
        metadata["TEMPORAL_EXTENT"][0].split("T")[0], "%Y-%m-%d"
    )

    extent = pystac.Extent(
        pystac.SpatialExtent([metadata["SPATIAL_EXTENT"]]),
        pystac.TemporalExtent([[start_datetime, None]]),
    )

    # double check, this is hard-coded!
    # links = [
    #     pystac.Link(
    #         pystac.RelType.LICENSE,
    #         target="https://creativecommons.org/publicdomain/zero/1.0/",
    #         media_type="text/html",
    #         title="CC License",
    #     )
    # ]

    if "Creative Commons" in metadata["LICENSE"] and "4.0" in metadata["LICENSE"]:
        metadata["LICENSE"] = "CC-BY-4.0"

    collection = pystac.Collection(
        id=COLLECTION_ID,
        title=metadata["TITLE"],
        description=metadata["DESCRIPTION"],
        license=metadata["LICENSE"],
        providers=providers,
        extent=extent,
        catalog_type=pystac.CatalogType.RELATIVE_PUBLISHED,
    )

    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            f"https://storage.googleapis.com/coclico-data-public/coclico/assets/thumbnails/{COLLECTION_ID}.jpeg",
            title="Thumbnail",
            media_type=pystac.MediaType.JPEG,
        ),
    )
    # collection.links = links
    collection.keywords = metadata["KEYWORDS"]

    pystac.extensions.item_assets.ItemAssetsExtension.add_to(collection)

    collection.extra_fields["item_assets"] = {
        "data": {
            "title": metadata["TITLE_ABBREVIATION"],
            "description": metadata["SHORT_DESCRIPTION"],
            "roles": ["data"],
            "type": stac_table.PARQUET_MEDIA_TYPE,
            **ASSET_EXTRA_FIELDS,
        }
    }

    if extra_fields:
        collection.extra_fields.update(extra_fields)

    pystac.extensions.scientific.ScientificExtension.add_to(collection)
    collection.extra_fields["sci:citation"] = metadata["CITATION"]

    collection.stac_extensions.append(stac_table.SCHEMA_URI)

    pystac.extensions.version.VersionExtension.add_to(collection)
    collection.extra_fields["version"] = "1"

    return collection


def create_item(
    asset_href: str,
    storage_options: dict[str, Any] | None = None,
    asset_extra_fields: dict[str, Any] | None = None,
) -> pystac.Item:
    """Create a STAC Item

    For

    Args:
        asset_href (str): The HREF pointing to an asset associated with the item

    Returns:
        Item: STAC Item object
    """

    parts = PathParts(asset_href)

    properties = {
        "title": metadata["TITLE_ABBREVIATION"],
        "description": metadata["SHORT_DESCRIPTION"],
    }

    dt = datetime.datetime.strptime(
        metadata["TEMPORAL_EXTENT"][0].split("T")[0], "%Y-%m-%d"
    )
    # shape = shapely.box(*bbox)
    # geometry = shapely.geometry.mapping(shape)
    template = pystac.Item(
        id=parts.stac_item_id,
        properties=properties,
        geometry=None,
        bbox=None,
        datetime=dt,
        stac_extensions=[],
    )

    item = stac_table.generate(
        uri=asset_href,
        template=template,
        infer_bbox=True,
        infer_geometry=None,
        datetime_column=None,
        infer_datetime=stac_table.InferDatetimeOptions.no,
        count_rows=True,
        asset_key="data",
        asset_extra_fields=asset_extra_fields,
        proj=True,
        storage_options=storage_options,
        validate=False,
    )
    assert isinstance(item, pystac.Item)

    item.common_metadata.created = datetime.datetime.utcnow()

    # add descriptions to item properties
    if "table:columns" in ASSET_EXTRA_FIELDS and "table:columns" in item.properties:
        source_lookup = {
            col["name"]: col for col in ASSET_EXTRA_FIELDS["table:columns"]
        }

    for target_col in item.properties["table:columns"]:
        source_col = source_lookup.get(target_col["name"])
        if source_col:
            target_col.setdefault("description", source_col.get("description"))

    # TODO: make configurable upstream
    item.assets["data"].title = metadata["TITLE_ABBREVIATION"]
    item.assets["data"].description = metadata["SHORT_DESCRIPTION"]

    return item


# %%
# ## Do the work
if __name__ == "__main__":
    log = logging.getLogger()
    log.setLevel(logging.ERROR)

    # loading credentials
    load_google_credentials(
        google_token_fp=cred_data_dir.joinpath("google_credentials_new.json")
    )

    # %% test if file is multi-indexed, if we need to write to the cloud and whether we need to split files
    dum = gpd.read_parquet(ds_fp)  # read parquet file
    split = "N"  # value to determine if we need to split the files
    for file in os.listdir(ds_path):
        if file.endswith(".parquet"):
            if os.path.getsize(ds_path.joinpath(file)) / 10**6 > MAX_FILE_SIZE:
                split = "Y"  # change slit to Yes
                break

    # bucket content
    uri = f"gs://{BUCKET_NAME}/{BUCKET_PROJ}/{PROJ_NAME}"
    # storage_options = {"account_name": "coclico", "credential": sas_token}
    # fs, token, [root] = fsspec.get_fs_token_paths(uri, storage_options=storage_options)
    fs = gcsfs.GCSFileSystem(
        gcs_project=GCS_PROJECT, token=os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    )
    paths = fs.glob(uri + "/*.parquet")
    uris = ["gs://" + p for p in paths]

    # TODO: build something in for assessing size of parquet data, do this in both the if and elif statements
    if (
        dum.index.nlevels > 1 or split == "Y"
    ) and paths == []:  # if multi-indexed or split and there is nothing in the cloud
        files = os.listdir(ds_path)  # list all files in the directory
        files_clean = [k for k in files if ".parquet" in k]  # only select parquet files

        for file in files_clean:
            print(file)
            file_size = os.path.getsize(ds_path.joinpath(file)) / 10**6

            if file_size < MAX_FILE_SIZE:  # test if file size is smaller than 500MB
                dspd = gpd.read_parquet(ds_path.joinpath(file))  # read parquet file
                if dum.index.nlevels > 1:
                    dspd = dspd.reset_index()  # reset multi-index

                # write to the cloud, single file
                dspd.to_parquet(
                    f"{uri}/{file}", engine="pyarrow"
                )  # or supply with local path if needed

            elif file_size > MAX_FILE_SIZE:  # test if file size is smaller than 500MB
                dspd = gpd.read_parquet(ds_path.joinpath(file))  # read parquet file

                batch_size = int(
                    np.ceil(len(dspd) / np.ceil(file_size / MAX_FILE_SIZE))
                )  # calc batch size (max number of rows per partition)
                if dum.index.nlevels > 1:
                    dspd = dspd.reset_index()  # reset multi-index
                splitted_dspd = partition_dataframe(dspd, batch_size)  # calc partitions

                # write to the cloud, all split files
                for idx, split_dspd in enumerate(splitted_dspd):
                    file_name = (
                        file.split(".")[0]
                        + "_{:02d}.".format(idx + 1)
                        + file.split(".")[1]
                    )  # add zero-padded index (+1 to start at 1) to file name
                    split_dspd.to_parquet(
                        f"{uri}/{file_name}", engine="pyarrow"
                    )  # or supply with local path if needed

    elif (
        dum.index.nlevels == 1 and split == "N" and paths == []
    ):  # if not multi-indexed and no need to split and cloud file does not exist

        # upload directory to the cloud (files already parquet)
        file_to_google_cloud(
            file_path=str(ds_fp),
            gcs_project=GCS_PROJECT,
            bucket_name=BUCKET_NAME,
            bucket_proj=BUCKET_PROJ,
            dir_name=PROJ_NAME,
            file_name=ds_fp.name,
        )

    elif paths:
        print("Dataset already exists in the Google Bucket")

    # %% get descriptions
    COLUMN_DESCRIPTIONS = read_parquet_schema_df(
        uris[0]
    )  # select first file of the cloud directory

    ASSET_EXTRA_FIELDS = {
        "table:storage_options": {"account_name": "coclico"},
        "table:columns": COLUMN_DESCRIPTIONS,
    }

    # %% add to STAC
    catalog = pystac.Catalog.from_file(str(STAC_DIR / "catalog.json"))

    stac_io = DefaultStacIO()
    layout = ParquetLayout()

    collection = create_collection(extra_fields={"base_url": uri})

    for uri in uris:
        GCS_url = urljoin(HREF_PREFIX, uri.split("/")[-1])
        print(GCS_url)
        item = create_item(uri)
        item.assets["data"].href = GCS_url  # replace with https link iso gs uri
        collection.add_item(item)

    collection.update_extent_from_items()

    items = list(collection.get_all_items())
    items_as_json = [i.to_dict() for i in items]
    item_extents = stac_geoparquet.to_geodataframe(items_as_json)
    with fsspec.open(GEOPARQUET_STAC_ITEMS_HREF, mode="wb") as f:
        item_extents.to_parquet(f)

    collection.add_asset(
        "geoparquet-stac-items",
        pystac.Asset(
            GCS_url,
            title="GeoParquet STAC items",
            description="Snapshot of the collection's STAC items exported to GeoParquet format.",
            media_type=PARQUET_MEDIA_TYPE,
            roles=["data"],
        ),
    )

    # Set thumbnail directory
    THUMB_DIR = pathlib.Path(__file__).parent.parent.joinpath("thumbnails")
    THUMB_FILE = THUMB_DIR.joinpath(COLLECTION_ID + ".png")

    # Make sure image is reshaped to desired aspect ratio (default = 16/9)
    cropped_im = reshape_aspectratio_image(str(THUMB_FILE))

    # Overwrite image with cropped version
    cv2.imwrite(str(THUMB_FILE), cropped_im)

    # Upload thumbnail to cloud
    THUMB_URL = file_to_google_cloud(
        str(THUMB_FILE),
        GCS_PROJECT,
        BUCKET_NAME,
        BUCKET_PROJ,
        "assets/thumbnails",
        THUMB_FILE.name,
        return_URL=True,
    )

    # Add thumbnail
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            THUMB_URL,  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    if catalog.get_child(collection.id):
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")

    catalog.add_child(collection)

    collection.normalize_hrefs(str(STAC_DIR / collection.id), layout)

    collection.validate_all()

    catalog.save(
        catalog_type=pystac.CatalogType.SELF_CONTAINED,
        dest_href=str(STAC_DIR),
        stac_io=stac_io,
    )

# %%
