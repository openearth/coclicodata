import os
import pathlib
import warnings
from typing import Optional, Union

from dotenv import load_dotenv
from google.cloud import storage

from etl import p_drive, rel_root


class CredentialLeakageWarning(Warning):
    pass


def load_env_variables(env_var_keys: list = list()) -> None:
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


def load_google_credentials(google_token_fp: Union[pathlib.Path, None] = None) -> None:

    if google_token_fp:
        #  TODO: Manage keys at user level, not with shared drive. The code block below
        # should tested by Windows users to see if gcloud credentials behave similar on
        # that os. If so, the code block below can be used instead.
        warnings.warn(
            "Keys loaded from shared network drive.", CredentialLeakageWarning
        )
        if not google_token_fp.exists():
            if not p_drive.exists():
                raise FileNotFoundError(
                    "Deltares drive not found, mount drive to access Google keys."
                )
            raise FileNotFoundError("Credential file does not exist.")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(google_token_fp)
        print("Google Application Credentials load into environment.")

    else:
        #  TODO: Migrate to token=None in gcsfs when bug that no credentials can be found is fixed.
        gmail_pattern = "*@gmail.com"
        p = pathlib.Path.home().joinpath(
            ".config", "gcloud", "legacy_credentials", gmail_pattern, "adc.json"
        )
        p = list(p.parent.parent.expanduser().glob(p.parent.name))[0].joinpath(p.name)
        if not p.exists():
            raise FileNotFoundError("Google credentials not found.")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(p)
        print("Google Application Credentials load into environment.")


if __name__ == "__main__":

    coclico_data_dir = pathlib.Path(p_drive, "11205479-coclico", "data")
    load_env_variables(env_var_keys=["MAPBOX_TOKEN"])
    load_google_credentials(coclico_data_dir.joinpath("google_credentials.json"))
