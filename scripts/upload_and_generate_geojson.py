import pathlib
import sys
from importlib.resources import path

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

import geojson
import xarray as xr
from etl import p_drive
from etl.cloud_services import dataset_to_google_cloud, dataset_from_google_cloud, geojson_to_mapbox
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
    GCS_PROJECT = "DGDS - I1000482-002"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"

    # hard-coded input params at project level
    coclico_data_dir = pathlib.Path(p_drive, "11205479-coclico", "data")
    dataset_dir = coclico_data_dir.joinpath("01_storm_surge_jrc")
    IN_FILENAME = "CoastAlRisk_Europe_EESSL.zarr" # original filename as on P drive
    OUT_FILENAME = "europe_storm_surge_level.zarr" # file name in the cloud and on MapBox
    VARIABLES = ["ssl"]
    ADDITIONAL_DIMENSIONS = [
        "rp",
        "nscenarios",
    ]
    # use these to reduce dimension, e.g., {ensemble: "mean", "time": [1995, 2020, 2100]}
    MAP_SELECTION_DIMS = {"nscenarios": [0, 1, 2], "rp": [5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0]}

    # TODO: safe cloud creds in password client 
    load_env_variables(env_var_keys=["MAPBOX_ACCESS_TOKEN"])
    load_google_credentials(
        google_token_fp=coclico_data_dir.joinpath("google_credentials.json")
    )

    # TODO: come up with checks for zarr data

    # upload data to gcs from local drive
    source_data_fp = dataset_dir.joinpath(IN_FILENAME)

    dataset_to_google_cloud(
        ds=source_data_fp,
        gcs_project=GCS_PROJECT,
        bucket_name=BUCKET_NAME,
        bucket_proj=BUCKET_PROJ,
        zarr_filename=OUT_FILENAME,
    )

    # read data from gcs 
    ds = dataset_from_google_cloud(
        bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=OUT_FILENAME
    )

    # # read data from local source
    # fpath = pathlib.Path.home().joinpath(
    #     "data", "tmp", "shoreline_change_projections.zarr"
    # )
    # ds = xr.open_zarr(fpath)

    ds = zero_terminated_bytes_as_str(ds)

    # remove characters that cause problems in the frontend.

    ds = rm_special_characters(
        ds=ds, dimensions_to_check=ADDITIONAL_DIMENSIONS, characters=["%"]
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
        with dataset_dir.joinpath("platform") as outdir:
            # with tempfile.TemporaryDirectory() as outdir:

            # TODO: put this in a function because this is also used in generate_stac scripts?
            mapbox_url = get_mapbox_url(
                MAPBOX_PROJ, OUT_FILENAME, var, add_mapbox_protocol=False
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
            geojson_to_mapbox(source_fpath=fp, mapbox_url=mapbox_url)
