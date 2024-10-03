# %%
# ## Load software
import datetime

# import os
import pathlib
import glob
import os

# import sys
# from re import S, template
import json
import fsspec
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
from posixpath import join as urljoin
from pystac.extensions import eo, raster
from stactools.core.utils import antimeridian
from pystac.stac_io import DefaultStacIO

# from datacube.utils.cog import write_cog
from coclicodata.drive_config import p_drive

from pystac import Catalog, CatalogType, Collection, Summaries
from coclicodata.etl.cloud_utils import load_google_credentials, dir_to_google_cloud
from coclicodata.coclico_stac.io import CoCliCoStacIO
from coclicodata.coclico_stac.layouts import CoCliCoCOGLayout
from coclicodata.coclico_stac.extension import (
    CoclicoExtension,
)  # self built stac extension
from coclicodata.coclico_stac.templates import (
    extend_links,
    gen_default_collection_props,
    gen_default_item,
    gen_default_item_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_template_collection,
)

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
PROJ_NAME = "cfhp"

# hard-coded STAC templates
CUR_CWD = pathlib.Path.cwd()
STAC_DIR = CUR_CWD / "current"  # .parent.parent

# hard-coded input params which differ per dataset
METADATA = "Mean_spring_tide_HD.json"
DATASET_DIR = "WP4"
CF_FILE = "Mean_spring_tide_HD.tif"  # NOTE: multiple files
COLLECTION_ID = "cfhp"  # name of stac collection

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
metadata_fp = ds_dir.joinpath("data", "HIGH_DEFENDED_MAPS", "Metadata", METADATA)
with open(metadata_fp, "r") as f:
    metadata = json.load(f)

# data output configurations
HREF_PREFIX = urljoin(
    GCS_PROTOCOL, BUCKET_NAME, BUCKET_PROJ, PROJ_NAME
)  # cloud export directory
TMP_DIR = pathlib.Path.home() / "tmp"


# %%
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
            "Universidad de Cantabria, Instituto de Hidráulica Ambiental de la Universidad de Cantabria 'IHCantabria'",
            roles=[
                pystac.provider.ProviderRole.PRODUCER,
            ],
            url="www.ihcantabria.com",
        ),
    ]

    start_datetime = datetime.datetime(2024, 1, 18, tzinfo=datetime.timezone.utc)

    extent = pystac.Extent(
        pystac.SpatialExtent([[5415925, 941625, 1547750, 6525950]]),
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
        "Flood Maps",
        "Coastal Hazard",
        "Coastal Hazards",
        "Flood Risk",
        "Flood Projections",
        "Coastal Hazard Flood Projections",
        "Europe",
        "European" "CoCliCo",
        "Deltares",
        "Cloud Optimized GeoTIFF",
        "Natural Hazards",
        "Full-Track",
    ]

    if description is None:
        description = "This is a collection of maps representing the flood simulation across Europe for different scenarios"

    if "Creative Commons" in metadata["LICENSE"] and "4.0" in metadata["LICENSE"]:
        metadata["LICENSE"] = "CC-BY-4.0"

    collection = pystac.Collection(
        id=COLLECTION_ID,
        title="Coastal Hazard Flood Projections",
        description=description,  # noqa: E502
        license=metadata["LICENSE"],  # NOTE: not sure if this applies
        providers=providers,
        extent=extent,
        catalog_type=pystac.CatalogType.RELATIVE_PUBLISHED,
    )

    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://storage.googleapis.com/dgds-data-public/coclico/assets/thumbnails/"
            + COLLECTION_ID
            + ".png",  # noqa: E501,  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    collection.add_asset(
        "geoserver_link",
        pystac.Asset(
            "https://coclico.avi.deltares.nl/geoserver/gwc/service/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0&LAYER=cfhp:lau_nuts_cfhp&STYLE=&TILEMATRIX=EPSG:900913:{z}&TILEMATRIXSET=EPSG:900913&FORMAT=application/vnd.mapbox-vector-tile&TILECOL={x}&TILEROW={y}",
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
            "title": "Coastal Hazard Flood Projections",
            "roles": ["data"],
            "description": "Coastal Flooding projections for Europe",
            **ASSET_EXTRA_FIELDS,
        }
    }

    if extra_fields:
        collection.extra_fields.update(extra_fields)

    # add coclico frontend properties to collection, NOTE: custom extension does not work like this anymore, need renewed generic method to manage this centrally
    # coclico_ext = CoclicoExtension.ext(collection, add_if_missing=True)
    # coclico_ext.units = "float32"
    # coclico_ext.plot_type = "raster"
    # coclico_ext.min = 0
    # coclico_ext.max = 10  # NOTE: not checked

    collection.extra_fields["deltares:units"] = metadata["UNITS"]
    collection.extra_fields["deltares:plot_type"] = PLOT_TYPE
    collection.extra_fields["deltares:min"] = MIN
    collection.extra_fields["deltares:max"] = MAX

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
    if item_type == "single":
        bbox = rasterio.warp.transform_bounds(
            block.rio.crs, dst_crs, *block.rio.bounds()
        )
    if item_type == "mosaic":
        bbox = rasterio.warp.transform_bounds(
            block.rio.crs, dst_crs, *tuple(metadata["SPATIAL_EXTENT"])
        )
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

    if item_type == "single":
        ext.bbox = block.rio.bounds()  # these are provided in the crs of the data
    if item_type == "mosaic":
        ext.bbox = tuple(metadata["SPATIAL_EXTENT"])
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
            description="Coastal Flood Projections",
        )
    ]
    ...
    return item


