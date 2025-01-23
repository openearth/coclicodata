# %%
import os
import pathlib
import sys
import json
import cftime
import fsspec
import operator
import itertools
import xarray as xr
import numpy as np
import datetime
import rasterio
import shapely
import pandas as pd
from posixpath import join as urljoin
from typing import List, Mapping, Optional

import pystac
from coclicodata.drive_config import p_drive
from coclicodata.etl.cloud_utils import (
    dataset_from_google_cloud,
    load_google_credentials,
    dir_to_google_cloud,
)
from coclicodata.etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import Catalog, CatalogType, Collection, Summaries
from coclicodata.coclico_stac.io import CoCliCoStacIO
from pystac.stac_io import DefaultStacIO
from coclicodata.coclico_stac.layouts import CoCliCoCOGLayout
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
from coclicodata.coclico_stac.extension import CoclicoExtension
from coclicodata.coclico_stac.datacube import add_datacube
from coclicodata.coclico_stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
    rm_special_characters,
)

__version__ = "0.0.1"


def name_block(
    block: xr.DataArray,
    prefix: str = "",
    x_dim="x",
    y_dim="y",
) -> str:
    """
    Get the name for a block, based on the coordinates at the top-left corner.

    Parameters
    ----------
    block : xarray.DataArray
        A singly-chunked DataArray
    prefix : str, default ""
        The prefix to use when writing to disk. This might be just a path prefix
        like "path/to/dir", in which case the data will be written to disk. Or it
        might be an fsspec-uri, in which case the file will be written to that
        file system (e.g. Azure Blob Storage, S3, GCS)
    include_band : bool, default True
        Whether to include the "band" component in the name. You might wish to
        exclude the band component when generating an ID for a STAC Item, which
        will merge multiple assets into a single Item.
    x_dim : str, default "x"
        The name of the x dimension / coordinate.
    y_dim : str, default "y"
        The name of the y dimension / coordinate.

    Returns
    -------
    str
        The unique name for the block.

    Examples
    --------
    >>> import xarray as xr
    """
    minx = round(block.coords[x_dim][0].item(), 2)
    miny = round(block.coords[y_dim][0].item(), 2)
    maxx = round(block.coords[x_dim][-1].item(), 2)
    maxy = round(block.coords[y_dim][-1].item(), 2)
    # long name
    # name = f"minx={minx}_miny={miny}_maxx={maxx}_maxy{maxy}.tif"
    # or a bit shorter..
    name = f"minx={minx}-miny={miny}.tif"
    blob_name = os.path.join(prefix, name)
    return blob_name


