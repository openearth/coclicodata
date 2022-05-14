import os
import pathlib
import warnings
from typing import Optional

from dotenv import load_dotenv
from google.cloud import storage

from . import abs_proj_path, proj, root


class CredentialLeakageWarning(Warning):
    pass


def load_env_variables(env_variables: Optional[list] = list()) -> None:
    env_fpath = abs_proj_path.joinpath(".env")
    if not env_fpath.exists():
        raise FileNotFoundError(
            "Processing data requires access keys for cloud services, which should be"
            f" stored as environment variables in .../{proj.joinpath('.env')}"
        )

    load_dotenv(env_fpath)
    for env_var in env_variables:
        if not env_var in os.environ:
            raise KeyError(f"{env_var} not in environmental variables.")
    print("Environmental variables loaded.")


def load_google_crededentials(token_fpath: pathlib.Path) -> None:
    #  TODO: Manage keys at user level, not with share drive
    warnings.warn("Keys loaded from shared network drive.", CredentialLeakageWarning)
    if not token_fpath.exists():
        if not root.exists():
            raise FileNotFoundError(
                "Deltares drive not found, mount drive to access Google keys."
            )
        raise FileNotFoundError("Credential file does not exist.")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(token_fpath)
    print("Google Application Credentials load into environment.")


if __name__ == "__main__":

    coclico_data_dir = pathlib.Path(root, "11205479-coclico", "data")
    load_env_variables(env_variables=["MAPBOX_TOKEN"])
    load_google_crededentials(coclico_data_dir.joinpath("google_credentials.json"))
