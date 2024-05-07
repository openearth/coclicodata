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
import pathlib
import re
import json
import pyarrow
import gcsfs
import geopandas as gpd
import pandas as pd
from typing import Any

import fsspec
import pystac
import stac_geoparquet
from typing import List
from posixpath import join as urljoin
from dotenv import load_dotenv
from pystac.stac_io import DefaultStacIO

from coclicodata.etl.cloud_utils import load_google_credentials, dir_to_google_cloud
from coclicodata.drive_config import p_drive

from coastmonitor import stac_table
from coastmonitor.stac.layouts import ParquetLayout

# %%
# ## Define variables
# hard-coded input params at project level
GCS_PROTOCOL = "https://storage.googleapis.com"
GCS_PROJECT = "coclico-11207608-002"
BUCKET_NAME = "coclico-data-public"
BUCKET_PROJ = "coclico"
PROJ_NAME = "ceed"

# hard-coded STAC templates
STAC_DIR = pathlib.Path.cwd() / "current"

# hard-coded input params which differ per dataset
METADATA = "metadata_infra_objects.json"
DATASET_DIR = "WP5"
# CF_FILE = "Global_merit_coastal_mask_landwards.tif"
COLLECTION_ID = "ceed"  # name of stac collection

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
    ds_dir = tmp_dir.joinpath(DATASET_DIR)
else:
    ds_dir = coclico_data_dir.joinpath(DATASET_DIR)

if not ds_dir.exists():
    raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

# # directory to export result
# cog_dirs = ds_dir.joinpath("cogs")
ds_path = ds_dir.joinpath("pilot/nuts2_ceed/pilot/")
# ds_fp = ds_dir.joinpath(CF_FILE)  # file directory

# # load metadata template
metadata_fp = ds_dir.joinpath("metadata", METADATA)
with open(metadata_fp, "r") as f:
    metadata = json.load(f)

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
    f"gs://{BUCKET_NAME}/{BUCKET_PROJ}/items/{COLLECTION_ID}.parquet"
)


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

    providers = [
        pystac.Provider(
            name=metadata["PROVIDERS"]["name"],
            roles=[
                pystac.provider.ProviderRole.PRODUCER,
                pystac.provider.ProviderRole.LICENSOR,
            ],
            url=metadata["PROVIDERS"]["url"],
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
            f"https://storage.googleapis.com/dgds-data-public/coclico/assets/thumbnails/{COLLECTION_ID}.jpeg",
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

    # %% test if file is multi-indexed and if we need to write to the cloud
    dum = gpd.read_parquet(
        ds_path.joinpath(os.listdir(ds_path)[0])
    )  # read parquet file

    # bucket content
    uri = f"gs://{BUCKET_NAME}/{BUCKET_PROJ}/{PROJ_NAME}"
    # storage_options = {"account_name": "coclico", "credential": sas_token}
    # fs, token, [root] = fsspec.get_fs_token_paths(uri, storage_options=storage_options)
    fs = gcsfs.GCSFileSystem(
        gcs_project=GCS_PROJECT, token=os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    )
    paths = fs.glob(uri + "/*.parquet")
    uris = ["gs://" + p for p in paths]

    if (
        dum.index.nlevels > 1 and paths == []
    ):  # if multi-indexed and there is nother in the cloud

        for uri in os.listdir(ds_path):
            dspd = gpd.read_parquet(ds_path.joinpath(uri))  # read parquet file
            dspd = dspd.reset_index()
            file = uri.split("/")[-1]

            # write to the cloud
            dspd.to_parquet(
                f"gs://{BUCKET_NAME}/{BUCKET_PROJ}/{PROJ_NAME}/{file}", engine="pyarrow"
            )  # or supply with local path if needed

    elif (
        dum.index.nlevels == 1 and paths == []
    ):  # if not multi-indexed and cloud file does not exist

        # upload directory to the cloud (files already parquet)
        dir_to_google_cloud(
            dir_path=str(ds_path),
            gcs_project=GCS_PROJECT,
            bucket_name=BUCKET_NAME,
            bucket_proj=BUCKET_PROJ,
            dir_name=PROJ_NAME,
        )

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
        item = create_item(uri)
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
            GEOPARQUET_STAC_ITEMS_HREF,
            title="GeoParquet STAC items",
            description="Snapshot of the collection's STAC items exported to GeoParquet format.",
            media_type=PARQUET_MEDIA_TYPE,
            roles=["data"],
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
