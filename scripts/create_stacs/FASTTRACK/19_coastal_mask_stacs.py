# %%
# ## Load software
import datetime

# import os
import pathlib

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

# from datacube.utils.cog import write_cog
from coclicodata.drive_config import p_drive

# from pystac import Catalog, CatalogType, Collection, Summaries
from coclicodata.etl.cloud_utils import load_google_credentials, dir_to_google_cloud
from coclicodata.coclico_stac.io import CoCliCoStacIO
from coclicodata.coclico_stac.layouts import CoCliCoCOGLayout
from coclicodata.coclico_stac.extension import (
    CoclicoExtension,
)  # self built stac extension

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
GCS_PROJECT = "DGDS - I1000482-002"
BUCKET_NAME = "dgds-data-public"
BUCKET_PROJ = "coclico"
PROJ_NAME = "coastal_mask"

# hard-coded STAC templates
STAC_DIR = pathlib.Path.cwd() / "current"

# hard-coded input params which differ per dataset
METADATA = "metadata_coastal_mask.json"
DATASET_DIR = "19_coastal_mask"
CF_FILE = "Global_merit_coastal_mask_landwards.tif"
COLLECTION_ID = "coastal-mask"  # name of stac collection

# define local directories
home = pathlib.Path().home()
tmp_dir = home.joinpath("data", "tmp")
coclico_data_dir = p_drive.joinpath(
    "11207608-coclico", "FASTTRACK_DATA"
)  # remote p drive

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
metadata_fp = ds_dir.joinpath(METADATA)
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
            "Global Climate Forum",
            roles=[
                pystac.provider.ProviderRole.PRODUCER,
            ],
            url="https://globalclimateforum.org",
        ),
    ]

    start_datetime = datetime.datetime(2022, 2, 22, tzinfo=datetime.timezone.utc)

    extent = pystac.Extent(
        pystac.SpatialExtent([[-180.0, 90.0, 180.0, -90.0]]),
        pystac.TemporalExtent([[start_datetime, None]]),
    )

    links = [
        pystac.Link(
            rel=pystac.RelType.LICENSE,
            target="https://coclicoservices.eu/legal/",
            media_type="text/html",
            title="ODbL-1.0 License",
        )
    ]

    keywords = [
        "Coast",
        "Coastal Mask",
        "Coastal Change",
        "Coastal Hazards",
        "Flood Risk",
        "CoCliCo",
        "Deltares",
        "Cloud Optimized GeoTIFF",
    ]

    if description is None:
        description = (
            "Coastal mask that is derived from Copernicus elevation data combined with"
            " a maximum distanceto coastal water bodies."
        )

    collection = pystac.Collection(
        id=COLLECTION_ID,
        title="Coastal Mask",
        description=description,  # noqa: E502
        license="ODbL-1.0",
        providers=providers,
        extent=extent,
        catalog_type=pystac.CatalogType.RELATIVE_PUBLISHED,
    )

    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://coclico.blob.core.windows.net/assets/thumbnails/coastal-mask-thumbnail.png",  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
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
            "title": "Coastal Mask",
            "roles": ["data"],
            "description": "Coastal areas masked for this region.",
            **ASSET_EXTRA_FIELDS,
        }
    }

    if extra_fields:
        collection.extra_fields.update(extra_fields)

    pystac.extensions.scientific.ScientificExtension.add_to(collection)
    collection.extra_fields["sci:citation"] = "Lincke et al., 2023, in progress"

    # add coclico frontend properties to collection
    coclico_ext = CoclicoExtension.ext(collection, add_if_missing=True)
    coclico_ext.units = "bool"
    coclico_ext.plot_type = "raster"
    coclico_ext.min = 0
    coclico_ext.max = 1

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
    coclico_ext = CoclicoExtension.ext(item, add_if_missing=True)
    coclico_ext.item_key = item_id
    coclico_ext.add_to(item)

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
            description="Coastal mask for this region.",
        )
    ]
    ...
    return item


