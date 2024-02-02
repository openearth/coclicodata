#%%
<<<<<<< Updated upstream
import os
import pathlib
import sys
import json
from posixpath import join as urljoin

import pystac
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
=======

# Import standard packages
import os
import pathlib
import sys
import numpy as np
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import xarray as xr
import math
import itertools
import glob

# Import custom functionality
from coclicodata.drive_config import p_drive
from coclicodata.etl.cf_compliancy_checker import check_compliancy, save_compliancy

# Define (local and) remote drives
gca_data_dir = p_drive.joinpath("11205479-coclico","FULLTRACK_DATA","WP3")

# Workaround to the Windows OS (10) udunits error after installation of cfchecker: https://github.com/SciTools/iris/issues/404
os.environ["UDUNITS2_XML_PATH"] = str(
    pathlib.Path().home().joinpath(  # change to the udunits2.xml file dir in your Python installation
        r"Anaconda3\pkgs\udunits2-2.2.28-h892ecd3_0\Library\share\udunits\udunits2.xml"
        )
    )
>>>>>>> Stashed changes

if __name__ == "__main__":
    # hard-coded input params at project level
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"

    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "cfr"  # name of stac collection
    COLLECTION_TITLE = "Coastal flood risk"
    DATASET_DESCRIPTION = """Dataset presenting the results of a European coastal flood risk assessment (present till 2100), incorporating impacts of climate change scenarios (RCP4.5 and RCP8.5) and different socio-economic pathways (SSP1, SSP3 and SSP5). Outcomes are expressed in Expected Annual Damage (EAD), EAD per Gross Domestic Product (EAD_GDP) and the Expected Annual number of People Affected (AEPA) per NUTS0 region (country) and are available for the years 2000, 2050 and 2100.  This dataset is part of the [LISCOAST](https://data.jrc.ec.europa.eu/collection/LISCOAST) project. See this [article](https://doi.org/10.1038/s41558-018-0260-4) for more dataset-specific information. """

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "coastal_flood_risk.zarr"
    VARIABLES = ["ead", "ead_gdp", "eapa"]  # xarray variables in dataset
    X_DIMENSION = "lon"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "lat"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = "time"  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = [
        "scenarios",
    ]  # False, None, or str; additional dims ""
    DIMENSIONS_TO_IGNORE = [
        "stations",
        "nscenarios",
        "geometry",
    ]  # List of str; dims ignored by datacube

    # hard-coded frontend properties
    STATIONS = "locationId"
    TYPE = "circle"
    ON_CLICK = {}

    # these are added at collection level
    UNITS = "m"
    PLOT_SERIES = "scenario"
    PLOT_TYPE = "line"
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
        "https://storage.googleapis.com", BUCKET_NAME, BUCKET_PROJ, DATASET_FILENAME
    )

    # read data from gcs zarr store
    ds = dataset_from_google_cloud(
        bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    )

    # import xarray as xr

    # fpath = pathlib.Path.home().joinpath(
    #     "ddata", "tmp", "eu_coastal_flood_risk.zarr"
    # )
    # ds = xr.open_zarr(fpath)

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
        keywords=[],
    )

    # add datacube dimensions derived from xarray dataset to dataset stac_obj
    collection = add_datacube(
        stac_obj=collection,
        ds=ds,
        x_dimension=X_DIMENSION,
        y_dimension=Y_DIMENSION,
        temporal_dimension=TEMPORAL_DIMENSION,
        additional_dimensions=ADDITIONAL_DIMENSIONS,
    )

    # add datacube dimensions derived from xarray dataset to dataset stac_obj
    collection = add_datacube(
        stac_obj=collection,
        ds=ds,
        x_dimension=X_DIMENSION,
        y_dimension=Y_DIMENSION,
        temporal_dimension=TEMPORAL_DIMENSION,
        additional_dimensions=ADDITIONAL_DIMENSIONS,
    )

    # generate stac feature keys (strings which will be stac item ids) for mapbox layers
    dimvals = get_dimension_values(ds, dimensions_to_ignore=DIMENSIONS_TO_IGNORE)
    dimcombs = get_dimension_dot_product(dimvals)

    # TODO: check what can be customized in the layout
    layout = CoCliCoZarrLayout()

    # Add thumbnail to the collection
    collection.add_asset(
    "thumbnail",
    pystac.Asset(
        "https://coclico.blob.core.windows.net/assets/thumbnails/coastal-mask-thumbnail.png",  # noqa: E501
        title="Thumbnail",
        media_type=pystac.MediaType.PNG,
        ),
    )

    # create stac collection per variable and add to dataset collection
    for var in VARIABLES:
        # add zarr store as asset to stac_obj
        collection.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

        # stac items are generated per AdditionalDimension (non spatial)
        for dimcomb in dimcombs:
            mapbox_url = get_mapbox_url(MAPBOX_PROJ, DATASET_FILENAME, var)

            # generate stac item key and add link to asset to the stac item
            item_id = get_mapbox_item_id(dimcomb)
            feature = gen_default_item(f"{var}-mapbox-{item_id}")
            feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url))

            # This calls ItemCoclicoExtension and links CoclicoExtension to the stac item
            coclico_ext = CoclicoExtension.ext(feature, add_if_missing=True)

            coclico_ext.item_key = item_id
            coclico_ext.paint = get_paint_props(item_id)
            coclico_ext.type_ = TYPE
            coclico_ext.stations = STATIONS
            coclico_ext.on_click = ON_CLICK

            # TODO: include this in our datacube?
            # add dimension key-value pairs to stac item properties dict
            for k, v in dimcomb.items():
                feature.properties[k] = v

            # add stac item to collection
            collection.add_item(feature, strategy=layout)

    # if no variables present we still need to add zarr reference at colleciton level
    if not VARIABLES:
        collection.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

    # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    collection.summaries = Summaries({})
    # TODO: check if maxcount is required (inpsired on xstac library)
    # stac_obj.summaries.maxcount = 50
    for k, v in dimvals.items():
        collection.summaries.add(k, v)

    # this calls CollectionCoclicoExtension since stac_obj==pystac.Collection
    coclico_ext = CoclicoExtension.ext(collection, add_if_missing=True)

    # Add frontend properties defined above to collection extension properties. The
    # properties attribute of this extension is linked to the extra_fields attribute of
    # the stac collection.
    coclico_ext.units = UNITS
    coclico_ext.plot_series = PLOT_SERIES
    coclico_ext.plot_type = PLOT_TYPE
    coclico_ext.min_ = MIN
    coclico_ext.max_ = MAX
    coclico_ext.linear_gradient = LINEAR_GRADIENT

    # set extra link properties
    extend_links(collection, dimvals.keys())

    # Add thumbnail
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://storage.googleapis.com/dgds-data-public/coclico/assets/thumbnails/" + COLLECTION_ID + ".png",  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    # save and limit number of folders
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