def write_block(
    block: xr.DataArray,
    prefix: str = "",
    href_prefix: str = "",
    x_dim: str = "x",
    y_dim: str = "y",
    storage_options: Optional[Mapping[str, str]] = None,
):
    """
    Write a block of a DataArray to disk.

    Parameters
    ----------
    block : xarray.DataArray
        A singly-chunked DataArray
    prefix : str, default ""
        The prefix to use when writing to disk. This might be just a path prefix
        like "path/to/dir", in which case the data will be written to disk. Or it
        might be an fsspec-uri, in which case the file will be written to that
        file system (e.g. Azure Blob Storage, S3, GCS)
    x_dim : str, default "x"
        The name of the x dimension / coordinate.
    y_dim : str, default "y"
        The name of the y dimension / coordinate.
    storage_options : mapping, optional
        A mapping of additional keyword arguments to pass through to the fsspec
        filesystem class derived from the protocol in `prefix`.

    Returns
    -------
    xarray.DataArray
        A size-1 DataArray with the :class:pystac.Item for that block.

    Examples
    --------
    >>> import xarray as xr

    """
    # this is specific to azure blob storage. We could generalize to accept an fsspec URL.
    import rioxarray  # noqa

    storage_options = storage_options or {}
    blob_name = name_block(block, prefix=prefix, x_dim=x_dim, y_dim=y_dim)

    # map the blob name (str) to serializable filesystem (could also be cloud bucket)
    fs, _, paths = fsspec.get_fs_token_paths(blob_name, storage_options=storage_options)
    if len(paths) > 1:
        raise ValueError("too many paths", paths)
    path = paths[0]
    memfs = fsspec.filesystem("memory")

    with memfs.open("data", "wb") as buffer:
        block.squeeze().rio.to_raster(buffer, driver="COG")
        buffer.seek(0)

        if fs.protocol == "file":
            # can't write a MemoryFile to an io.BytesIO
            # fsspec should arguably handle this
            buffer = buffer.getvalue()
        fs.pipe_file(path, buffer)
        nbytes = len(buffer)

    # make a template for storing the results, probably usefuil for Dask to ensure correct
    # datatypes are returned without making complex meta arguments.
    result = (
        block.isel(**{k: slice(1) for k in block.dims}).astype(object).compute().copy()
    )
    template_item = pystac.Item("id", None, None, datetime.datetime(2000, 1, 1), {})
    item = itemize(
        block,
        template_item,
        nbytes=nbytes,
        x_dim=x_dim,
        y_dim=y_dim,
        prefix=prefix,
        href_prefix=href_prefix,
    )

    # indexing first entry along all dimensions and store pystac item as data value
    result[(0,) * block.ndim] = item
    return result


def itemize(
    block,
    item: pystac.Item,
    nbytes: int,
    *,
    asset_roles: "List[str] | None" = None,  # "" enables Python 3.8 development not to crash: https://github.com/tiangolo/typer/issues/371
    asset_media_type=pystac.MediaType.COG,
    prefix: str = "",
    href_prefix: str = "",
    time_dim="time",
    x_dim="x",
    y_dim="y",
) -> pystac.Item:
    """
    Generate a pystac.Item for an xarray DataArray

    The following properties will be be set on the output item using data derived
    from the DataArray:

        * id
        * geometry
        * datetime
        * bbox
        * proj:bbox
        * proj:shape
        * proj:geometry
        * proj:transform

    The Item will have a single asset. The asset will have the following properties set:

        * file:size

    Parameters
    ----------
    block : xarray.DataArray
        A singly-chunked DataArray
    item : pystac.Item
        A template pystac.Item to use to construct.
    asset_roles:
        The roles to assign to the item's asset.
    prefix : str, default ""
        The prefix to use when writing to disk. This might be just a path prefix
        like "path/to/dir", in which case the data will be written to disk. Or it
        might be an fsspec-uri, in which case the file will be written to that
        file system (e.g. Azure Blob Storage, S3, GCS)
    time_dim : str, default "time"
        The name of the time dimension / coordinate.
    x_dim : str, default "x"
        The name of the x dimension / coordinate.
    y_dim : str, default "y"
        The name of the y dimension / coordinate.
    storage_options : mapping, optional
        A mapping of additional keyword arguments to pass through to the fsspec
        filesystem class derived from the protocol in `prefix`.

    Returns
    -------
    xarray.DataArray
        A size-1 DataArray with the :class:pystac.Item for that block.
    """
    import rioxarray  # noqa

    item = item.clone()
    dst_crs = rasterio.crs.CRS.from_epsg(4326)

    bbox = rasterio.warp.transform_bounds(block.rio.crs, dst_crs, *block.rio.bounds())
    geometry = shapely.geometry.mapping(shapely.geometry.box(*bbox))

    # feature = gen_default_item(f"{var}-mapbox-{item_id}")
    # feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url))

    name = pathlib.Path(name_block(block, x_dim=x_dim, y_dim=y_dim)).stem
    item.id = f"{metadata['TITLE_ABBREVIATION']}-{name}"
    # item.id = pathlib.Path(name_block(block, x_dim=x_dim, y_dim=y_dim)).stem
    item.geometry = geometry
    item.bbox = bbox
    # item.datetime = pd.Timestamp(block.coords[time_dim].item()).to_pydatetime()

    ext = pystac.extensions.projection.ProjectionExtension.ext(
        item, add_if_missing=True
    )
    ext.bbox = block.rio.bounds()
    ext.shape = block.shape[-2:]
    ext.epsg = block.rio.crs.to_epsg()
    ext.geometry = shapely.geometry.mapping(shapely.geometry.box(*ext.bbox))
    ext.transform = list(block.rio.transform())[:6]
    ext.add_to(item)

    roles = asset_roles or ["data"]

    # TODO: We need to generalize this `href` somewhat.
    asset = pystac.Asset(
        href=name_block(block, x_dim=x_dim, y_dim=y_dim, prefix=href_prefix),
        media_type=asset_media_type,
        roles=roles,
    )
    asset.extra_fields["file:size"] = nbytes
    item.add_asset("cm", asset)
    # item.add_asset(str(block.band[0].item()), asset)

    return item


