# %%
# written by Etienne Kras, 15-08-2025
# venv: edito_env
# This script migrates the CoCliCo STAC to the EDITO; adjusting the URLs and making an absolute catalog
# sources: https://pub.pages.mercator-ocean.fr/edito-infra/edito-tutorials-content/#/interactWithTheDataAPI?id=edito-data-catalog-api
# see STAC here: https://radiantearth.github.io/stac-browser/#/external/api.dive.edito.eu/data

# import packages
from pystac_client import Client
from pystac import Catalog, Link
import pystac
import copy
from pystac.stac_io import DefaultStacIO
import s3fs
import gcsfs
import click
from posixpath import join as urljoin
from os import environ
import os
import pathlib

# %% Hard-coded input params at project level
test = False  # set to True to create a small test catalog with only 3 collections, False for entire collection

# Google Cloud Storage (GCS) details
GCS_PROTOCOL = "https://storage.googleapis.com"
GCS_PROJECT = "coclico-11207608-002"
BUCKET_NAME = "coclico-data-public"
BUCKET_PROJ = "coclico"
STAC_NAME_ORIG = "coclico-stac"

# EDITO S3 storage details
EDITO_PROTOCOL = "https://minio.dive.edito.eu"
EDITO_PROJECT = "project-coclico"
STAC_NAME = "coclico-stac-edito"  # note, never put coclico-stac or the original stac will be overwritten

# %% Access CoCliCo catalog and set URLs

# set urls
OLD_BASE = f"{GCS_PROTOCOL}/{BUCKET_NAME}/{BUCKET_PROJ}"
NEW_BASE = f"{EDITO_PROTOCOL}/{EDITO_PROJECT}"
LOCAL_CATALOG_BASE = (
    f"{pathlib.Path.cwd().as_posix()}/current"  # local folder with coclico-stac
)

# Access the existing CoCliCo STAC catalog from GCS
# REMOTE_CATALOG_URL = f"{OLD_BASE}/coclico-stac/catalog.json"
# coclico_project_catalog = pystac.Catalog.from_file(
#     REMOTE_CATALOG_URL
# )  # SELF CONTAINED CATALOG
# coclico_project_catalog._stac_io.start_href = (
#     REMOTE_CATALOG_URL  # set start href to resolve relative links
# )

# Access the existing CoCliCo STAC catalog from local file
coclico_project_catalog = pystac.Catalog.from_file(
    f"{LOCAL_CATALOG_BASE}/catalog.json"
)  # SELF_CONTAINED CATALOG


# %% walk through catalog and update links in collections, items and assets

if test == True:
    # Create a new smaller catalog
    coclico_edito_catalog = Catalog(
        id="small-catalog",
        description="Subset catalog with 2 collections",
        title="Small Test Catalog",
    )

    # List the collection IDs you want to keep
    collections_to_keep = ["floodmaps", "cisi", "pp"]  # , "slp6"]

    # Copy the collections into the smaller catalog
    for collection_id in collections_to_keep:
        collection = coclico_project_catalog.get_child(collection_id)
        if collection is not None:
            coclico_edito_catalog.add_child(collection)
        else:
            print(f"Collection {collection_id} not found in the full catalog!")
else:
    # deepcopy the catalog to create a new one for EDITO
    coclico_edito_catalog = copy.deepcopy(coclico_project_catalog)

# iterate over all children (collections) and their items in the catalog
# replace asset hrefs with new urls, while item or collection self_href with local paths
for child in coclico_edito_catalog.get_children():  # top-level collections only
    print("Updating:", child.id)
    for asset in child.assets.values():  # update collection asset urls
        if asset.href.startswith(OLD_BASE):
            asset.href = asset.href.replace(OLD_BASE, NEW_BASE)
    for item in child.get_items():  # update item asset urls
        if item.self_href and item.self_href.startswith(
            LOCAL_CATALOG_BASE
        ):  # set href of items because normalize messes up the paths with remote / local catalogs
            item.set_self_href(
                item.self_href.replace(
                    LOCAL_CATALOG_BASE,
                    f"{NEW_BASE}/{STAC_NAME}",  # ".\edito_catalog_relative"
                )
            )
        link = item.get_single_link("collection")
        if link is not None and link.href.startswith(
            ".."
        ):  # replace automatic collection relative paths also with absolute ones
            collection = coclico_edito_catalog.get_child(item.collection_id)
            if collection is not None and collection.self_href is not None:
                item.remove_links("collection")
                abs_link = Link(
                    rel="collection",
                    target=collection.self_href.replace(
                        LOCAL_CATALOG_BASE, f"{NEW_BASE}/{STAC_NAME}"
                    ),
                    media_type="application/json",
                )
                item.add_link(abs_link)
        for asset in item.assets.values():
            if asset.href.startswith(OLD_BASE):
                asset.href = asset.href.replace(OLD_BASE, NEW_BASE)
    if child.self_href and child.self_href.startswith(
        LOCAL_CATALOG_BASE
    ):  # set href of collection because normalize messes up the paths with remote / local catalogs
        child.set_self_href(
            child.self_href.replace(
                LOCAL_CATALOG_BASE,
                f"{NEW_BASE}/{STAC_NAME}",  # ".\edito_catalog_relative"
            )
        )

coclico_edito_catalog.set_self_href(
    f"{NEW_BASE}/{STAC_NAME}/catalog.json"
)  # set self href of catalog

coclico_edito_catalog.catalog_type = (
    pystac.CatalogType.ABSOLUTE_PUBLISHED
)  # use absolute paths

