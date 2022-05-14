import os
import pathlib

import gcsfs
import xarray as xr

from etl import root
from etl.keys import load_keys


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


if __name__ == "__main__":

    coclico_data_dir = pathlib.Path(root, "11205479-coclico", "data")

    load_keys(
        env_var_keys=["MAPBOX_TOKEN"],
        google_token=coclico_data_dir.joinpath("google_credentials.json"),
    )

    network_dir = coclico_data_dir.joinpath("06_adaptation_jrc")
    zarr_dir = "cost_and_benefits_of_coastal_adaptation.zarr"
    dataset_path = network_dir.joinpath(zarr_dir)

    dataset_to_google_cloud(
        ds=dataset_path,
        gcs_project="DGDS - I1000482-002",
        bucket_name="dgds-data-public",
        root_path="coclico",
        zarr_name=zarr_dir,
    )
