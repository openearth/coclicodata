# %%
import os
import pathlib
import sys
import json
from posixpath import join as urljoin

# make modules importable when running this file as script
# sys.path.append(str(pathlib.Path(__file__).parent.parent))

# import coclicodata functionalities (TODO: import as package when ETL is decoupled from CoCliCo STAC; Etiënne & Floris now whereabouts)
sys.path.append(
    str(pathlib.Path().home().joinpath("Documents", "GitHub", "coclicodata"))
)  # import functionality from local clone of coclicodata (make sure you pull the latest version)

import pystac
from etl import rel_root, p_drive
from etl.cloud_services import dataset_from_google_cloud
from etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import Catalog, CatalogType, Collection, Summaries
from stac.blueprint import (
    IO,
    LayoutZarr,
    extend_links,
    gen_default_collection_props,
    gen_default_item,
    gen_default_item_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_template_collection,
)
from stac.coclico_extension import CoclicoExtension
from stac.datacube import add_datacube
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
    rm_special_characters,
)

if __name__ == "__main__":
    # hard-coded input params at project level
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"

    # hard-coded input params at project level
    gca_data_dir = pathlib.Path(
        # p_drive, "1000545-054-globalbeaches", "15_GlobalCoastalAtlas", "datasets"
        p_drive,
        "11205479-coclico",
        "FULLTRACK_DATA",
        "WP3"
    )
    dataset_dir = gca_data_dir

    # opening metadata
    metadata_fp = gca_data_dir.joinpath("metadata","metadata_SLP.json")
    with open(metadata_fp, "r") as f:
        metadata = json.load(f)

    # STAC configs
    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_TITLE = metadata["TITLE"]
    COLLECTION_ID = metadata["TITLE_ABBREVIATION"]  # name of stac collection
    DATASET_DESCRIPTION = metadata["DESCRIPTION"]

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "sea_level_projections.zarr"
    VARIABLES = ["slp"]  # xarray variables in dataset
    X_DIMENSION = "lon"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "lat"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = "time"  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = [
        "ssp",
        "ensemble",
        "time"
    ]  # Empty list or list of str; additional dims ""
    DIMENSIONS_TO_IGNORE = [
        "nlocs",
    ]  # List of str; dims ignored by datacube
    MAP_SELECTION_DIMS = {
        "ssp": ["ssp126","ssp585","ssp245","high"],
        "ensemble": ["low", "median", "high"],
        "time":[2030, 2050, 2100, 2150]
    }
    # hard-coded frontend properties
    STATIONS = "locs"
    TYPE = "circle"
    ON_CLICK = {}

    # these are added at collection level (for graph plot in the dashboard)
    UNITS = "m"
    PLOT_SERIES = "slp"
    PLOT_X_AXIS = "time"
    PLOT_TYPE = "line"
    MIN = 0
    MAX = 3
    LINEAR_GRADIENT = [
        {"color": "hsl(110,90%,80%)", "offset": "0.000%", "opacity": 100},
        {"color": "hsla(55,88%,53%,0.5)", "offset": "50.000%", "opacity": 100},
        {"color": "hsl(0,90%,70%)", "offset": "100.000%", "opacity": 100},
    ]

    # functions to generate properties that vary per dataset but cannot be hard-coded because
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
    ds = rm_special_characters(
        ds, dimensions_to_check=ADDITIONAL_DIMENSIONS, characters=["%"]
    )

    title = ds.attrs.get("title", COLLECTION_ID)

    # load coclico data catalog
    catalog = Catalog.from_file(
        os.path.join(pathlib.Path(__file__).parent.parent, STAC_DIR, "catalog.json")
    )

    template_fp = os.path.join(
        pathlib.Path(__file__).parent.parent,
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
        keywords=[]
    )

    # add datacube dimensions derived from xarray dataset to dataset stac_obj
    collection = add_datacube(
        stac_obj=collection,
        ds=ds,
        x_dimension=X_DIMENSION,
        y_dimension=Y_DIMENSION,
        temporal_dimension=TEMPORAL_DIMENSION,
        additional_dimensions=ADDITIONAL_DIMENSIONS,
        reference_system=ds.CRS,
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
    if len(ADDITIONAL_DIMENSIONS) > 0:
        dimvals = get_dimension_values(ds, dimensions_to_ignore=DIMENSIONS_TO_IGNORE)
        dimcombs = get_dimension_dot_product(dimvals)
    else:
        dimvals = {}
        dimcombs = []

    # TODO: check what can be customized in the layout
    layout = LayoutZarr()

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
    coclico_ext = CoclicoExtension.ext(collection, add_if_missing=True)

    # Add frontend properties defined above to collection extension properties. The
    # properties attribute of this extension is linked to the extra_fields attribute of
    # the stac collection.
    coclico_ext.units = UNITS
    coclico_ext.plot_series = PLOT_SERIES
    coclico_ext.plot_x_axis = PLOT_X_AXIS
    coclico_ext.plot_type = PLOT_TYPE
    coclico_ext.min_ = MIN
    coclico_ext.max_ = MAX
    coclico_ext.linear_gradient = LINEAR_GRADIENT

    # set extra link properties
    extend_links(collection, dimvals.keys())

    # save and limit number of folders
    catalog.add_child(collection)

    collection.normalize_hrefs(
        os.path.join(pathlib.Path(__file__).parent.parent, STAC_DIR, COLLECTION_ID),
        strategy=layout,
    )

    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(pathlib.Path(__file__).parent.parent, STAC_DIR),
        stac_io=IO(),
    )

# %%
