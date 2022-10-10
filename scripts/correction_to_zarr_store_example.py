import pathlib
import sys

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

import xarray as xr
from etl.cloud_services import dataset_from_google_cloud
from etl.extract import clear_zarr_information

if __name__ == "__main__":

    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    DATASET_FILENAME = "global_wave_energy_flux.zarr"

    # # read data from gcs zarr store
    # ds = dataset_from_google_cloud(
    #     bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    # )

    # read in from local iff available
    fpath = pathlib.Path.home().joinpath("data", "tmp", DATASET_FILENAME)
    ds = xr.open_zarr(fpath)

    # correction code comes here, for example:
    ds["time"] = ds["time"].astype(int)

    # remote old attrs
    ds = clear_zarr_information(ds)

    # first write to test file, when correct, mv to original path
    outpath = fpath.with_stem(fpath.stem + "_test")
    print(f"writing to {str(outpath)}")
    ds.to_zarr(outpath, mode="w")
    print("done")
