# %%
# ## Load software
import datetime

# import os
import pathlib
import glob
import os

# import sys
# from re import S, template
import json
import fsspec
from typing import Any, Dict, List, Optional, Tuple, Union

# import cftime
# import numpy as np
import pandas as pd
import pystac
import rasterio

# import rioxarray as rio
import shapely
import xarray as xr
import math
import dask
from posixpath import join as urljoin
from pystac.extensions import eo, raster
from stactools.core.utils import antimeridian
from pystac.stac_io import DefaultStacIO
from pystac import Catalog, CatalogType, Collection, Summaries
# Import coclico modules
from coclicodata.drive_config import p_drive
from coclicodata.etl.cloud_utils import dataset_from_google_cloud
from coclicodata.etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import Catalog, CatalogType, Collection, Summaries
from coclicodata.coclico_stac.io import CoCliCoStacIO
from coclicodata.coclico_stac.layouts import CoCliCoZarrLayout
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


# %%

if __name__ == "__main__":

    # Define (local and) remote drives
    COCLICO_DATA_DIR = p_drive.joinpath("11207608-coclico", "FULLTRACK_DATA")
    # Project paths & files (manual input)
    WP_DIR = COCLICO_DATA_DIR.joinpath("WP3")
    DATA_DIR = WP_DIR.joinpath("data")
    DS_DIR = DATA_DIR.joinpath("NetCDF")
    ZARR_FILE = DS_DIR.joinpath("CTP_ReturnPeriods.zarr")
    METADATA_FILE = DS_DIR.joinpath("CTP_ReturnPeriods.json")

    # Load metadata for setting variables such as data description etc.
    with open(METADATA_FILE, "r") as f:
        METADATA = json.load(f)

    # hard-coded input params at project level
    BUCKET_NAME = "coclico-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"

    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "twl"  # name of stac collection
    COLLECTION_TITLE = "Total Water Level"
    DATASET_DESCRIPTION = METADATA['DESCRIPTION']

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = COLLECTION_ID
    VARIABLES = ["RP1", "RP100","RP1000"]  # xarray variables in dataset
    X_DIMENSION = "lon"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "lat"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = None  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = None  # False, None, or str; additional dims ""
    MAP_SELECTION_DIMS = {"ensemble": "mean", "time": 2100}
    STATIONS = "locationId"
    TYPE = "circle"
    ON_CLICK = {}

    # these are added at collection level
    UNITS = "m"
    PLOT_SERIES = "scenario"
    PLOT_X_AXIS = "time"
    PLOT_TYPE = "area"
    MIN = 0
    MAX = 3
    LINEAR_GRADIENT = [
        {"color": "hsl(0,90%,80%)", "offset": "0.000%", "opacity": 100},
        {"color": "hsla(55,88%,53%,0.5)", "offset": "50.000%", "opacity": 100},
        {"color": "hsl(110,90%,70%)", "offset": "100.000%", "opacity": 100},
    ]

    # functions to generate properties that vary per dataset but cannot be hard-corded because
    # they also require input arguments
    def get_paint_props(item_key: str):
        return {
            "circle-color": [
                "interpolate",
                ["linear"],
                ["get", item_key],
                0,
                "hsl(110,90%,80%)",
                1.5,
                "hsla(55, 88%, 53%, 0.5)",
                3.0,
                "hsl(0, 90%, 70%)",
            ],
            "circle-radius": [
                "interpolate",
                ["linear"],
                ["zoom"],
                0,
                0.5,
                1,
                1,
                5,
                5,
            ],
        }

    # semi hard-coded input params
    gcs_zarr_store = os.path.join("gcs://", BUCKET_NAME, BUCKET_PROJ, DATASET_FILENAME)
    gcs_api_zarr_store = os.path.join(
        "https://storage.googleapis.com", BUCKET_NAME, BUCKET_PROJ, DATASET_FILENAME + ".zarr"
    )

