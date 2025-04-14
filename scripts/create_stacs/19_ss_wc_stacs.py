# %%
import os
import pathlib
import sys
import cv2
import json
from posixpath import join as urljoin
import pystac
from coclicodata.drive_config import p_drive
from coclicodata.etl.cloud_utils import (
    load_google_credentials,
    file_to_google_cloud,
    dataset_from_google_cloud,
)
from coclicodata.etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import Catalog, CatalogType, Collection, Summaries

from pystac.stac_io import DefaultStacIO
from coclicodata.coclico_stac.reshape_im import reshape_aspectratio_image
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

if __name__ == "__main__":
    # Define (local and) remote drives
    COCLICO_DATA_DIR = p_drive.joinpath("11207608-coclico", "FULLTRACK_DATA")
    # Project paths & files (manual input)
    WP_DIR = COCLICO_DATA_DIR.joinpath("WP3")
    DATA_DIR = WP_DIR.joinpath("data")
    DS_DIR = DATA_DIR.joinpath("NetCDF")
    ZARR_FILE = DS_DIR.joinpath("CTP_MarineClimatologies.zarr")
    METADATA_FILE = DS_DIR.joinpath("CTP_MarineClimatologies.json")

    # Load metadata for setting variables such as data description etc.
    with open(METADATA_FILE, "r") as f:
        METADATA = json.load(f)

    # Extend keywords
    METADATA["KEYWORDS"].extend(["Sea Levels", "Full-Track"])

    # hard-coded input params at project level
    GCS_PROJECT = "coclico-11207608-002"
    BUCKET_NAME = "coclico-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"
    CRED_DIR = pathlib.Path(p_drive, "11207608-coclico", "FASTTRACK_DATA")

    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "ss_wc"  # name of stac collection
    COLLECTION_TITLE = "Storm Surge and Wave Climate"
    DATASET_DESCRIPTION = METADATA["DESCRIPTION"]

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = COLLECTION_ID + ".zarr"
    VARIABLES = ["Hsmean", "SSp99", "tidal_range"]  # xarray variables in dataset
    X_DIMENSION = "lon"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "lat"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = False  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = []
    DIMENSIONS_TO_IGNORE = ["stations"]  # False, None, or str; additional dims ""
    MAP_SELECTION_DIMS = None
    STATIONS = "locationId"
    TYPE = "circle"
    ON_CLICK = {}

    # these are added at collection level
    UNITS = "m"
    PLOT_SERIES = "scenarios"
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
        "https://storage.googleapis.com", BUCKET_NAME, BUCKET_PROJ, DATASET_FILENAME
    )

    # read data from gcs zarr store
    ds = dataset_from_google_cloud(
        bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    )

    # import xarray as xr

    # fpath = pathlib.Path.home().joinpath("data", "tmp", "europe_storm_surge_level.zarr")
    # ds = xr.open_zarr(fpath)

    # cast zero terminated bytes to str because json library cannot write handle bytes
    ds = zero_terminated_bytes_as_str(ds)

    # remove characters that cause problems in the frontend.
    # ds = rm_special_characters(
    #     ds, dimensions_to_check=ADDITIONAL_DIMENSIONS, characters=["%"]
    # )

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
        keywords=METADATA["KEYWORDS"],
        license="CC-BY-4.0",  # NOTE: no license/doi was provided in the metadata
        spatial_extent=None,  # NOTE: no spatial extent was provided in the metadata
        temporal_extent=METADATA["TEMPORAL_EXTENT"],
        providers=[
            pystac.Provider(
                name=METADATA["PROVIDERS"]["name"],
                url=METADATA["PROVIDERS"]["url"],
                roles=[
                    "producer"
                ],  # NOTE: roles is plural and for that reason should be a list, consisting of one or more ['producer', 'licensor', 'processor', 'host']
                description=METADATA["PROVIDERS"]["description"],
            )
        ],
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
    if len(ADDITIONAL_DIMENSIONS) > 0:
        dimvals = get_dimension_values(ds, dimensions_to_ignore=DIMENSIONS_TO_IGNORE)
        dimcombs = get_dimension_dot_product(dimvals)
    else:
        dimvals = {}
        dimcombs = []

    # TODO: check what can be customized in the layout
    layout = CoCliCoZarrLayout()
    stac_io = DefaultStacIO()

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
            # coclico_ext = CoclicoExtension.ext(feature, add_if_missing=True)

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

        # stac items are generated for an empty AdditionalDimension (no dropdowns, visualize always the same single layer); consensus is that we always need items in a collection
        if not dimcombs:
            mapbox_url = get_mapbox_url(MAPBOX_PROJ, DATASET_FILENAME, var)

            # generate stac item key and add link to asset to the stac item
            item_id = "value"  # default name in such layers
            feature = gen_default_item(f"{var}-mapbox-{item_id}")
            feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url))

            # This calls ItemCoclicoExtension and links CoclicoExtension to the stac item
            # coclico_ext = CoclicoExtension.ext(feature, add_if_missing=True)

            feature.properties["deltares:item_key"] = item_id
            feature.properties["deltares:paint"] = get_paint_props(item_id)
            feature.properties["deltares:type"] = TYPE
            feature.properties["deltares:stations"] = STATIONS
            feature.properties["deltares:onclick"] = ON_CLICK

            # add stac item to collection
            collection.add_item(feature, strategy=layout)

    # if no variables present we still need to add zarr reference at collection level
    if not VARIABLES:
        collection.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

    # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    collection.summaries = Summaries({})
    # TODO: check if maxcount is required (inpsired on xstac library)
    # stac_obj.summaries.maxcount = 50
    for k, v in dimvals.items():
        collection.summaries.add(k, v)

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

    # Set thumbnail directory
    THUMB_DIR = pathlib.Path(__file__).parent.parent.joinpath("thumbnails")
    THUMB_FILE = THUMB_DIR.joinpath(COLLECTION_ID + ".png")

    # Make sure image is reshaped to desired aspect ratio (default = 16/9)
    cropped_im = reshape_aspectratio_image(str(THUMB_FILE))

    # Overwrite image with cropped version
    cv2.imwrite(str(THUMB_FILE), cropped_im)

    # Load google credentials
    load_google_credentials(
        google_token_fp=CRED_DIR.joinpath("google_credentials_new.json")
    )

    # Upload thumbnail to cloud
    THUMB_URL = file_to_google_cloud(
        str(THUMB_FILE),
        GCS_PROJECT,
        BUCKET_NAME,
        BUCKET_PROJ,
        "assets/thumbnails",
        THUMB_FILE.name,
        return_URL=True,
    )

    # Add thumbnail
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            THUMB_URL,  # noqa: E501
            title="Thumbnail",
            media_type=pystac.MediaType.PNG,
        ),
    )

    if catalog.get_child(collection.id):
        catalog.remove_child(collection.id)
        print(f"Removed child: {collection.id}.")

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
        stac_io=stac_io,
    )
# %%
