import os
import pathlib
import sys
import tempfile
from importlib.resources import path

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

import geojson
import geopandas as gpd
import xarray as xr
from etl import p_drive, rel_root
from etl.cloud_services import dataset_from_google_cloud, geojson_to_mapbox
from etl.extract import clear_zarr_information, get_geojson
from etl.keys import load_env_variables, load_google_credentials
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
)

if __name__ == "__main__":
    # hard-coded input params
    DATASET_FILENAME = "CoastAlRisk_Europe_EESSL.zarr"
    GCS_PROJECT = ("DGDS - I1000482-002",)
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_BASENAME = "mapbox://global-data-viewer"

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

    # read data
    ds = xr.open_zarr(source_data_fp)

    dimvals = get_dimension_values(ds, dimensions_to_ignore=["stations"])
    dimcombs = get_dimension_dot_product(dimvals)
    collection = get_geojson(ds, variable="ssl", dimension_combinations=dimcombs)

    # save feature collection as geojson in tempdir and upload to cloud
    with tempfile.TemporaryDirectory() as tempdir:

        fpath = pathlib.Path(tempdir, "data.geojson")

        with open(fpath, "w") as f:
            geojson.dump(collection, f)

        # TODO: put this in a function because this is also used in generate_stace scripts?
        mapbox_url = f"{MAPBOX_BASENAME}.{pathlib.Path(DATASET_FILENAME).stem}"
        geojson_to_mapbox(source_fpath=fpath, mapbox_url=mapbox_url)
