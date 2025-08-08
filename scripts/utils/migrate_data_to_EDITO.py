# %%
# written by Etienne Kras, 19-05-2025
# venv: edito_env
# This script migrates data from a local zarr store to the EDITO S3 storage
# sources: https://datalab.dive.edito.eu/account/storage and https://pub.pages.mercator-ocean.fr/edito-infra/edito-tutorials-content/#/zarr-netcdf-xarray-edito-data-storage

# import packages
from os import environ
import xarray as xr
from xarray import Dataset
import s3fs
import pathlib
import gcsfs
import os
from azure.storage.blob import BlobServiceClient

# import polars as pl

# %% define user and enable access to EDITO S3 storage (MiniO)
USERNAME = "project-coclico"

# intialize s3 filesystem and set environment variables
fs = s3fs.S3FileSystem(
    client_kwargs={"endpoint_url": "https://" + "minio.dive.edito.eu"},
    key=environ["EDITO_AWS_ACCESS_KEY_ID"],
    secret=environ["EDITO_AWS_SECRET_ACCESS_KEY"],
    token=environ["EDITO_AWS_SESSION_TOKEN"],
)

# %% Get data from Google bucket and write to EDITO S3 storage (MiniO) --> migrate bulk
#
# # Load google credentials and set bucket details
# GCS_PROJECT = "coclico-11207608-002"
# BUCKET_NAME = "coclico-data-public"
# BUCKET_PROJ = "coclico"
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
#     pathlib.Path("P:/").joinpath(
#         "11207608-coclico", "FASTTRACK_DATA", "google_credentials_new.json"
#     )
# )

# # intialize gcs filesystem and set environment variables
# gcs = gcsfs.GCSFileSystem(
#     gcs_project=GCS_PROJECT, token=os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
# )

# # List all files under the GCS folder
# # gcs_files = gcs.find(f"{BUCKET_NAME}/{BUCKET_PROJ}")  # recursive
# top_level_paths = gcs.ls(f"{BUCKET_NAME}/{BUCKET_PROJ}", detail=False)

# # Only keep directories
# folders = [p for p in top_level_paths if gcs.isdir(p)]

# for gcs_path in folders[1:]:  # skip the base directory on position 0

#     if "coclico-stac" in gcs_path:  # skip stacs
#         continue

#     if "assets" in gcs_path:  # skip thumbnails
#         continue

#     print(f"Copying: {gcs_path}")

#     all_files = gcs.find(gcs_path) # recursive

#     for gcs_file_path in all_files:
#         if gcs.isdir(gcs_file_path):
#             continue  # skip directories, just in case

#         # Step 3: Calculate relative path (inside this folder)
#         relative_path = gcs_file_path.replace(gcs_path, "")

#         # Compose final destination path in S3
#         s3_path = f"{USERNAME}{gcs_path.replace(f'{BUCKET_NAME}/{BUCKET_PROJ}', '')}{relative_path}"

#         print(f"📤 Copying: {gcs_file_path} → {s3_path}")

#         # Stream copy file in chunks
#         with gcs.open(gcs_file_path, "rb") as src:
#             with fs.open(s3_path, "wb") as dst:
#                 for chunk in iter(lambda: src.read(1024 * 1024), b""):
#                     dst.write(chunk)

# %% Get data from Microsoft Azure and write to EDITO S3 storage (MiniO) --> migrate bulk

# Load azure credentials and set bucket details
AZURE_STORAGE_ACCOUNT = "coclico"  # AZURE_CONTAINER
containers_to_export = [
    "gcts",
    "coastal-grid",
    "deltares-delta-dtm",
    "edito",
]  # containers to export, note edito includes projections and typology

# intialize Azure filesystem and set container client
account_url = f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net"
blob_service = BlobServiceClient(
    account_url=account_url, credential=os.environ["AZURE_STORAGE_SAS_TOKEN"]
)

# Loop over specified containers
for container_name in containers_to_export:
    print(f"\n Processing container: {container_name}")
    container_client = blob_service.get_container_client(container_name)

    # TODO: check for container / blob existence and skip if present

    try:
        # List blobs in the container
        blobs = container_client.list_blobs()

        for blob in blobs:
            blob_name = blob.name

            # Build S3 path
            s3_path = f"{USERNAME}/{container_name}/{blob_name}"

            print(f"Copying: {container_name}/{blob_name} → s3://{s3_path}")

            # Download blob and stream to S3
            azure_blob_client = container_client.get_blob_client(blob_name)
            downloader = azure_blob_client.download_blob()
            stream = downloader.chunks()

            with fs.open(s3_path, "wb") as s3_file:
                for chunk in stream:
                    s3_file.write(chunk)

    except Exception as e:
        print(f"Error processing container '{container_name}': {e}")

# %% general example
# dataset: Dataset = (
#     ...
# )  # a dataset containing values of a variable my_var over dimensions x and y
# x_chunk: int = ...  # maximum number of value in each chunk over dimension x
# y_chunk: int = ...  # maximum number of value in each chunk over dimension y
# encoding = {"my_var": {"chunks": (x_chunk, y_chunk)}}

# %% Zarr files --> migrate single file
#
# # define local drives
# coclico_data_dir = pathlib.Path("P:/").joinpath(
#     "11207608-coclico",
#     "FULLTRACK_DATA",
#     "WP3",
#     "data",
#     "NetCDF_MarineDynamicsUpdate",  # "NetCDF_MarineDynamicsChanges_TWL"
# )

# # set dataset name and output name
# dataset_name = "CTP_MarineClimatologies"  # "CTP_ReturnPeriods_SLR"
# dataset_name_out = "drivers_twl.zarr"  # "twl_SLR.zarr"

# # open dataset
# dataset = xr.open_zarr(coclico_data_dir.joinpath("%s.zarr" % (dataset_name)))

# # write output to my files in EDITO's S3 storage
# out_store = s3fs.S3Map(root=f"%s/%s" % (USERNAME, dataset_name_out), s3=fs, create=True)
# dataset.to_zarr(store=out_store, consolidated=True, mode="w")  # encoding=encoding)

# # testing written output
# test = xr.open_dataset(
#     "https://minio.dive.edito.eu/%s/%s" % (USERNAME, dataset_name_out), engine="zarr"
# )

# %% TODO: Parquet files --> migrate single file


# %% TODO: CoG files --> migrate single file


# %% TODO: NetCDF files --> migrate single file
# see https://pub.pages.mercator-ocean.fr/edito-infra/edito-tutorials-content/#/writing-data-on-the-fly-to-edito-data-storage?id=uploading-netcdf-files