# saving the catalog locally
stac_io = DefaultStacIO()  # define layout
coclico_edito_catalog.save(dest_href=f"./{STAC_NAME}", stac_io=stac_io)  # save

# # Save updated catalog locally, with hrefs to the S3 bucket
# # Note, doesnt work as normalize messes up the paths with remote / local catalogs
# stac_io = DefaultStacIO()  # define layout
# coclico_edito_catalog.normalize_and_save(
#     root_href=r".\edito_catalog",
#     catalog_type=pystac.CatalogType.ABSOLUTE_PUBLISHED,
# )

# coclico_edito_catalog.normalize_hrefs(
#     NEW_BASE + "/" + STAC_NAME
# )  # this gives a very weird folder structure in the EDITO STAC
# coclico_edito_catalog.catalog_type = (
#     pystac.CatalogType.ABSOLUTE_PUBLISHED
# )  # use absolute paths
# coclico_edito_catalog.save(dest_href="./edito_catalog", stac_io=stac_io)  # save

# %% upload to EDITO S3 storage

LOCAL_CATALOG_PATH = f"./{STAC_NAME}"  # folder with normalized catalog

# load intermediate catalog..
coclico_edito_catalog = pystac.Catalog.from_file(LOCAL_CATALOG_PATH + "/catalog.json")

# intialize s3 filesystem and set environment variables
fs = s3fs.S3FileSystem(
    client_kwargs={"endpoint_url": "https://" + "minio.dive.edito.eu"},
    key=environ["EDITO_AWS_ACCESS_KEY_ID"],
    secret=environ["EDITO_AWS_SECRET_ACCESS_KEY"],
    token=environ["EDITO_AWS_SESSION_TOKEN"],
)

# Upload catalog recursively using s3fs
for root, dirs, files in os.walk(LOCAL_CATALOG_PATH):
    for file in files:
        local_path = os.path.join(root, file)
        relative_path = os.path.relpath(local_path, LOCAL_CATALOG_PATH)
        s3_path = f"{EDITO_PROJECT}/{STAC_NAME}/{relative_path.replace(os.sep, '/')}"
        fs.put(local_path, s3_path)
        print(f"Uploaded {s3_path}")

# %% delete from EDITO S3 storage (if needed)
# delete button in datalab GUI does not work with large folders
# also does not work in python for boto3 or s3fs: An error occurred (MissingContentMD5) when calling the DeleteObjects operation: Missing required header for this request: Content-Md5.
# way to go: in EDITO datalab, select the folder, then open in Jupyter Notebook, there open a terminal and then run: mc rm -r --force s3/project-coclico/**folder**
# note that the force is needed!

# %% upload to GCS bucket

# get environment sorted
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
    pathlib.Path("P:/").joinpath(
        "11207608-coclico", "FASTTRACK_DATA", "google_credentials_new.json"
    )
)


# function to upload to the cloud (from coclicodata)
def dir_to_google_cloud(
    dir_path: str,
    gcs_project: str,
    bucket_name: str,
    bucket_proj: str,
    dir_name: str,
    return_URL: bool = False,
):
    """Upload directory to Google Cloud Services

    # TODO: fails when uploading to store that already exists or;
    # TODO: creates a subfolder in the desired folder when a store already exists, fix this..

    """

    # file system interface for google cloud storage
    fs = gcsfs.GCSFileSystem(
        gcs_project, token=os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    )

    # Define Google Cloud target directory
    target_path = urljoin(bucket_name, bucket_proj, dir_name)

    # Check if could directory already exists
    if fs.exists(urljoin(target_path, "catalog.json")):
        print(f"Cloud directory {target_path} already exists...")
        # Ask user to confirm directory overwrite
        if click.confirm("Do you want to overwirte this directory?"):
            # Check if user is on the main branch
            if dir_name == "coclico-stac" and click.confirm(
                "You trying to overwrite the main coclico-stac, are you working from the coclicodata Github main branch?"
            ):
                # Remove target directory to be updated
                fs.rm(target_path, recursive=True)
            else:
                # Remove target directory to be updated
                fs.rm(target_path, recursive=True)

    # saved directory to google cloud
    print(f"Writing to directory at {target_path}...")
    try:
        fs.put(dir_path, target_path, recursive=True)
        print("Done!")
    except OSError as e:
        print(f"Failed uploading: \n {e}")

    # When requested return resulting URL
    if return_URL:
        return fs.url(target_path)


# execute function
dir_to_google_cloud(
    dir_path=LOCAL_CATALOG_PATH,
    gcs_project=GCS_PROJECT,
    bucket_name=BUCKET_NAME,
    bucket_proj=BUCKET_PROJ,
    dir_name=STAC_NAME,
)

# %% test the catalogs
catalog_test_S3 = pystac.Catalog.from_file(
    "https://minio.dive.edito.eu/project-coclico/coclico-stac-edito/catalog.json"
)

catalog_test_GCS = pystac.Catalog.from_file(
    "https://minio.dive.edito.eu/project-coclico/coclico-stac-edito/catalog.json"
)


# %% Access EDITO STAC
# edito_stac_url = "https://api.dive.edito.eu/data/catalogs"

# client = Client.open(edito_stac_url)
# client  # check to see if access

# %% fetch some collections
# collections = client.get_collections()
# for coll in collections:
#     print(f"Collection: {coll.id}")
#     # Retrieve full STAC Collection metadata
#     full_coll = client.get_collection(coll.id)
#     break
