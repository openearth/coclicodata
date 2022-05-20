import os
import pathlib
import subprocess
import tempfile
from itertools import product

import gcsfs
import geojson
import xarray as xr
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable

from etl import p_drive
from etl.extract import get_geojson
from etl.keys import load_env_variables, load_google_credentials
from etl.stac_utils import (
    get_cube_dimensions,
    get_dimension_combinations,
    get_stac_summary_keys,
)


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


def geojson_to_mapbox(fpath: pathlib.Path, mapbox_name: str) -> None:
    """Upload geojson to mapbox.

    Mapbox Python SDK recommends to use Mapbox Python CLI. However, this cli seems
    to be outdated.

    Installing the package in a python 3.10 environment raises 'Cannot import mapping
    from collection. This can be fixed by changing in the mapbox package:

    from collections import Mapping

    to

    from collections.abc import Mapping

    """

    if not fpath.exists():
        raise FileNotFoundError(f": {fpath} not found.")

    uri = f"global-data-viewer.{mapbox_name}"

    print(f"uploading {fpath} to {uri}")

    # subprocess.run(
    #     [
    #         "mapbox",
    #         "--access-token",
    #         os.environ["MAPBOX_ACCESS_TOKEN"],
    #         "upload",
    #         uri,
    #         str(fpath),
    #     ],
    #     shell=True,
    #     check=True,
    # )

    mapbox_cmd = r"mapbox --access-token {} upload {} {}".format(
        os.environ.get("MAPBOX_ACCESS_TOKEN", ""), uri, str(fpath)
    )
    print(mapbox_cmd)
    subprocess.run(mapbox_cmd, shell=True)


if __name__ == "__main__":

    coclico_data_dir = pathlib.Path(p_drive, "11205479-coclico", "data")

    load_env_variables(env_var_keys=["MAPBOX_ACCESS_TOKEN"])
    load_google_credentials(
        google_token=coclico_data_dir.joinpath("google_credentials.json")
    )

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
    collection = get_geojson(
        ds, variable="ssl", dimension_combinations=dimension_combinations
    )

    with tempfile.TemporaryDirectory() as tempdir:

        fpath = pathlib.Path(tempdir, "data.geojson")

        with open(fpath, "w") as f:
            geojson.dump(collection, f)

        geojson_to_mapbox(fpath=fpath, mapbox_name="testregion")
