# %%
import os
import pathlib
import sys
import json
import glob
import xarray as xr
import numpy as np
import datetime
import rasterio
import shapely
import pandas as pd
from posixpath import join as urljoin

import pystac
from pystac.stac_io import DefaultStacIO
from coclicodata.drive_config import p_drive
from coclicodata.etl.cloud_utils import (
    dataset_from_google_cloud,
    load_google_credentials,
    dir_to_google_cloud,
)
from coclicodata.etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import Catalog, CatalogType, Collection, Summaries
from coclicodata.coclico_stac.io import CoCliCoStacIO
from coclicodata.coclico_stac.layouts import CoCliCoCOGLayout
from coclicodata.coclico_stac.templates import (
    extend_links,
    gen_default_collection_props,
    gen_default_item,
    gen_default_item_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_template_collection,
)
from coclicodata.coclico_stac.extension import CoclicoExtension
from coclicodata.coclico_stac.datacube import add_datacube
from coclicodata.coclico_stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
    rm_special_characters,
)


# TODO: move itemize to ETL or stac.blueprint when generalized
def itemize(
    da,
    item: pystac.Item,
    blob_name: str,
    asset_roles: "List[str] | None" = None,  # "" enables Python 3.8 development not to crash: https://github.com/tiangolo/typer/issues/371
    asset_media_type=pystac.MediaType.COG,
) -> pystac.Item:
    """ """
    import rioxarray  # noqa

    item = item.clone()
    dst_crs = rasterio.crs.CRS.from_epsg(4326)

    bbox = rasterio.warp.transform_bounds(da.rio.crs, dst_crs, *da.rio.bounds())
    geometry = shapely.geometry.mapping(shapely.geometry.box(*bbox))

    item.id = blob_name
    item.geometry = geometry
    item.bbox = bbox
    item.datetime = pd.Timestamp(da["time"].item()).to_pydatetime()  # dataset specific
    # item.datetime = cftime_to_pdts(da["time"].item()).to_pydatetime() # dataset specific

    ext = pystac.extensions.projection.ProjectionExtension.ext(
        item, add_if_missing=True
    )
    ext.bbox = da.rio.bounds()
    ext.shape = da.shape[-2:]
    ext.epsg = da.rio.crs.to_epsg()
    ext.geometry = shapely.geometry.mapping(shapely.geometry.box(*ext.bbox))
    ext.transform = list(da.rio.transform())[:6]
    ext.add_to(item)

    href = os.path.join(
        GCS_PROTOCOL,
        BUCKET_NAME,
        BUCKET_PROJ,
        COLLECTION_ID,
        blob_name,
    )

    roles = asset_roles or ["data"]

    # TODO: We need to generalize this `href` somewhat.
    dasset = pystac.Asset(  # data asset
        href=href,
        media_type=asset_media_type,
        roles=roles,
    )

    item.add_asset("data", dasset)

    roles = asset_roles or ["visual"]
    title = COLLECTION_ID + ":" + blob_name.split(".")[0].replace("\\", "_")

    # TODO: We need to generalize this `href` somewhat.
    vasset = pystac.Asset(  # data asset
        href="https://coclico.avi.deltares.nl/geoserver/%s/wms?bbox={bbox-epsg-3857}&format=image/png&service=WMS&version=1.1.1&request=GetMap&srs=EPSG:3857&transparent=true&width=256&height=256&layers=%s"
        % (COLLECTION_ID, title),
        media_type="application/png",
        title=title,
        description="OGS WMS url",
        roles=roles,
    )

    item.add_asset("visual", vasset)

    return item