def make_template(data: xr.DataArray) -> xr.DataArray:
    """DataArray template for xarray to infer datatypes returned by function.

    Comparable to the dask meta argument.
    """
    offsets = dict(
        zip(
            data.dims,
            [
                np.hstack(
                    [
                        np.array(
                            0,
                        ),
                        np.cumsum(x)[:-1],
                    ]
                )
                for x in data.chunks
            ],
        )
    )
    template = data.isel(**offsets).astype(object)
    return template


def to_cog_and_stac(
    data: xr.DataArray, prefix="", storage_options=None
) -> List[pystac.Item]:
    template = make_template(data)
    storage_options = storage_options or {}

    r = data.map_blocks(
        write_block,
        kwargs=dict(prefix=prefix, storage_options=storage_options),
        template=template,
    )
    result = r.compute()
    new_items = collate(result)
    return new_items


def collate(items: xr.DataArray) -> List[pystac.Item]:
    """
    Collate many items by id, gathering together assets with the same item ID.
    """
    # flat list with stac items from datarray
    items2 = items.data.ravel().tolist()

    new_items = []
    key = operator.attrgetter("id")

    # TODO: group by osm slippy mapbox box?
    for _, group in itertools.groupby(sorted(items2, key=key), key=key):
        items = list(group)
        item = items[0].clone()
        new_items.append(item)
        # todo: check
        for other_item in items:
            other_item = other_item.clone()
            for k, asset in other_item.assets.items():
                item.add_asset(k, asset)
    return new_items


