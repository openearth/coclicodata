# %%
import pathlib
import sys
import pystac
import pystac_client
import os

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from coclicodata.etl.cloud_utils import dir_to_google_cloud, load_google_credentials
from coclicodata.drive_config import p_drive

if __name__ == "__main__":
    # hard-coded input params
    GCS_PROJECT = "coclico-11207608-002"
    BUCKET_NAME = "coclico-data-public"
    BUCKET_PROJ = "coclico"
    STAC_NAME = "coclico-stac-4oct"  # NOTE: if working from main STAC_NAME = 'coclico-stac', if working from branch STAC_NAME = coclico-stac-***
    IN_DIRNAME = "current"

    # hard-coded input params at project level
    cred_data_dir = p_drive.joinpath("11207608-coclico", "FASTTRACK_DATA")

    # upload dir to gcs from local drive
    source_dir_fp = str(
        pathlib.Path(__file__).parent.parent.parent.joinpath(IN_DIRNAME)
    )

    # load google credentials
    load_google_credentials(
        google_token_fp=cred_data_dir.joinpath("google_credentials_new.json")
    )

    # validate STAC catalog and upload to cloud
    catalog = pystac_client.Client.open(
        os.path.join(source_dir_fp, "catalog.json")  # local cloned STAC
    )

    ## NOTE: no need to validate whole catalog,
    # if (
    #     catalog.validate_all() == None
    # ):  # no valid STAC (note, pystac >1.10 and jsonschema >4.20)
    #     print(
    #         "STAC is not valid and hence not uploaded to cloud, please adjust"
    #         " accordingly by debugging the STAC catalog."
    #     )
    # else:
    dir_to_google_cloud(
        dir_path=source_dir_fp,
        gcs_project=GCS_PROJECT,
        bucket_name=BUCKET_NAME,
        bucket_proj=BUCKET_PROJ,
        dir_name=STAC_NAME,
    )

# %%
