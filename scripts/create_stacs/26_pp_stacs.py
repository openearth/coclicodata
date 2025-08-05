# %%
# ## Load software
import datetime

# import os
import pathlib
import glob
import os
import cv2

# import sys
# from re import S, template
import json5
import pyarrow
import fsspec
import gcsfs
from typing import Any, Dict, List, Optional, Tuple, Union

# import cftime
# import numpy as np
import pandas as pd
import pystac
import rasterio

# import rioxarray as rio
import shapely
import xarray as xr
import math
import dask
import stac_geoparquet
from posixpath import join as urljoin
from pystac import Summaries
from pystac.extensions import eo, raster
from stactools.core.utils import antimeridian
from pystac.stac_io import DefaultStacIO

# from datacube.utils.cog import write_cog
from coclicodata.drive_config import p_drive

# from pystac import Catalog, CatalogType, Collection, Summaries
from coclicodata.etl.cloud_utils import (
    load_google_credentials,
    dir_to_google_cloud,
    file_to_google_cloud,
)
from coclicodata.coclico_stac.io import CoCliCoStacIO
from coclicodata.coclico_stac.reshape_im import reshape_aspectratio_image
from coclicodata.coclico_stac.layouts import CoCliCoCOGLayout
from coclicodata.coclico_stac.extension import (
    CoclicoExtension,
)  # self built stac extension
from coclicodata.coclico_stac.templates import extend_links

# from coastmonitor.io.cloud import (
#     to_https_url,
#     to_storage_location,
#     to_uri_protocol,
#     write_block,
# )
from coastmonitor.io.utils import name_block
from rasterio import logging

log = logging.getLogger()
log.setLevel(logging.ERROR)

# %%
# ## Define variables
# hard-coded input params at project level
GCS_PROTOCOL = "https://storage.googleapis.com"
GCS_PROJECT = "coclico-11207608-002"
BUCKET_NAME = "coclico-data-public"
BUCKET_PROJ = "coclico"
PROJ_NAME = "pp"

# hard-coded STAC templates
CUR_CWD = pathlib.Path.cwd()
STAC_DIR = CUR_CWD / "current"  # .parent.parent

# hard-coded input params which differ per dataset
METADATA = "metadata_population.json"
DATASET_DIR = "WP5"
CF_FILE = "SSP1_2010_Europe.tif"  # NOTE: multiple files
COLLECTION_ID = "pp"  # name of stac collection

# these are added at collection level, determine dashboard graph layout using all items
PLOT_SERIES = "scenarios"
PLOT_X_AXIS = "time"
PLOT_TYPE = "line"
MIN = 0
MAX = 3
LINEAR_GRADIENT = [
    {"color": "hsl(110,90%,80%)", "offset": "0.000%", "opacity": 100},
    {"color": "hsla(55,88%,53%,0.5)", "offset": "50.000%", "opacity": 100},
    {"color": "hsl(0,90%,70%)", "offset": "100.000%", "opacity": 100},
]

# define local directories
home = pathlib.Path().home()
tmp_dir = home.joinpath("data", "tmp")
coclico_data_dir = p_drive.joinpath(
    "11207608-coclico", "FULLTRACK_DATA"
)  # remote p drive
google_cred_dir = p_drive.joinpath(
    "11207608-coclico", "FASTTRACK_DATA", "google_credentials_new.json"
)

# use local or remote data dir
use_local_data = False

if use_local_data:
    ds_dir = tmp_dir.joinpath(DATASET_DIR)
else:
    ds_dir = coclico_data_dir.joinpath(DATASET_DIR)

if not ds_dir.exists():
    raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

# directory to export result
cog_dirs = ds_dir.joinpath("cogs")
ds_fp = ds_dir.joinpath(CF_FILE)  # file directory

# load metadata template
metadata_fp = ds_dir.joinpath("metadata", METADATA)
with open(metadata_fp, "r") as f:
    metadata = json5.load(f)

# data output configurations
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


