import os
import pathlib
import sys
import tempfile
from importlib.resources import path
from typing import List

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

import geojson
import geopandas as gpd
import xarray as xr
from etl import p_drive, rel_root
from etl.cloud_services import dataset_from_google_cloud, geojson_to_mapbox
from etl.extract import (
    clear_zarr_information,
    get_geojson,
    get_mapbox_url,
    zero_terminated_bytes_as_str,
)
from etl.keys import load_env_variables, load_google_credentials
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
    rm_special_characters,
)

if __name__ == "__main__":
    # hard-coded input params
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"

    # hard-coded input params at project level
    DATASET_FILENAME = "shoreline_change_projections.zarr"
    VARIABLES = ["sc"]
    ADDITIONAL_DIMENSIONS = [
        "ensemble",
        "scenarios",
    ]

    load_env_variables(env_var_keys=["MAPBOX_ACCESS_TOKEN"])

    # # read data from gcs zarr store
    # ds = dataset_from_google_cloud(
    #     bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    # )

    import xarray as xr

    fpath = pathlib.Path.home().joinpath(
        "data", "tmp", "shoreline_change_projections.zarr"
    )
    ds = xr.open_zarr(fpath)

    ds = zero_terminated_bytes_as_str(ds)

    # remove characters that cause problems in the frontend.
    ds = rm_special_characters(
        ds, dimensions_to_check=ADDITIONAL_DIMENSIONS, characters=["%"]
    )

    # This dataset has quite some dimensions, so if we would parse all information the end-user
    # would be overwhelmed by all options. So we select a subset of the data. This option is of
    # course dataset specific.
    if "time" in ds:
        ds = ds.sel({"time": 2100})
    # if "ensemble" in ds:
    #     # TODO: ens filter that works for both '50%' and 'mean'
    #     # ds = ds.sel({"nensemble": "ensemble" == "mean"})
    #     ds = ds.sel({"nensemble": "ensemble" == "50%"})

    dimvals = get_dimension_values(ds, dimensions_to_ignore=["stations"])
    dimcombs = get_dimension_dot_product(dimvals)

    for var in VARIABLES:

        collection = get_geojson(
            ds, variable=var, dimension_combinations=dimcombs, stations_dim="stations"
        )

        # save feature collection as geojson in tempdir and upload to cloud
        with tempfile.TemporaryDirectory() as tempdir:

            fp = pathlib.Path(tempdir, "data.geojson")

            with open(fp, "w") as f:
                # load
                geojson.dump(collection, f)

            # TODO: put this in a function because this is also used in generate_stace scripts?
            mapbox_url = get_mapbox_url(
                MAPBOX_PROJ, DATASET_FILENAME, var, add_mapbox_protocol=False
            )
            # Note, if mapbox cli raises en util collection error, this should be monkey
            # patched. Instructions are in documentation of the function.
            geojson_to_mapbox(source_fpath=fp, mapbox_url=mapbox_url)