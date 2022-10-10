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
    # use these to reduce dimension, e.g., {ensemble: "mean", "time": [1995, 2020, 2100]}
    MAP_SELECTION_DIMS = {"time": [2100]}

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
    # would be overwhelmed by all options. So for the stac items that we generate for the frontend
    # visualizations a subset of the data is selected. Of course, this operation is dataset specific.
    for k, v in MAP_SELECTION_DIMS.items():
        if k in ds.dims and ds.coords:
            ds = ds.sel({k: v})
        else:
            try:
                # assume that coordinates with strings always have same dim name but with n
                ds = ds.sel({"n" + k: k == v})
            except:
                raise ValueError(f"Cannot find {k}")

    dimvals = get_dimension_values(ds, dimensions_to_ignore=["stations"])
    dimcombs = get_dimension_dot_product(dimvals)

    for var in VARIABLES:

        collection = get_geojson(
            ds, variable=var, dimension_combinations=dimcombs, stations_dim="stations"
        )

        # save feature collection as geojson in tempdir and upload to cloud
        with pathlib.Path.home().joinpath("data", "tmp") as outdir:
            # with tempfile.TemporaryDirectory() as outdir:

            # TODO: put this in a function because this is also used in generate_stace scripts?
            mapbox_url = get_mapbox_url(
                MAPBOX_PROJ, DATASET_FILENAME, var, add_mapbox_protocol=False
            )

            fn = mapbox_url.split(".")[1]

            fp = pathlib.Path(outdir, fn).with_suffix(".geojson")

            with open(fp, "w") as f:
                # load
                print(f"Writing data to {fp}")
                geojson.dump(collection, f)
            print("Done!")

            # Note, if mapbox cli raises en util collection error, this should be monkey
            # patched. Instructions are in documentation of the function.
            # geojson_to_mapbox(source_fpath=fp, mapbox_url=mapbox_url)