def create_collection(
    description: str | None = None, extra_fields: dict[str, Any] | None = None
) -> pystac.Collection:
    providers = [
        pystac.Provider(
            name="Deltares",
            roles=[
                pystac.provider.ProviderRole.PROCESSOR,
                pystac.provider.ProviderRole.HOST,
            ],
            url="https://deltares.nl",
        ),
        pystac.Provider(
            "Geographisches Institut, Kiel University",
            roles=[
                pystac.provider.ProviderRole.PRODUCER,
            ],
            url="www.uni-kiel.de",
        ),
    ]

    start_datetime = datetime.datetime(2024, 1, 18, tzinfo=datetime.timezone.utc)

    extent = pystac.Extent(
        pystac.SpatialExtent([[-180, -89.9999999999, 180, 90.0000000001]]),
        pystac.TemporalExtent([[start_datetime, None]]),
    )

    links = [
        pystac.Link(
            rel=pystac.RelType.LICENSE,
            target="https://coclicoservices.eu/legal/",
            media_type="text/html",
            title="ODbL-1.0 License",  # NOTE: not sure if this applies
        )
    ]

    keywords = [
        "Coast",
        "Population",
        "Projection",
        "Shared Socioeconomic Pathways",
        "Europe",
        "European" "CoCliCo",
        "Deltares",
        "Cloud Optimized GeoTIFF",
        "Exposure & Vulnerability",
        "Data Layers",
    ]

    if description is None:
        description = "Merkens et al. 2016 regionalised the population projection of the SSP-Database. The produced grids have a spatial resolution of 30*30 arcsecond (approx. 1 km at the equator) and represent the population count per cell. A detailed description of the methods is given in the reference below."

    if "Creative Commons" in metadata["LICENSE"] and "4.0" in metadata["LICENSE"]:
        metadata["LICENSE"] = "CC-BY-4.0"

    collection = pystac.Collection(
        id=COLLECTION_ID,
        title="Population Projections",
        description=metadata["SHORT_DESCRIPTION"],  # noqa: E502
        license=metadata["LICENSE"],
        providers=providers,
        extent=extent,
        catalog_type=pystac.CatalogType.RELATIVE_PUBLISHED,
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

    collection.add_asset(
        "geoserver_link",
        pystac.Asset(
            "https://coclico.avi.deltares.nl/geoserver/gwc/service/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&LAYER=pp:pop_fp_LAU_EPSG4326&STYLE=&TILEMATRIX=EPSG:900913:{z}&TILEMATRIXSET=EPSG:900913&FORMAT=application/vnd.mapbox-vector-tile&TILECOL={x}&TILEROW={y}",
            title="Geoserver Parquet link",
            media_type="application/vnd.apache.parquet",
        ),
    )

    collection.links = links
    collection.keywords = keywords

    pystac.extensions.item_assets.ItemAssetsExtension.add_to(collection)

    ASSET_EXTRA_FIELDS = {
        "xarray:storage_options": {"token": "google_default"},
    }

    collection.extra_fields["item_assets"] = {
        "data": {
            "type": pystac.MediaType.COG,
            "title": "Gridded population projections for the coastal zone under the Shared Socioeconomic Pathways",
            "roles": ["data"],
            "description": "Merkens et al. 2016 regionalised the population projection of the SSP-Database. The produced grids have a spatial resolution of 30*30 arcsecond (approx. 1 km at the equator) and represent the population count per cell. A detailed description of the methods is given in the reference below.",
            **ASSET_EXTRA_FIELDS,
        }
    }

    if extra_fields:
        collection.extra_fields.update(extra_fields)

    # add coclico frontend properties to collection, NOTE: custom extension does not work like this anymore, need renewed generic method to manage this centrally
    # coclico_ext = CoclicoExtension.ext(collection, add_if_missing=True)
    # coclico_ext.units = "float32"
    # coclico_ext.plot_type = "raster"
    # coclico_ext.min = 1
    # coclico_ext.max = 100000  # NOTE: not checked

    # CoclicoExtension.add_to(collection)
    collection.extra_fields["deltares:units"] = metadata["UNITS"]
    collection.extra_fields["deltares:plot_type"] = PLOT_TYPE
    collection.extra_fields["deltares:min"] = MIN
    collection.extra_fields["deltares:max"] = MAX
    collection.extra_fields["deltares:clickable"] = (
        False  # TODO: test if it worked properly (put in manually in collection now)
    )

    return collection


# %%
def create_item(block, item_id, antimeridian_strategy=antimeridian.Strategy.SPLIT):
    dst_crs = rasterio.crs.CRS.from_epsg(4326)

    # when the data spans a range, it's common practice to use the middle time as the datetime provided
    # in the STAC item. So then you have to infer the start_datetime, end_datetime and get the middle
    # from those.
    # start_datetime, end_datetime = ...
    # middle_datetime = start_datetime + (end_datetime - start_datetime) / 2

    # the bbox of the STAC item is provided in 4326
    bbox = rasterio.warp.transform_bounds(block.rio.crs, dst_crs, *block.rio.bounds())
    geometry = shapely.geometry.mapping(shapely.make_valid(shapely.geometry.box(*bbox)))
    bbox = shapely.make_valid(shapely.box(*bbox)).bounds

    item = pystac.Item(
        id=item_id,
        geometry=geometry,
        bbox=bbox,
        datetime=pd.Timestamp(block["time"].item()),
        properties={},
    )

    # useful for global datasets that cross the antimerdian E-W line
    antimeridian.fix_item(item, antimeridian_strategy)

    # use this when the data spans a certain time range
    # item.common_metadata.start_datetime = start_datetime
    # item.common_metadata.end_datetime = end_datetime

    item.common_metadata.created = datetime.datetime.utcnow()

    ext = pystac.extensions.projection.ProjectionExtension.ext(
        item, add_if_missing=True
    )
    ext.bbox = block.rio.bounds()  # these are provided in the crs of the data
    ext.shape = tuple(v for k, v in block.sizes.items() if k in ["y", "x"])
    ext.epsg = block.rio.crs.to_epsg()
    ext.geometry = shapely.geometry.mapping(shapely.geometry.box(*ext.bbox))
    ext.transform = list(block.rio.transform())[:6]
    ext.add_to(item)

    # add CoCliCo frontend properties to visualize it in the web portal
    # TODO: This is just example. We first need to decide which properties frontend needs for COG visualization
    # NOTE: custom extension does not work like this anymore, need renewed generic method to manage this centrally
    # coclico_ext = CoclicoExtension.ext(item, add_if_missing=True)
    # coclico_ext.item_key = item_id
    # coclico_ext.add_to(item)

    # CoclicoExtension.add_to(item)
    item.properties["deltares:item_key"] = item_id

    # add more functions to describe the data at item level, for example the frontend properties to visualize it
    ...

    return item


# %%
def create_asset(
    item, asset_title, asset_href, nodata, resolution, data_type, nbytes=None
):
    asset = pystac.Asset(
        href=asset_href,
        media_type=pystac.MediaType.COG,
        title=asset_title,
        roles=["data"],
    )

    item.add_asset(asset_title, asset)

    pystac.extensions.file.FileExtension.ext(asset, add_if_missing=True)

    if nbytes:
        asset.extra_fields["file:size"] = nbytes

    raster.RasterExtension.ext(asset, add_if_missing=True).bands = [
        raster.RasterBand.create(
            nodata=nodata,
            spatial_resolution=resolution,
            data_type=data_type,  # e.g., raster.DataType.INT8
        )
    ]

    eo.EOExtension.ext(asset, add_if_missing=True).bands = [
        eo.Band.create(
            name=asset_title,
            # common_name=asset_title, # Iff in <eo#common-band-names>`
            description="POP_SSPs",
        )
    ]
    ...
    return item


# %%
# ## Function to process one data partition
def process_block(
    file_path: pathlib.Path,
    base_path: pathlib.Path,  # NOTE: only needed because the cog's are stored in a dimension folder structure
    data_type: raster.DataType,  # Make sure to have raster.DataType properly imported
    resolution: int,
    storage_prefix: str = "",
    name_prefix: str = "",
    include_band: str = "",
    time_dim: str = "",
    x_dim: str = "x",
    y_dim: str = "y",
    profile_options: Dict[str, Union[str, int]] = {},
    storage_options: Dict[str, str] = {},
) -> "pystac.Item":
    """
    Process a data block, save it, and return a placeholder STAC item.

    Args:
    - block: The data block.
    - storage_prefix: The storage prefix.
    ... [other parameters]

    Returns:

    - pystac.Item: Placeholder STAC item.
    """
    # Open dataset (.tif in this case)
    block = xr.open_dataset(file_path, engine="rasterio", mask_and_scale=False)

    # Date when Lincke et al. sent Deltares this data
    block = block.assign_coords(time=pd.Timestamp(2022, 2, 22).isoformat())

    item_id = file_path.relative_to(base_path).as_posix()
    item = create_item(block, item_id=item_id)

    for var in block:
        da = block[var]

        href = urljoin(storage_prefix, pathlib.Path(file_path.name).as_posix())
        # href = name_block(
        #     da,
        #     storage_prefix=storage_prefix,
        #     name_prefix=name_prefix,
        #     time_dim=time_dim,
        #     x_dim=x_dim,
        #     y_dim=y_dim,
        # )

        # uri = to_uri_protocol(href, protocol="gs")

        # TODO: include this file checking
        # if not file_exists(file, str(storage_destination), existing_blobs):
        # nbytes = write_block(da, uri, storage_options, profile_options, overwrite=True)

        nbytes = os.path.getsize(file_path)

        item = create_asset(
            item,
            asset_title=da.name,
            asset_href=href,
            nodata=da.rio.nodata.item(),  # use item() as this converts np dtype to python dtype
            resolution=resolution,
            data_type=raster.DataType.FLOAT32,  # should be same as how data is written
            nbytes=nbytes,
        )

    return item


# %%
def generate_slices(num_chunks: int, chunk_size: int) -> Tuple[slice, slice]:
    """Generate slices for chunk-based iteration."""
    for i in range(num_chunks):
        yield slice(i * chunk_size, (i + 1) * chunk_size)


# %%
def get_paths(folder_structure, base_dir=""):
    """Generate paths for a folder structure defined by a dict"""
    paths = []
    for key, value in folder_structure.items():
        if isinstance(value, dict):
            paths.extend(get_paths(value, os.path.join(base_dir, key)))
        elif isinstance(value, list):
            if value:
                for item in value:
                    if item != "":
                        paths.append(os.path.join(base_dir, key, item))
            else:
                paths.append(os.path.join(base_dir, key))
        else:
            continue
    return paths


# %%
# ## Do the work
if __name__ == "__main__":

    # store to cloud folder

    # # upload directory with cogs to google cloud
    load_google_credentials(google_token_fp=google_cred_dir)

    # dir_to_google_cloud(
    #     dir_path=str(cog_dirs),
    #     gcs_project=GCS_PROJECT,
    #     bucket_name=BUCKET_NAME,
    #     bucket_proj=BUCKET_PROJ,
    #     dir_name=PROJ_NAME,
    # )

    fs = gcsfs.GCSFileSystem(
        gcs_project=GCS_PROJECT, token=os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    )

    # get descriptions
    uri_dum = f"gs://{BUCKET_NAME}/{BUCKET_PROJ}/pp_stats"
    paths_dum = fs.glob(uri_dum + "/*.parquet")
    uris_dum = ["gs://" + p for p in paths_dum]
    HREF_PREFIX_dum = urljoin(
        GCS_PROTOCOL, BUCKET_NAME, BUCKET_PROJ, "pp_stats"
    )  # cloud export directory
    GCS_url_dum = urljoin(HREF_PREFIX_dum, uris_dum[0].split("/")[-1])
    COLUMN_DESCRIPTIONS = read_parquet_schema_df(
        uris_dum[0]
    )  # select first file of the cloud directory

    ASSET_EXTRA_FIELDS = {
        "table:storage_options": {"account_name": "coclico"},
        "table:columns": COLUMN_DESCRIPTIONS,
    }

    ## Setup folder structure

    # List the desired folder structure as a dict
    # NOTE: make sure the resulting path_list (based on folder structure) matches the tif_list
    # NOTE: shortcut taken by calling every year twice, because there are two tif's per year.
    folder_structure = {
        "SSP1": ["2010", "2030", "2050", "2100", "2150"],
        "SSP2": ["2010", "2030", "2050", "2100", "2150"],
        "SSP5": ["2010", "2030", "2050", "2100", "2150"],
    }

    # Get list of paths for the folder structure
    path_list = get_paths(folder_structure)

    items = []
    dimcombs = []

    collection = create_collection()

    scens = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]
    years = ["2010", "2030", "2050", "2100"]
    item_properties = ["scenarios", "time"]

    for scen in scens:
        for year in years:

            # Define tif_list for the cog's created using ../notebooks/26_pp.ipynb
            tif_list = pathlib.Path.joinpath(cog_dirs, scen, year).glob("*.tif")

            for cur_tif in tif_list:

                # Open original dataset
                pp = xr.open_dataset(cur_tif, engine="rasterio", mask_and_scale=False)
                pp = pp.assign_coords(
                    band=("band", [f"B{k+1:02}" for k in range(pp.dims["band"])])
                )
                pp = pp["band_data"].to_dataset("band")

                profile_options = {
                    "driver": "COG",
                    "dtype": "float32",
                    "compress": "DEFLATE",
                    # "interleave": "band",
                    # "ZLEVEL": 9,
                    # "predictor": 1,
                }
                storage_options = {"token": "google_default"}

                # Get last 3 elements from pathlib.Path object

                #

                CUR_HREF_PREFIX = urljoin(HREF_PREFIX, scen, year)

                # Process the chunk using a delayed function
                item = process_block(
                    cur_tif,
                    cog_dirs,
                    resolution=30,
                    data_type=raster.DataType.FLOAT32,
                    storage_prefix=CUR_HREF_PREFIX,
                    name_prefix="B01",
                    include_band="",
                    time_dim=False,
                    x_dim="x",
                    y_dim="y",
                    profile_options=profile_options,
                    storage_options=storage_options,
                )

                item_href = pathlib.Path(
                    STAC_DIR, COLLECTION_ID, "items", cur_tif.parent, item.id
                )
                item_href.with_suffix(".json")
                item.set_self_href(item_href)

                title = (
                    COLLECTION_ID
                    + ":"
                    + pathlib.Path(item_href).with_suffix(".tif").stem
                )
                # TODO: We need to generalize this `href` somewhat.
                vasset = pystac.Asset(  # data asset
                    href="https://coclico.avi.deltares.nl/geoserver/%s/wms?bbox={bbox-epsg-3857}&format=image/png&service=WMS&version=1.1.1&request=GetMap&srs=EPSG:3857&transparent=true&width=256&height=256&layers=%s"
                    % (COLLECTION_ID, title),
                    media_type="application/png",
                    title=title,
                    description="OGS WMS url",
                    roles=["visual"],
                )

                # TODO: generalize this
                dimcomb = {
                    item_properties[0]: scen,
                    item_properties[1]: year,
                }
                dimcombs.append(dimcomb)

                # TODO: include this in our datacube?
                # add dimension key-value pairs to stac item properties dict
                for k, v in dimcomb.items():
                    item.properties[k] = v

                item.add_asset("visual", vasset)

                items.append(item)
                collection.add_item(item)

                print(len(items))

    # %%
    # stac_io = CoCliCoStacIO()
    stac_io = DefaultStacIO()
    layout = CoCliCoCOGLayout()

    # Set up folder structure
    for cur_path in path_list:
        STAC_DIR.joinpath(COLLECTION_ID, "items", cur_path).mkdir(
            parents=True, exist_ok=True
        )

    collection.update_extent_from_items()

    collection.summaries = Summaries({})
    # TODO: check if maxcount is required (inpsired on xstac library)
    # stac_obj.summaries.maxcount = 50
    dimvals = {}
    for d in dimcombs:
        for key, value in d.items():
            if key not in dimvals:
                dimvals[key] = []
            if value not in dimvals[key]:
                dimvals[key].append(value)

    # set extra link properties
    extend_links(collection, dimvals.keys())

    collection.update_extent_from_items()

    dims_to_ignore = {"scenarios": ["SSP3", "SSP4"]}

    # Delete dims_to_ignore from dimvals
    for k, v in dims_to_ignore.items():
        for val in v:
            if val in dimvals[k]:
                dimvals[k].remove(val)

    for k, v in dimvals.items():
        collection.summaries.add(k, v)

    items = list(collection.get_all_items())
    items_as_json = [i.to_dict() for i in items]
    item_extents = stac_geoparquet.to_geodataframe(items_as_json)
    with fsspec.open(GEOPARQUET_STAC_ITEMS_HREF, mode="wb") as f:
        item_extents.to_parquet(f)

    collection.add_asset(
        "geoparquet-stac-items",
        pystac.Asset(
            GCS_url_dum,
            title="GeoParquet STAC items",
            description="Snapshot of the collection's STAC items exported to GeoParquet format.",
            media_type=PARQUET_MEDIA_TYPE,
            roles=["data"],
        ),
    )

    catalog = pystac.Catalog.from_file(str(STAC_DIR / "catalog.json"))

    if catalog.get_child(collection.id):
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")

    catalog.add_child(collection)

    # NOTE: This function creates problems for maintaining the folder structure. Look into this.
    collection.normalize_hrefs(str(STAC_DIR / collection.id), strategy=layout)

    catalog.save(
        catalog_type=pystac.CatalogType.SELF_CONTAINED,
        dest_href=str(STAC_DIR),
        stac_io=stac_io,
    )

    # %%
    # TODO: # check coastal_mask_stacs.py validate funcs with coclico_new..
    collection.validate_all()

    # # %%
    catalog.validate_all()
# %%
