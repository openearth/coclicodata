import os
import pathlib
import subprocess
import tempfile
from itertools import product

import gcsfs
import geojson
import xarray as xr
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
)

from etl import p_drive
from etl.extract import clear_zarr_information, get_geojson
from etl.keys import load_env_variables, load_google_credentials


def _validate_fpath(*args: pathlib.Path) -> None:

    for fpath in args:
        if not isinstance(fpath, pathlib.Path):
            raise TypeError(
                f"Argument should be of type pathlib.Path, not {type(fpath)}."
            )

        if not fpath.exists():
            raise FileNotFoundError(f"{fpath} does not exist.")


def dataset_to_google_cloud(ds, gcs_project, bucket_name, bucket_proj, zarr_filename):
    """Upload zarr store to Google Cloud Services

    # TODO: fails when uploading to store that already exists

    """

    if isinstance(ds, pathlib.Path):
        _validate_fpath(ds.parent, ds)

        #  TODO: append to cloud zarr store from Dask chunks in parallel
        ds = xr.open_zarr(ds)

        # zarr tries to double encode some information
        ds = clear_zarr_information(ds)

    # file system interface for google cloud storage
    fs = gcsfs.GCSFileSystem(
        gcs_project, token=os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    )

    target_path = os.path.join(bucket_name, bucket_proj, zarr_filename)

    gcsmap = gcsfs.mapping.GCSMap(target_path, gcs=fs)

    print(f"Writing to zarr store at {target_path}...")
    try:
        ds.to_zarr(store=gcsmap, mode="w")
        print("Done!")
    except OSError as e:
        print(f"Failed uploading: \n {e}")


def dataset_from_google_cloud(bucket_name, bucket_proj, zarr_filename):
    uri = os.path.join("gs://" + bucket_name, bucket_proj, zarr_filename)
    return xr.open_zarr(uri)


def geojson_to_mapbox(source_fpath: pathlib.Path, mapbox_url: str) -> None:
    """Upload GeoJSON to Mapbox by CLI.

    Mapbox Python SDK recommends to use Mapbox Python CLI, but CLI seems outdated.

    # TODO: make PR at mapbox gh?
    Installing Mapbox CLI in Python 3.10 raises 'Cannot import mapping from collection.'
    This can be resolved by patching the following in the Mapbox package:

    from collections import Mapping

    to

    from collections.abc import Mapping

    Note 18/8/2022: monkey patch is still required for mapboxcli package. This package
    is also not available on conda-forge and was installed with pip.

    """

    if not source_fpath.exists():
        raise FileNotFoundError(f": {source_fpath} not found.")

    print(f"uploading {source_fpath} to {mapbox_url}")

    mapbox_cmd = r"mapbox --access-token {} upload {} {}".format(
        os.environ.get("MAPBOX_ACCESS_TOKEN", ""), mapbox_url, str(source_fpath)
    )
    # TODO: check if subprocess has to be run with check=True
    subprocess.run(mapbox_cmd, shell=True)


if __name__ == "__main__":

    # hard-coded input params
    DATASET_FILENAME = "CoastAlRisk_Europe_EESSL.zarr"
    GCS_PROJECT = "DGDS - I1000482-002"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"

    # semi hard-coded variables including both local and remote drives
    coclico_data_dir = pathlib.Path(p_drive, "11205479-coclico", "data")
    network_dir = coclico_data_dir.joinpath("06_adaptation_jrc")
    local_dir = pathlib.Path.home().joinpath("ddata", "temp")

    # TODO: safe cloud creds in password client
    load_env_variables(env_var_keys=["MAPBOX_ACCESS_TOKEN"])
    load_google_credentials(
        google_token=coclico_data_dir.joinpath("google_credentials.json")
    )

    # upload data to cloud from local drive
    source_data_fp = local_dir.joinpath(DATASET_FILENAME)

    # dataset_to_google_cloud(
    #     ds=source_data_fp,
    #     gcs_project=GCS_PROJECT,
    #     bucket_name=BUCKET_NAME,
    #     bucket_proj=BUCKET_PROJ,
    #     zarr_filename="test.zarr",
    # )

    # commented code is here to provide an example of how this file can be used as a script to
    # interact with cloud services.
    #
    # # read data from cloud
    # ds = dataset_from_google_cloud(
    #     bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    # )