if __name__ == "__main__":
    # hard-coded input params at project level
    GCS_PROTOCOL = "https://storage.googleapis.com"
    GCS_PROJECT = "coclico-11207608-002"
    BUCKET_NAME = "coclico-data-public"
    BUCKET_PROJ = "coclico"

    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "slp"  # name of stac collection

    # hard-coded input params which differ per dataset
    ADDITIONAL_DIMENSIONS = [
        "scenarios",
        "ensemble",
        "time",
    ]  # List of str; dims added to datacube

    # these are added at collection level, determine dashboard graph layout using all items
    PLOT_SERIES = "scenarios"
    PLOT_X_AXIS = "time"
    PLOT_TYPE = "line"
    MIN = 0
    MAX = 3
    LINEAR_GRADIENT = [
        {"color": "hsl(110,90%,80%)", "offset": "0.000%", "opacity": 100},
        {"color": "hsla(55,88%,53%,0.5)", "offset": "50.000%", "opacity": 100},
        {"color": "hsl(0,90%,70%)", "offset": "100.000%", "opacity": 100},
    ]

    # define local directories
    home = pathlib.Path().home()
    tmp_dir = home.joinpath("data", "tmp")
    coclico_data_dir = p_drive.joinpath(
        "11207608-coclico", "FULLTRACK_DATA", "WP3"
    )  # remote p drive
    google_cred_dir = p_drive.joinpath(
        "11207608-coclico", "FASTTRACK_DATA", "google_credentials_new.json"
    )

    # hard-coded input params which differ per dataset
    METADATA_LIST = glob.glob(str(coclico_data_dir.joinpath("data", "*.json")))
    DATASET_DIR = "data"
    CF_FILE = "slr_medium_confidence_values_CF.nc"

    # use local or remote data dir
    use_local_data = False

    if use_local_data:
        ds_dir = tmp_dir.joinpath(DATASET_DIR)
    else:
        ds_dir = coclico_data_dir.joinpath(DATASET_DIR)

    if not ds_dir.exists():
        raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

    # directory to export result
    cog_dirs = coclico_data_dir.joinpath("cogs")

    catalog = Catalog.from_file(
        os.path.join(
            pathlib.Path(__file__).parent.parent.parent, STAC_DIR, "catalog.json"
        )
    )

    template_fp = os.path.join(
        pathlib.Path(__file__).parent.parent.parent,
        STAC_DIR,
        TEMPLATE_COLLECTION,
        "collection.json",
    )

    layout = CoCliCoCOGLayout()

    # %% DO THE WORK
    # Hard code the various ssp scenarios considered
    scens = "high_end", "ssp126", "ssp245", "ssp585"

    # List all nc-files from data folder
    ncfile_list = glob.glob(str(ds_dir.joinpath("*.nc")))

    for scen, file in zip(scens, ncfile_list):
        if not scen in file:
            raise ValueError(
                "The some or more of the strings defined in scens are not found in your file_list"
            )

    # load metadata
    with open(
        r"p:\11207608-coclico\FULLTRACK_DATA\WP3\data\full_dataset_metadata\SLP_CoCliCo_metadata.json",
        "r",
    ) as f:
        ds_metadata = json.load(f)

    if "Creative Commons" in ds_metadata["LICENSE"] and "4.0" in ds_metadata["LICENSE"]:
        ds_metadata["LICENSE"] = "CC-BY-4.0"

    # Add extra keywords
    ds_metadata["KEYWORDS"].extend(["Sea Levels", "Full-Track", "Data Layers"])

    # generate collection for dataset
    collection = get_template_collection(
        template_fp=template_fp,
        collection_id=COLLECTION_ID,
        title=ds_metadata["TITLE"],
        description=ds_metadata["SHORT_DESCRIPTION"],
        keywords=ds_metadata["KEYWORDS"],
        license=ds_metadata["LICENSE"],
        spatial_extent=ds_metadata["SPATIAL_EXTENT"],
        temporal_extent=ds_metadata["TEMPORAL_EXTENT"],
        providers=[
            pystac.Provider(
                name="Deltares",
                roles=[
                    pystac.provider.ProviderRole.PROCESSOR,
                    pystac.provider.ProviderRole.HOST,
                ],
                url="https://deltares.nl",
            ),
            pystac.Provider(
                ds_metadata["PROVIDERS"]["name"],
                roles=[
                    pystac.provider.ProviderRole.PRODUCER,
                ],
                url=ds_metadata["PROVIDERS"]["url"],
                description=ds_metadata["PROVIDERS"]["description"],
            ),
        ],
    )

    # %%
    dimcombs = []
    for scen, ncfile, metadata_fp in zip(scens, ncfile_list, METADATA_LIST):

        slp = xr.open_dataset(ncfile, engine="rasterio", mask_and_scale=False)

        slp["time"] = slp.indexes["time"].to_datetimeindex()

        # load metadata template
        with open(metadata_fp, "r") as f:
            metadata = json.load(f)

        for var in slp:
            for itime, time in enumerate(slp["time"].values):

                # Select the variable and timestep from dataset
                da = slp[var].isel(time=itime)

                # Set final output file name, nc-file is broken down into tif's
                item_name = np.datetime_as_string(time, unit="Y") + ".tif"

                blob_name = pathlib.Path(
                    scen,
                    var,
                    item_name,
                )

                # TODO: generalize this
                dimcomb = {
                    ADDITIONAL_DIMENSIONS[0]: scen,
                    ADDITIONAL_DIMENSIONS[1]: var,
                    ADDITIONAL_DIMENSIONS[2]: item_name.split(".")[0],
                }
                dimcombs.append(dimcomb)

                outpath = cog_dirs.joinpath(blob_name)
                template_item = pystac.Item(
                    "id", None, None, datetime.datetime(2000, 1, 1), {}
                )

                item = itemize(da, template_item, blob_name=str(blob_name))

                # TODO: include this in our datacube?
                # add dimension key-value pairs to stac item properties dict
                for k, v in dimcomb.items():
                    item.properties[k] = v

                collection.add_item(item, strategy=layout)

    # %% TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    collection.summaries = Summaries({})
    # TODO: check if maxcount is required (inpsired on xstac library)
    # stac_obj.summaries.maxcount = 50
    dimvals = {}
    for d in dimcombs:
        for key, value in d.items():
            if key not in dimvals:
                dimvals[key] = []
            if value not in dimvals[key]:
                dimvals[key].append(value)

    for k, v in dimvals.items():
        collection.summaries.add(k, v)

    # collection.extra_fields["item_assets"] = {"data": {"type": pystac.MediaType.COG}}

    pystac.extensions.item_assets.ItemAssetsExtension.add_to(collection)

    ASSET_EXTRA_FIELDS = {
        "xarray:storage_options": {"token": "google_default"},
    }

    collection.extra_fields["item_assets"] = {
        "data": {
            "type": pystac.MediaType.COG,
            "title": "Global Sea Level Projections",
            "roles": ["data"],
            "description": "The MSL_CIS_HIGH-END dataset provides AR6-based regional mean sea level projections following the High-end in 2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100, 2110, 2120, 2130, 2140 and 2150 with respect to the baseline period 1995-2014 at a resolution of 1° x 1°.",
            **ASSET_EXTRA_FIELDS,
        }
    }

    collection.extra_fields["deltares:units"] = ds_metadata["UNITS"]
    collection.extra_fields["deltares:plotType"] = (
        PLOT_TYPE  # NOTE:this causes validation to break
    )
    collection.extra_fields["deltares:min"] = MIN
    collection.extra_fields["deltares:max"] = MAX

    # set extra link properties
    extend_links(collection, dimvals.keys())

    # Add thumbnail
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://storage.googleapis.com/coclico-data-public/coclico/assets/thumbnails/"
            + COLLECTION_ID
            + ".png",  # noqa: E501,  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    # Check if collection already exists within catalog
    if catalog.get_child(collection.id):
        # If so, delete child
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")

    # add collection to catalog
    catalog.add_child(collection)

    # normalize the paths
    collection.normalize_hrefs(
        os.path.join(
            pathlib.Path(__file__).parent.parent.parent, STAC_DIR, COLLECTION_ID
        ),
        strategy=layout,
    )

    # Validate collection instead of full catalog in stac_to_cloud.py
    collection.validate_all()

    # Initialize stac_io
    stac_io = DefaultStacIO()

    # save updated catalog to local drive
    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(pathlib.Path(__file__).parent.parent.parent, STAC_DIR),
        # dest_href=str(tmp_dir),
        stac_io=stac_io,  # TODO: Adjust to STAC IO
    )
    print("Done!")

    # upload directory with cogs to google cloud
    load_google_credentials(google_token_fp=google_cred_dir)

    dir_to_google_cloud(
        dir_path=str(cog_dirs),
        gcs_project=GCS_PROJECT,
        bucket_name=BUCKET_NAME,
        bucket_proj=BUCKET_PROJ,
        dir_name="slp",
    )


# %%
