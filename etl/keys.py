import os
import pathlib
import warnings
from typing import Optional

from dotenv import load_dotenv
from google.cloud import storage

from etl import p_drive, rel_root


class CredentialLeakageWarning(Warning):
    pass


def load_env_variables(env_var_keys: Optional[list] = list()) -> None:
    env_fpath = rel_root.joinpath(".env")
    if not env_fpath.exists():
        raise FileNotFoundError(
            "Processing data requires access keys for cloud services, which should be"
            f" stored as environment variables in .../{rel_root.joinpath('.env')}"
        )

    load_dotenv(env_fpath)
    for env_var in env_var_keys:
        if not env_var in os.environ:
            raise KeyError(f"{env_var} not in environmental variables.")
    print("Environmental variables loaded.")


def load_google_credentials(google_token: pathlib.Path) -> None:
    #  TODO: Manage keys at user level, not with shared drive
    warnings.warn("Keys loaded from shared network drive.", CredentialLeakageWarning)
    if not google_token.exists():
        if not p_drive.exists():
            raise FileNotFoundError(
                "Deltares drive not found, mount drive to access Google keys."
            )
        raise FileNotFoundError("Credential file does not exist.")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(google_token)
    print("Google Application Credentials load into environment.")


if __name__ == "__main__":

    coclico_data_dir = pathlib.Path(p_drive, "11205479-coclico", "data")
    load_env_variables(env_var_keys=["MAPBOX_TOKEN"])
    load_google_credentials(coclico_data_dir.joinpath("google_credentials.json"))