#%%

    ds = xr.open_zarr(ZARR_FILE)

    # cast zero terminated bytes to str because json library cannot write handle bytes
    ds = zero_terminated_bytes_as_str(ds)

    title = ds.attrs.get("title", COLLECTION_ID)

    # load coclico data catalog
    catalog = Catalog.from_file(os.path.join(pathlib.Path(__file__).parent.parent.parent, STAC_DIR, "catalog.json"))

    template_fp = os.path.join(
        pathlib.Path(__file__).parent.parent.parent, STAC_DIR, TEMPLATE_COLLECTION, "collection.json"
    )

    # generate collection for dataset
    collection = get_template_collection(
        template_fp=template_fp,
        collection_id=COLLECTION_ID,
        title=COLLECTION_TITLE,
        description=DATASET_DESCRIPTION,
        keywords=METADATA["KEYWORDS"].append(["Sea Levels", "Full-Track"]),
        license="CC-BY-4.0",    # NOTE: no license/doi was provided in the metadata
        spatial_extent=None,    # NOTE: no spatial extent was provided in the metadata
        temporal_extent=METADATA["TEMPORAL_EXTENT"],
        providers=[pystac.Provider(name=METADATA['PROVIDERS']['name'],
                                  url=METADATA['PROVIDERS']['url'],
                                  roles=[METADATA['PROVIDERS']['roles']], # NOTE: roles is plural and for that reason should be a list
                                  description=METADATA['PROVIDERS']['description'])]
    )
    

    # add datacube dimensions derived from xarray dataset to dataset stac_obj
    collection = add_datacube(
        stac_obj=collection,
        ds=ds,
        x_dimension=X_DIMENSION,
        y_dimension=Y_DIMENSION,
        temporal_dimension=False,
        additional_dimensions=ADDITIONAL_DIMENSIONS
    )

# %%
    # TODO: check what can be customized in the layout
    layout = CoCliCoZarrLayout()

    # create stac collection per variable and add to dataset collection
    for var in VARIABLES:
        # add zarr store as asset to stac_obj
        collection.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

        # add extra fields to the collection for plotting purposes
        collection.extra_fields["deltares:units"] = UNITS
        collection.extra_fields["deltares:plotSeries"] = PLOT_SERIES
        collection.extra_fields["deltares:plotxAxis"] = PLOT_X_AXIS
        collection.extra_fields["deltares:plotType"] = PLOT_TYPE
        collection.extra_fields["deltares:min"] = MIN
        collection.extra_fields["deltares:max"] = MAX
        collection.extra_fields["deltares:linearGradient"] = LINEAR_GRADIENT

        # NOTE: only spatial dimension exists, no time/scen etc., thus each variable will be an asset

        mapbox_url = get_mapbox_url(MAPBOX_PROJ, COLLECTION_ID, var)

        # generate stac item key and add link to asset to the stac item
        item_id = var
        feature = gen_default_item(f"{var}-mapbox")
        feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url))

        # Add properties at feature level
        feature.properties["deltares:item_key"] = item_id
        feature.properties["deltares:paint"] = get_paint_props(item_id)
        feature.properties["deltares:type"] = TYPE
        feature.properties["deltares:stations"] = STATIONS
        feature.properties["deltares:onclick"] = ON_CLICK

        # add stac item to collection
        collection.add_item(feature, strategy=layout)
# %%
    # if no variables present we still need to add zarr reference at collection level
    if not VARIABLES:
        collection.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

    # # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    # collection.summaries = Summaries({})
    # # TODO: check if maxcount is required (inpsired on xstac library)
    # # stac_obj.summaries.maxcount = 50
    # for k, v in dimvals.items():
    #     collection.summaries.add(k, v)

    dimvals = get_dimension_values(ds, dimensions_to_ignore=[])

    # set extra link properties
    extend_links(collection, dimvals.keys())

    # add reduced dimensions as links as well
    extend_links(
        collection,
        {k: v for k, v in MAP_SELECTION_DIMS.items() if k not in dimvals.keys()}.keys(),
    )

    # Add thumbnail
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://storage.googleapis.com/dgds-data-public/coclico/assets/thumbnails/" + COLLECTION_ID + ".png",  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    if catalog.get_child(collection.id):
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")
    
    catalog.add_child(collection)

    collection.normalize_hrefs(
        os.path.join(pathlib.Path(__file__).parent.parent.parent, STAC_DIR, COLLECTION_ID), strategy=layout
    )

    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(pathlib.Path(__file__).parent.parent.parent, STAC_DIR),
        stac_io=CoCliCoStacIO(),
    )
# %%
