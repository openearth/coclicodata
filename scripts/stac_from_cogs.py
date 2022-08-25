from __future__ import annotations

import datetime
import itertools
import operator
import os
import pathlib
from typing import List, Mapping, Optional

import datacube
import fsspec
import numpy as np
import pandas as pd
import pystac
import rasterio.warp
import shapely.geometry
import xarray as xr
from datacube.utils.cog import write_cog
from etl import p_drive


def write_block(
    block: xr.DataArray,
    prefix: str = "",
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

    # cogs will be stored in a dirs per timestep, but opening file fails if this dir not exists.
    pathlib.Path(blob_name).parent.mkdir(parents=True, exist_ok=True)

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

    result = (
        block.isel(**{k: slice(1) for k in block.dims}).astype(object).compute().copy()
    )
    template_item = pystac.Item("id", None, None, datetime.datetime(2000, 1, 1), {})
    item = itemize(
        block, template_item, nbytes=nbytes, x_dim=x_dim, y_dim=y_dim, prefix=prefix
    )

    result[(0,) * block.ndim] = item
    return result


def itemize(
    block,
    item: pystac.Item,
    nbytes: int,
    *,
    asset_roles: list[str] | None = None,
    asset_media_type=pystac.MediaType.COG,
    prefix: str = "",
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

    item.id = name_block(block, include_band=False, x_dim=x_dim, y_dim=y_dim)
    item.geometry = geometry
    item.bbox = bbox
    item.datetime = pd.Timestamp(block.coords[time_dim][0].item()).to_pydatetime()

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
        href=name_block(block, x_dim=x_dim, y_dim=y_dim, prefix=prefix),
        media_type=asset_media_type,
        roles=roles,
    )
    asset.extra_fields["file:size"] = nbytes
    item.add_asset(block.name, asset)

    return item


def make_template(data: xr.DataArray) -> List[pystac.Item]:
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
    items2 = items.data.ravel().tolist()

    new_items = []
    key = operator.attrgetter("id")

    # group by id.
    for _, group in itertools.groupby(sorted(items2, key=key), key=key):
        items = list(group)
        item = items[0].clone()
        new_items.append(item)
        for other_item in items:
            other_item = other_item.clone()
            for k, asset in other_item.assets.items():
                item.add_asset(k, asset)
    return new_items