# %%
# ## Function to process one data partition
def process_block(
    block: xr.DataArray,
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

    item_id = pathlib.Path(item_name).stem
    item = create_item(block, item_id=item_id)

    for var in block:
        da = block[var]
        # it's more efficient to save the data as unsigned integer, so replace the -9999 nodata values by 0
        da = (
            da.where(da != -9999, 0)
            .astype("uint8")
            .rio.write_nodata(0)
            .rio.set_spatial_dims(x_dim="x", y_dim="y")
        )

        href = name_block(
            da,
            storage_prefix=storage_prefix,
            name_prefix=name_prefix,
            include_band=da.name,
            time_dim=time_dim,
            x_dim=x_dim,
            y_dim=y_dim,
        )

        # uri = to_uri_protocol(href, protocol="gs")

        # TODO: include this file checking
        # if not file_exists(file, str(storage_destination), existing_blobs):
        # nbytes = write_block(da, uri, storage_options, profile_options, overwrite=True)

        memfs = fsspec.filesystem("memory")

        with memfs.open("data", "wb") as buffer:
            da.squeeze().rio.to_raster(buffer, **profile_options)
            buffer.seek(0)

        nbytes = len(buffer.getvalue())

        item = create_asset(
            item,
            asset_title=da.name,
            asset_href=href,
            nodata=da.rio.nodata.item(),  # use item() as this converts np dtype to python dtype
            resolution=resolution,
            data_type=raster.DataType.UINT8,  # should be same as how data is written
            nbytes=nbytes,
        )

    return item


# %%
def generate_slices(num_chunks: int, chunk_size: int) -> Tuple[slice, slice]:
    """Generate slices for chunk-based iteration."""
    for i in range(num_chunks):
        yield slice(i * chunk_size, (i + 1) * chunk_size)


# %%
# ## Do the work
if __name__ == "__main__":
    from dask.distributed import Client

    print("Launching local client...")
    client = Client(
        threads_per_worker=1, processes=True, local_directory=TMP_DIR, n_workers=6
    )
    client
    print(client.dashboard_link)

    cm = xr.open_dataset(
        ds_fp, engine="rasterio", mask_and_scale=False
    )  # .isel({"x":slice(0, 40000), "y":slice(0, 40000)})
    cm = cm.assign_coords(band=("band", [f"B{k+1:02}" for k in range(cm.dims["band"])]))
    cm = cm["band_data"].to_dataset("band")

    profile_options = {
        "driver": "COG",
        "dtype": "uint8",
        "compress": "DEFLATE",
        # "interleave": "band",
        # "ZLEVEL": 9,
        # "predictor": 1,
    }
    storage_options = {"token": "google_default"}

    # chunk size
    chunk_size = 2**12  # 16384, which is large, but OK for int8 datatype.

    cm_chunked = cm.chunk({"x": chunk_size, "y": chunk_size})

    num_x_chunks = math.ceil(cm_chunked.dims["x"] / chunk_size)
    num_y_chunks = math.ceil(cm_chunked.dims["y"] / chunk_size)

    # items = []
    delayed_items = []

    for x_slice in generate_slices(num_x_chunks, chunk_size):
        for y_slice in generate_slices(num_y_chunks, chunk_size):
            chunk = cm_chunked.isel(x=x_slice, y=y_slice)

            # Process the chunk using a delayed function
            delayed_item = dask.delayed(process_block)(
                # item = process_block(
                chunk,
                resolution=30,
                data_type=raster.DataType.UINT8,
                storage_prefix=HREF_PREFIX,
                name_prefix="",
                include_band="",
                time_dim=False,
                x_dim="x",
                y_dim="y",
                profile_options=profile_options,
                storage_options=storage_options,
            )

            delayed_items.append(delayed_item)
            # items.append(item)

    items = dask.compute(*delayed_items)

    print(len(items))

    # %%
    # ## store to cloud folder

    # upload directory with cogs to google cloud
    load_google_credentials(
        google_token_fp=coclico_data_dir.joinpath("google_credentials.json")
    )

    dir_to_google_cloud(
        dir_path=str(cog_dirs),
        gcs_project=GCS_PROJECT,
        bucket_name=BUCKET_NAME,
        bucket_proj=BUCKET_PROJ,
        dir_name=PROJ_NAME,
    )

    # %%
    stac_io = CoCliCoStacIO()
    layout = CoCliCoCOGLayout()

    collection = create_collection()

    for i in items:
        collection.add_item(i)

    collection.update_extent_from_items()

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
