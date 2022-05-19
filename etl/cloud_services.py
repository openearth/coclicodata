import os
import pathlib
from itertools import product

import gcsfs
import geojson
import xarray as xr
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable

from etl import p_drive
from etl.keys import load_env_variables, load_google_credentials


def _validate_fpath(*args: pathlib.Path) -> None:

    for fpath in args:
        if not isinstance(fpath, pathlib.Path):
            raise TypeError(
                f"Argument should be of type pathlib.Path, not {type(fpath)}."
            )

        if not fpath.exists():
            raise FileNotFoundError(f"{fpath} does not exist.")


def dataset_to_google_cloud(ds, gcs_project, bucket_name, root_path, zarr_name):

    if isinstance(ds, pathlib.Path):
        _validate_fpath(ds.parent, ds)

        #  TODO: append to cloud zarr store from Dask chunks in parallel
        ds = xr.open_zarr(ds)

        # zarr ignores xr encoding when xr open zarr (https://github.com/pydata/xarray/issues/3476)
        for v in list(ds.coords.keys()):
            if ds.coords[v].dtype == object:
                ds.coords[v] = ds.coords[v].astype("unicode")

        for v in list(ds.variables.keys()):
            if ds[v].dtype == object:
                ds[v] = ds[v].astype("unicode")

    # file system interface for google cloud storage
    fs = gcsfs.GCSFileSystem(
        gcs_project, token=os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    )

    target_path = os.path.join(bucket_name, root_path, zarr_name)

    gcsmap = gcsfs.mapping.GCSMap(target_path, gcs=fs)

    print(f"Copying zarr data to {target_path}...")
    ds.to_zarr(store=gcsmap, mode="w")
    print("Done!")


def dataset_from_google_cloud(bucket_name, root_path, zarr_store):
    uri = os.path.join("gs://" + bucket_name, root_path, zarr_store)
    return xr.open_zarr(uri)


def mapbox_vars():
    pass


def get_dimdict(ds, var):

    arr = ds[var]

    # TODO: make function dictionary when list of coclico cf conventions are decided
    if var == "stations":

        dimdict = {
            "type": "stations",
            "extent": [int(arr.values.min()), int(arr.values.max())],
            "unit": "-",
        }

    else:
        dimdict = {
            "type": "temporal",
            "values": arr.values.tolist(),
            "unit": arr.attrs.get("units", "-"),
        }

    return dimdict


def get_cube_dimensions(ds, variable) -> dict:

    dims_ = list(ds[variable].dims)

    # keep only vars that have matching dim with dim shape 1
    # TODO: make list of valid names when coclico cf_conventions are decided
    # vars_ = list(ds.variables)
    # vars_ = [x for x in vars_ if x in dims_]
    # vars_ = [x for x in vars_ if len(ds[x].dims) == 1]
    # vars_.append("stations")

    # TODO: dynamic, not hard coded.
    vars_ = ["scenario", "RP", "stations"]

    cube_dims = {}
    for var in vars_:
        dimdict = get_dimdict(ds, var)
        dim = Dimension.from_dict(dimdict)
        cube_dims[var] = dim
    return cube_dims


def get_stac_summary_keys(dimension_combinations):
    dict_as_str = [f"{k}-{v}" for k, v in dimension_combinations.items()]
    return "-".join(dict_as_str)


def get_dimension_combinations(cube_dimensions):
    """TODO: document this function."""

    # unnest dimension values
    dimvals = {k: v.values for k, v in cube_dimensions.items() if v.values}

    # get possible dimension combinations by taking the dot product:
    dimcombs = list(product(*dimvals.values()))

    # store dimcombs in dictionary to keep track of dimension name, e.g,:
    # [{"scenario": "Historical", "RP": 5.0}, ..., {"scenario": "RCP85", "RP": 500}]
    dimcombs = [dict(zip(dimvals.keys(), i)) for i in dimcombs]

    return dimcombs


def get_geojson(ds, variable, dimension_combinations):
    def get_point_feature(idx, lon, lat):
        point = geojson.Point([lon, lat])
        feature = geojson.Feature(geometry=point)
        feature["properties"]["locationId"] = idx

        # TODO: Check with Etienne if the variable values have to be stored in geojson
        # hopefully not, because the files will become very large. However, if they need to
        # be stored we could do it something like this:
        stac_keys = [get_stac_summary_keys(i) for i in dimension_combinations]
        for stac_key, dimension_indices in zip(stac_keys, dimension_combinations):
            # Wrong type to assign geojson property iff extracted without .flatten()[0]
            value = ds.sel(dimension_indices)[variable].values.flatten()[0]
            feature["properties"][stac_key] = value

        return feature

    def get_polygon_feature(idx, geometry):
        raise NotImplementedError(": not implemented yet. ")

    lons = ds["longitude"].values
    lats = ds["latitude"].values
    idxs = range(len(lons))

    features = list(
        map(lambda lon, lat, idx: get_point_feature(idx, lon, lat), lons, lats, idxs)
    )

    return features

    #
    #     for a, b in zip(
    #         ds.sel({"stations": j})["%s" % variable].values.flatten(), keys
    #     ):  # flattened along dimensions
    #         feature["properties"][b] = a

    #     features.append(feature)
    return features


if __name__ == "__main__":

    # coclico_data_dir = pathlib.Path(p_drive, "11205479-coclico", "data")

    # load_env_variables(env_var_keys=["MAPBOX_TOKEN"])
    # load_google_credentials(
    #     google_token=coclico_data_dir.joinpath("google_credentials.json")
    # )

    # network_dir = coclico_data_dir.joinpath("06_adaptation_jrc")
    # zarr_dir = "cost_and_benefits_of_coastal_adaptation.zarr"
    # dataset_path = network_dir.joinpath(zarr_dir)

    # dataset_to_google_cloud(
    #     ds=dataset_path,
    #     gcs_project="DGDS - I1000482-002",
    #     bucket_name="dgds-data-public",
    #     root_path="coclico",
    #     zarr_name=zarr_dir,
    # )

    bucket_name = "dgds-data-public"
    root_path = "coclico"
    zarr_name = "cost_and_benefits_of_coastal_adaptation.zarr"
    zarr_name = "CoastAlRisk_Europe_EESSL.zarr"
    ds = dataset_from_google_cloud(
        bucket_name=bucket_name, root_path=root_path, zarr_store=zarr_name
    )

    cube_dimensions = get_cube_dimensions(ds, variable="ssl")
    dimension_combinations = get_dimension_combinations(cube_dimensions=cube_dimensions)
    stac_key_dict = [get_stac_summary_keys(i) for i in dimension_combinations]
    features = get_geojson(
        ds, variable="ssl", dimension_combinations=dimension_combinations
    )
    features