# rename or swap dimension names, the latter in case the name already exists as coordinate
if __name__ == "__main__":
    metadata_fp = pathlib.Path(__file__).parent.parent.parent.joinpath(
        "metadata_template.json"
    )
    with open(metadata_fp, "r") as f:
        metadata = json.load(f)

    # hard-coded input params at project level
    GCS_PROTOCOL = "https://storage.googleapis.com"
    GCS_PROJECT = "coclico-11207608-002"
    BUCKET_NAME = "coclico-data-public"
    BUCKET_PROJ = "coclico"

    # hard-coded input params which differ per dataset
    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "cisi"  # name of stac collection

    # data configurations
    # DATASET_FILENAME = "Global_merit_coastal_mask_landwards.tif"  # source data
    DATASET_FILENAME = "europe.tif"  # sample from source data
    HOME = pathlib.Path().home()
    DATA_DIR = HOME.joinpath("data", "src")
    COCLICO_DATA_DIR = coclico_data_dir = p_drive.joinpath(
        "11207608-coclico", "FASTTRACK_DATA"
    )  # remote p drive
    DATASET_DIR = "20_cisi"
    OUTDIR = pathlib.Path.home() / "data" / "tmp" / "cisi_test"
    HREF_PREFIX = f"https://storage.googleapis.com/coclico-data-public/coclico/{metadata['TITLE_ABBREVIATION']}"
    USE_LOCAL_DATA = False  # can be used when data is also stored locally

    # TODO: check what can be customized with layout.
    layout = CoCliCoCOGLayout()

    if USE_LOCAL_DATA:
        DATASET_DIR = (  # overwrite dataset directory if dirname is diferent on local
            "cisi"
        )
        ds_dir = DATA_DIR.joinpath(DATASET_DIR)
    else:
        ds_dir = COCLICO_DATA_DIR.joinpath(DATASET_DIR)

    if not ds_dir.exists():
        raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

    # directory to store results
    # OUTDIR.mkdir(parents=True, exist_ok=True)

    # upload directory with cogs to google cloud
    # cred_data_dir = p_drive.joinpath("11207608-coclico", "FASTTRACK_DATA")
    # # load google credentials
    # load_google_credentials(
    #     google_token_fp=cred_data_dir.joinpath("google_credentials_new.json")
    # )

    # dir_to_google_cloud(
    #     dir_path=str(ds_dir.joinpath("cogs")),
    #     gcs_project=GCS_PROJECT,
    #     bucket_name=BUCKET_NAME,
    #     bucket_proj=BUCKET_PROJ,
    #     dir_name=COLLECTION_ID,
    # )

    # read data, set spatial dims and add crs if not exists
    data_fp = ds_dir.joinpath(DATASET_FILENAME)
    ds = xr.open_dataset(data_fp, chunks={"x": 512, "y": 512})

    ds.rio.set_spatial_dims(x_dim="x", y_dim="y")
    if not ds.rio.crs:
        ds = ds.rio.write_crs(metadata["CRS"])

    catalog = Catalog.from_file(
        os.path.join(
            pathlib.Path(__file__).parent.parent.parent, STAC_DIR, "catalog.json"
        )
    )

    template_fp = os.path.join(
        pathlib.Path(__file__).parent.parent.parent,
        STAC_DIR,
        TEMPLATE_COLLECTION,
        "collection.json",
    )

    # generate collection for dataset
    collection = get_template_collection(
        template_fp=template_fp,
        collection_id=metadata["TITLE_ABBREVIATION"],
        title=metadata["TITLE"],
        description=metadata["DESCRIPTION"],
        keywords=[],
    )

    # add datacube defaults at collection level
    collection = add_datacube(
        ds,
        collection,
        temporal_dimension=False,
        x_dimension=ds.rio.x_dim,
        y_dimension=ds.rio.y_dim,
    )

    # the cloud optimized geotiffs are created from a DataArray not Dataset
    da = ds["band_data"]

    # template represents the shape of the final result after the computation (like dask meta)
    template = make_template(da)
    r = da.map_blocks(
        write_block,
        kwargs=dict(
            # TODO: adjust the prefix str to osm slippy max box and use the collate function
            # to categorize the items in a collection at slippy max box level
            # prefix=str(OUTDIR),
            prefix=str(OUTDIR),
            href_prefix=HREF_PREFIX,
            storage_options=dict(auto_mkdir=True),
        ),
        template=template,
    )
    stac_items = collate(r.compute())

    # add the cog items to the collection
    for item in stac_items:
        collection.add_item(item, strategy=layout)

    # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    collection.summaries = Summaries({})

    # Add thumbnail
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://storage.googleapis.com/coclico-data-public/coclico/assets/thumbnails/"
            + COLLECTION_ID
            + ".png",  # noqa: E501,  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    if catalog.get_child(collection.id):
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")

    # add collection to catalog
    catalog.add_child(collection)

    # normalize the paths
    collection.normalize_hrefs(
        os.path.join(
            pathlib.Path(__file__).parent.parent.parent,
            STAC_DIR,
            metadata["TITLE_ABBREVIATION"],
        ),
        strategy=layout,
    )

    # save updated catalog
    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(pathlib.Path(__file__).parent.parent.parent, STAC_DIR),
        stac_io=DefaultStacIO(),
    )
    print("done")

# %%
