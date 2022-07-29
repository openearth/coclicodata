import geojson
import numpy as np
import rioxarray as rioxarray
import xarray as xr
from stac.utils import get_mapbox_item_id


def zero_terminated_bytes_as_str(ds: xr.Dataset) -> xr.Dataset:
    """Load zero-terminated bytes as strings

    To be CF compliant the coordinates of dtype string are stored as zero-terminated bytes. This
    function loads those bytes back to strings.

    Args:
        ds (xr.Dataset): Xarray dataset

    Returns:
        xr.Dataset: Xarray dataset
    """
    for coord in list(ds.coords):
        if np.issubdtype(ds[coord].values.dtype, np.dtype("S")):
            ds[coord] = ds[coord].values.astype(str)
    return ds


def clear_zarr_information(ds):
    """Zarr is inserting VLenUTF8 as a filter, but the loaded data array already has
    that as a filter so it's trying to double encode, see (https://github.com/pydata/xarray/issues/3476)
    """
    for v in list(ds.coords.keys()):
        if ds.coords[v].dtype == object:
            ds.coords[v] = ds.coords[v].astype("unicode")

    for v in list(ds.variables.keys()):
        if ds[v].dtype == object:
            ds[v] = ds[v].astype("unicode")

    return ds


def get_point_feature(idx, lon, lat):
    point = geojson.Point([lon, lat])
    feature = geojson.Feature(geometry=point)
    feature["properties"]["locationId"] = idx
    return feature


def get_geojson(ds, variable, dimension_combinations):

    da = ds[variable]
    instance_dim = list(set(da.dims) - set(dimension_combinations[0].keys()))[0]

    lons = da["longitude"].values.tolist()
    lats = da["latitude"].values.tolist()
    idxs = da[instance_dim].values.tolist()

    # create geojson features from lists of lons, lats and instance indices
    features = list(
        map(lambda lon, lat, idx: get_point_feature(idx, lon, lat), lons, lats, idxs)
    )

    # add variable values per mapbox layer to the geojson properties
    for dimdict in dimension_combinations:
        mapbox_layer_id = get_mapbox_item_id(dimdict)
        vals = da.sel(dimdict).values.tolist()
        for feature, value in zip(features, vals):
            feature["properties"][mapbox_layer_id] = value

    return geojson.FeatureCollection(features)
