# %%
import os
import pathlib
import sys
import json
from posixpath import join as urljoin

import pystac
from coclicodata.drive_config import p_drive
from coclicodata.etl.cloud_utils import (
    dataset_from_google_cloud,
    dataset_to_google_cloud,
    load_google_credentials,
)
from coclicodata.etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import Catalog, CatalogType, Collection, Summaries

from coclicodata.coclico_stac.io import CoCliCoStacIO
from pystac.stac_io import DefaultStacIO
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

if __name__ == "__main__":
    # hard-coded input params at project level
    GCS_PROJECT = "CoCliCo - 11207608-002"
    BUCKET_NAME = "coclico-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"

    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "sc"  # name of stac collection
    COLLECTION_TITLE = "Shoreline change"
    DATASET_DESCRIPTION = """Projections of global shoreline change in view of climate change. This assessment considers the combined effects of ambient change (historical trends), sea level rise (RCP4.5 and RCP8.5) and storm driven (instantaneous) erosion. Data is computed for seven ensembles (1, 5, 17, 50, 83, 95 and 99th percentile) and two timesteps (2050 and 2100). This dataset is part of the [LISCOAST](https://data.jrc.ec.europa.eu/collection/LISCOAST) project. See this [article](https://doi.org/10.1038/s41558-020-0697-0) for more dataset-specific information."""

    # hard-coded input params which differ per dataset
    DATASET_INFILENAME = "globalErosionProjections_Long_Term_Change.zarr"
    DATASET_FILENAME = "shoreline_change_projections.zarr"
    VARIABLES = ["sc"]  # xarray variables in dataset
    X_DIMENSION = "lon"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "lat"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = "time"  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = [
        "ensemble",
        "scenarios",
    ]  # False, None, or str; additional dims ""
    DIMENSIONS_TO_IGNORE = [
        "time",
        "stations",
        "nscenarios",
        "nensemble",
    ]  # List of str; dims ignored by datacube
    MAP_SELECTION_DIMS = {"time": [2100]}

    # hard-coded frontend properties
    STATIONS = "locationId"
    TYPE = "circle"
    ON_CLICK = {}

    # these are added at collection level
    UNITS = "m"
    PLOT_SERIES = "ensemble"
    PLOT_X_AXIS = "time"
    PLOT_TYPE = "area"
    MIN = -200
    MAX = 200
    LINEAR_GRADIENT = [
        {"color": "hsla(8,100%,43%, 0.7)", "offset": "0.000%", "opacity": 100},
        {"color": "hsla(39, 203%, 221%, 0.5)", "offset": "50.000%", "opacity": 100},
        {"color": "hsla(228,100%,42%, 0.7)", "offset": "100.000%", "opacity": 100},
    ]

    # functions to generate properties that vary per dataset but cannot be hard-corded because
    # they also require input arguments
    def get_paint_props(item_key: str):
        return {
            "circle-color": [
                "interpolate",
                ["linear"],
                ["get", item_key],
                -200,
                "hsla(8,100%,43%,0.7)",
                0,
                "hsla(39,203%,221%,0.5)",
                200,
                "hsla(228,100%,42%,0.7)",
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

    # add file to bucket
    cred_data_dir = p_drive.joinpath("11207608-coclico", "FASTTRACK_DATA")
    # load google credentials
    load_google_credentials(
        google_token_fp=cred_data_dir.joinpath("google_credentials_new.json")
    )
    coclico_data_dir = p_drive.joinpath("11207608-coclico", "FASTTRACK_DATA")
    dataset_dir = coclico_data_dir.joinpath("05_erosion_projections_jrc")
    source_data_fp = dataset_dir.joinpath(DATASET_INFILENAME)

    dataset_to_google_cloud(
        ds=source_data_fp,
        gcs_project=GCS_PROJECT,
        bucket_name=BUCKET_NAME,
        bucket_proj=BUCKET_PROJ,
        zarr_filename=DATASET_FILENAME,
    )

    # read data from gcs zarr store
    ds = dataset_from_google_cloud(
        bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    )

    # import xarray as xr

    # fpath = pathlib.Path.home().joinpath(
    #     "data", "tmp", "shoreline_change_projections.zarr"
    # )
    # ds = xr.open_zarr(fpath)

    # cast zero terminated bytes to str because json library cannot write handle bytes
    ds = zero_terminated_bytes_as_str(ds)

    # remove characters that cause problems in the frontend.
    ds = rm_special_characters(
        ds, dimensions_to_check=ADDITIONAL_DIMENSIONS, characters=["%"]
    )

    title = ds.attrs.get("title", COLLECTION_ID)

    # load coclico data catalog
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

    # generate collection for dataset
    collection = get_template_collection(
        template_fp=template_fp,
        collection_id=COLLECTION_ID,
        title=COLLECTION_TITLE,
        description=DATASET_DESCRIPTION,
        keywords=["Fast-Track"],
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

    # This dataset has quite some dimensions, so if we would parse all information the end-user
    # would be overwhelmed by all options. So for the stac items that we generate for the frontend
    # visualizations a subset of the data is selected. Of course, this operation is dataset specific.
    for k, v in MAP_SELECTION_DIMS.items():
        if k in ds.dims and ds.coords:
            ds = ds.sel({k: v})
        else:
            try:
                # assume that coordinates with strings always have same dim name but with n
                ds = ds.sel({"n" + k: k == v})
            except:
                raise ValueError(f"Cannot find {k}")

    # generate stac feature keys (strings which will be stac item ids) for mapbox layers
    dimvals = get_dimension_values(ds, dimensions_to_ignore=DIMENSIONS_TO_IGNORE)
    dimcombs = get_dimension_dot_product(dimvals)

    # TODO: check what can be customized in the layout
    layout = CoCliCoZarrLayout()

    # create stac collection per variable and add to dataset collection
    for var in VARIABLES:
        # add zarr store as asset to stac_obj
        collection.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

        # stac items are generated per AdditionalDimension (non spatial)
        for dimcomb in dimcombs:
            mapbox_url = get_mapbox_url(MAPBOX_PROJ, DATASET_FILENAME, var)

            # generate stac item key and add link to asset to the stac item
            item_id = get_mapbox_item_id(dimcomb)
            perc = item_id.split("-")[1] + "%"  # get value to make percentage
            item_id = item_id.replace(
                item_id.split("-")[1], perc
            )  # add percentage in string to match mapbox items
            feature = gen_default_item(f"{var}-mapbox-{item_id}")
            feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url))

            # This calls ItemCoclicoExtension and links CoclicoExtension to the stac item
            # coclico_ext = CoclicoExtension.ext(feature, add_if_missing=True)

            # coclico_ext.item_key = item_id
            # coclico_ext.paint = get_paint_props(item_id)
            # coclico_ext.type_ = TYPE
            # coclico_ext.stations = STATIONS
            # coclico_ext.on_click = ON_CLICK

            feature.properties["deltares:item_key"] = item_id
            feature.properties["deltares:paint"] = get_paint_props(item_id)
            feature.properties["deltares:type"] = TYPE
            feature.properties["deltares:stations"] = STATIONS
            feature.properties["deltares:onclick"] = ON_CLICK

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

    # for k, v in MAP_SELECTION_DIMS.items():
    #     collection.summaries.add(k, v)

    # this calls CollectionCoclicoExtension since stac_obj==pystac.Collection
    # coclico_ext = CoclicoExtension.ext(collection, add_if_missing=True)

    # Add frontend properties defined above to collection extension properties. The
    # properties attribute of this extension is linked to the extra_fields attribute of
    # the stac collection.
    # coclico_ext.units = UNITS
    # coclico_ext.plot_series = PLOT_SERIES
    # coclico_ext.plot_x_axis = PLOT_X_AXIS
    # coclico_ext.plot_type = PLOT_TYPE
    # coclico_ext.min_ = MIN
    # coclico_ext.max_ = MAX
    # coclico_ext.linear_gradient = LINEAR_GRADIENT

    collection.extra_fields["deltares:units"] = UNITS
    collection.extra_fields["deltares:plotSeries"] = PLOT_SERIES
    collection.extra_fields["deltares:plotxAxis"] = PLOT_X_AXIS
    collection.extra_fields["deltares:plotType"] = PLOT_TYPE
    collection.extra_fields["deltares:min"] = MIN
    collection.extra_fields["deltares:max"] = MAX
    collection.extra_fields["deltares:linearGradient"] = LINEAR_GRADIENT

    # set extra link properties
    extend_links(collection, dimvals.keys())

    if catalog.get_child(collection.id):
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")

    # Add thumbnail
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            "https://storage.googleapis.com/coclico-data-public/coclico/assets/thumbnails/"
            + COLLECTION_ID
            + ".png",  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    # save and limit number of folders
    catalog.add_child(collection)

    collection.normalize_hrefs(
        os.path.join(
            pathlib.Path(__file__).parent.parent.parent, STAC_DIR, COLLECTION_ID
        ),
        strategy=layout,
    )

    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(pathlib.Path(__file__).parent.parent.parent, STAC_DIR),
        stac_io=DefaultStacIO(),
    )

# %%
