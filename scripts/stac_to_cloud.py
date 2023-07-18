import pathlib
import sys

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from etl.cloud_services import dir_to_google_cloud
from etl.keys import load_google_credentials
from etl import p_drive, rel_root

if __name__ == "__main__":
    # hard-coded input params
    GCS_PROJECT = "DGDS - I1000482-002"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    STAC_NAME = "coclico-stac"
    IN_DIRNAME = "current"

    # hard-coded input params at project level
    coclico_data_dir = pathlib.Path(p_drive, "11205479-coclico", "FASTTRACK_DATA")

    # upload dir to gcs from local drive
    source_dir_fp = str(rel_root.joinpath(IN_DIRNAME))

    load_google_credentials(
        google_token_fp=coclico_data_dir.joinpath("google_credentials.json")
    )

    dir_to_google_cloud(
        dir_path=source_dir_fp,
        gcs_project=GCS_PROJECT,
        bucket_name=BUCKET_NAME,
        bucket_proj=BUCKET_PROJ,
        dir_name=STAC_NAME,
    )
