# %%
# written by Etienne Kras, 19-05-2025
# This script migrates data from a local zarr store to the EDITO S3 storage
# sources: https://datalab.dive.edito.eu/account/storage and https://pub.pages.mercator-ocean.fr/edito-infra/edito-tutorials-content/#/zarr-netcdf-xarray-edito-data-storage

# import packages
from os import environ
import xarray as xr
from xarray import Dataset
import s3fs
import pathlib

# import polars as pl

# %%
# define user
USERNAME = "project-coclico"

# set environment variables
fs = s3fs.S3FileSystem(
    client_kwargs={"endpoint_url": "https://" + "minio.dive.edito.eu"},
    key=environ["EDITO_AWS_ACCESS_KEY_ID"],
    secret=environ["EDITO_AWS_SECRET_ACCESS_KEY"],
    token=environ["EDITO_AWS_SESSION_TOKEN"],
)

# define (local and) remote drives
coclico_data_dir = pathlib.Path("P:/").joinpath(
    "11207608-coclico",
    "FULLTRACK_DATA",
    "WP3",
    "data",
    "NetCDF_MarineDynamicsChanges_TWL",
)
# TODO: get data from Google bucket and write to EDITO S3 storage (MiniO)

# %% general example
# dataset: Dataset = (
#     ...
# )  # a dataset containing values of a variable my_var over dimensions x and y
# x_chunk: int = ...  # maximum number of value in each chunk over dimension x
# y_chunk: int = ...  # maximum number of value in each chunk over dimension y
# encoding = {"my_var": {"chunks": (x_chunk, y_chunk)}}

# %% Zarr files
dataset_name = "CTP_ReturnPeriods_SLR"
dataset = xr.open_zarr(coclico_data_dir.joinpath("%s.zarr" % (dataset_name)))

# write output to my files in EDITO's S3 storage
out_store = s3fs.S3Map(
    root=f"%s/%s.zarr" % (USERNAME, dataset_name), s3=fs, create=True
)
dataset.to_zarr(store=out_store, consolidated=True, mode="w")  # encoding=encoding)

# testing written output
test = xr.open_dataset(
    "https://minio.dive.edito.eu/%s/%s.zarr" % (USERNAME, dataset_name), engine="zarr"
)

# %% Parquet files
# ??

# %% CoG files
# ??

# %% NetCDF files
# see https://pub.pages.mercator-ocean.fr/edito-infra/edito-tutorials-content/#/writing-data-on-the-fly-to-edito-data-storage?id=uploading-netcdf-files