def create_asset_mosaic(item, storage_prefix):
    title = (
        COLLECTION_ID
        + ":"
        + storage_prefix.split(COLLECTION_ID + "/")[1].replace("/", "_")
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

    item.add_asset("visual", vasset)
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
    item_name = name_block(
        block,
        storage_prefix="",
        name_prefix=name_prefix,
        include_band=None,
        time_dim=time_dim,
        x_dim=x_dim,
        y_dim=y_dim,
    )

    # item_name_dum = str(file_path).split("\\")[-1]
    if item_type == "single":
        item_id = file_path.relative_to(base_path).as_posix()
    if item_type == "mosaic":
        item_id = (
            file_path.relative_to(base_path).as_posix().split("/" + name_prefix)[0]
            + ".tif"
        )
    # item_id = item_id_dum.replace(item_name_dum, item_name)  # to match with item_name
    item = create_item(block, item_id=item_id)

    for var in block:
        da = block[var]

        href = name_block(
            da,
            storage_prefix=storage_prefix,
            name_prefix=name_prefix,
            time_dim=time_dim,
            x_dim=x_dim,
            y_dim=y_dim,
        )

        # uri = to_uri_protocol(href, protocol="gs")

        # TODO: include this file checking
        # if not file_exists(file, str(storage_destination), existing_blobs):
        # nbytes = write_block(da, uri, storage_options, profile_options, overwrite=True)

        nbytes = os.path.getsize(file_path)

        if item_type == "single":
            item = create_asset(
                item,
                asset_title=da.name,
                asset_href=href,
                nodata=da.rio.nodata.item(),  # use item() as this converts np dtype to python dtype
                resolution=resolution,
                data_type=raster.DataType.FLOAT32,  # should be same as how data is written
                nbytes=nbytes,
            )
        if item_type == "mosaic":
            item = create_asset_mosaic(item, storage_prefix=storage_prefix)

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

    ## Setup folder structure
    # List different types on map folders
    item_type = "mosaic"  # "single" or "mosaic"
    item_properties = ["defense level", "rp", "scenarios", "time"]
    map_types = [
        "HIGH_DEFENDED_MAPS",
        "LOW_DEFENDED_MAPS",
        "UNDEFENDED_MAPS",
    ]  # 3 options
    rps = ["static", "1", "100", "1000"]  # 4 options
    scenarios = ["none", "SSP126", "SSP245", "SSP585", "High_end"]  # 5 options
    times = ["2010", "2030", "2050", "2100", "2150"]  # 5 options

    # List all tif files present in first folder (note: it is assumed that the same files are present in all folders)
    # tif_list = glob.glob(str(ds_dir.joinpath("data", map_types[0], "*.tif")))

    # # List the desired folder structure as a dict
    # # NOTE: make sure the resulting path_list (based on folder structure) matches the tif_list
    # folder_structure = {
    #     "Mean_spring_tide": [],
    #     "RP": ["1000", "100", "1"],
    #     "SLR": {
    #         "High_end": ["2100", "2150"],
    #         "SSP126": ["2100"],
    #         "SSP245": ["2050", "2100"],
    #         "SSP585": ["2030", "2050", "2100"],
    #     },
    # }

    # # Get list of paths for the folder structure
    # path_list = get_paths(folder_structure)

    items = []
    dimcombs = []

    collection = create_collection()

    # for map_type in map_types:
    #     for cur_path in path_list:

    #         print("now working on: " + map_type + " " + cur_path)

    #         tif_list = pathlib.Path.joinpath(cog_dirs, map_type, cur_path).glob("*.tif")

    #         for cur_tif in tif_list:

    #             cfhp = xr.open_dataset(
    #                 cur_tif, engine="rasterio", mask_and_scale=False
    #             )  # .isel({"x":slice(0, 40000), "y":slice(0, 40000)})
    #             cfhp = cfhp.assign_coords(
    #                 band=("band", [f"B{k+1:02}" for k in range(cfhp.dims["band"])])
    #             )
    #             cfhp = cfhp["band_data"].to_dataset("band")

    #             profile_options = {
    #                 "driver": "COG",
    #                 "dtype": "float32",
    #                 "compress": "DEFLATE",
    #                 # "interleave": "band",
    #                 # "ZLEVEL": 9,
    #                 # "predictor": 1,
    #             }
    #             storage_options = {"token": "google_default"}

    #             CUR_HREF_PREFIX = urljoin(HREF_PREFIX, map_type, cur_path)

    #             # Process the chunk using a delayed function
    #             item = process_block(
    #                 cur_tif,
    #                 cog_dirs,
    #                 resolution=30,
    #                 data_type=raster.DataType.FLOAT32,
    #                 storage_prefix=CUR_HREF_PREFIX,
    #                 name_prefix="B01",
    #                 include_band="",
    #                 time_dim=False,
    #                 x_dim="x",
    #                 y_dim="y",
    #                 profile_options=profile_options,
    #                 storage_options=storage_options,
    #             )

    #             item_href = pathlib.Path(
    #                 STAC_DIR, COLLECTION_ID, "items", map_type, cur_path, item.id
    #             )
    #             item_href.with_suffix(".json")
    #             item.set_self_href(item_href)

    #             items.append(item)
    #             collection.add_item(item)

    for map_type in map_types:
        for rp in rps:
            for scen in scenarios:
                for time in times:
                    if (
                        rp == "static" and scen == "none" and time == "2010"
                    ):  # mean spring tide
                        tif_list = list(
                            pathlib.Path.joinpath(
                                cog_dirs, map_type, "Mean_spring_tide"
                            ).glob("*.tif")
                        )
                        cur_path = "Mean_spring_tide"
                        STAC_DIR.joinpath(COLLECTION_ID, "items", map_type).mkdir(
                            parents=True, exist_ok=True
                        )
                        filename = os.path.join(map_type, "Mean_spring_tide")
                        print(map_type, rp, scen, time)
                    elif (
                        rp != "static" and scen == "none" and time == "2010"
                    ):  # RPs frist batchs only for 2010 (hindcast)
                        tif_list = list(
                            pathlib.Path.joinpath(cog_dirs, map_type, "RP", rp).glob(
                                "*.tif"
                            )
                        )
                        cur_path = os.path.join("RP", rp)
                        STAC_DIR.joinpath(COLLECTION_ID, "items", map_type, "RP").mkdir(
                            parents=True, exist_ok=True
                        )
                        filename = os.path.join(map_type, "RP", rp)
                        print(map_type, rp, scen, time)
                    elif rp == "static" and scen != "none":  # this is for the SLR maps
                        tif_list = list(
                            pathlib.Path.joinpath(
                                cog_dirs, map_type, "SLR", scen, time
                            ).glob("*.tif")
                        )
                        cur_path = os.path.join("SLR", scen, time)
                        if (
                            len(tif_list) > 0
                        ):  # we have data so we continue (so not for all times)
                            STAC_DIR.joinpath(
                                COLLECTION_ID, "items", map_type, "SLR", scen
                            ).mkdir(parents=True, exist_ok=True)
                            filename = os.path.join(map_type, "SLR", scen, time)
                            print(map_type, rp, scen, time)
                        else:  # break loop if not satisfied
                            continue
                    else:  # break loop if not satisfied (so not for all other combinations)
                        continue

                    # print(len(tif_list))

                    # note, Here it changes because we are dealing with mosaics iso single tiffs. We will use a single tiff to create one item to direct to the mosaic
                    cfhp = xr.open_dataset(
                        tif_list[0], engine="rasterio", mask_and_scale=False
                    )  # .isel({"x":slice(0, 40000), "y":slice(0, 40000)})
                    cfhp = cfhp.assign_coords(
                        band=("band", [f"B{k+1:02}" for k in range(cfhp.dims["band"])])
                    )
                    cfhp = cfhp["band_data"].to_dataset("band")

                    profile_options = {
                        "driver": "COG",
                        "dtype": "float32",
                        "compress": "DEFLATE",
                        # "interleave": "band",
                        # "ZLEVEL": 9,
                        # "predictor": 1,
                    }
                    storage_options = {"token": "google_default"}

                    CUR_HREF_PREFIX = urljoin(HREF_PREFIX, map_type, cur_path)

                    # Process the chunk using a delayed function
                    item = process_block(
                        tif_list[0],
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

                    item_href = pathlib.Path(STAC_DIR, COLLECTION_ID, "items", cur_path)
                    item.set_self_href(item_href.with_suffix(".json"))
                    item.id = filename + ".tif"

                    # TODO: generalize this
                    dimcomb = {
                        item_properties[0]: map_type,
                        item_properties[1]: rp,
                        item_properties[2]: scen,
                        item_properties[3]: time,
                    }
                    dimcombs.append(dimcomb)

                    # TODO: include this in our datacube?
                    # add dimension key-value pairs to stac item properties dict
                    for k, v in dimcomb.items():
                        item.properties[k] = v

                    items.append(item)
                    collection.add_item(item)

    print(len(items))

    # %% store to cloud folder

    # # upload directory with cogs to google cloud
    # load_google_credentials(google_token_fp=google_cred_dir)

    # dir_to_google_cloud(
    #     dir_path=str(cog_dirs),
    #     gcs_project=GCS_PROJECT,
    #     bucket_name=BUCKET_NAME,
    #     bucket_proj=BUCKET_PROJ,
    #     dir_name=PROJ_NAME,
    # )

    # %%
    stac_io = DefaultStacIO()
    # stac_io = CoCliCoStacIO()
    layout = CoCliCoCOGLayout()

    # Set up folder structure
    # for map_type in map_types:
    #     for cur_path in path_list:
    #         STAC_DIR.joinpath(COLLECTION_ID, "items", map_type, cur_path).mkdir(
    #             parents=True, exist_ok=True
    #         )

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

    for k, v in dimvals.items():
        collection.summaries.add(k, v)

    # set extra link properties
    extend_links(collection, dimvals.keys())

    catalog = pystac.Catalog.from_file(str(STAC_DIR / "catalog.json"))

    if catalog.get_child(collection.id):
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")

    catalog.add_child(collection)

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
