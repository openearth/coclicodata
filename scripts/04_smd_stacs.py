import os
import pathlib
import sys
from curses import color_content

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

import pystac
from etl import rel_root
from etl.cloud_services import dataset_from_google_cloud
from etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import CatalogType, Collection, Summaries
from stac.blueprint import (
    IO,
    Layout,
    extend_links,
    gen_default_collection_props,
    gen_default_item,
    gen_default_item_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_stac_obj_from_template,
)
from stac.coclico_extension import CoclicoExtension
from stac.datacube import add_datacube
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
)

if __name__ == "__main__":
    # hard-coded input params at project level
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"
    TEMPLATE = "template"  # stac template for dataset collection
    STAC_DIR = "current"

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "global_shoreline_morphodynamics.zarr"
    STAC_COLLECTION_NAME = "smd"  # name of stac collection
    VARIABLES = []  # xarray variables in dataset
    X_DIMENSION = "lon"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "lat"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = False  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = []  # False, None, or str; additional dims ""
    DIMENSIONS_TO_IGNORE = [
        "stations",
        "nstations",
    ]  # List of str; dims ignored by datacube
    DATASET_DESCRIPTION = """Global long-term (1984-2015) shoreline evolution based on satellite observations. Per transect location (500 m spaced) it is assessed what the change from land to sea, land to active zone and active zone to sea (erosion) as well as sea to land, sea to active zone and active zone to land (accretion) is. This dataset is part of the [LISCOAST](https://data.jrc.ec.europa.eu/collection/LISCOAST) project. See this [article](https://doi.org/10.1038/s41598-018-30904-w) for more dataset-specific information. """

    # hard-coded frontend properties
    STATIONS = "locationId"
    TYPE = "circle"
    ON_CLICK = {}

    # these are added at collection level
    STAC_COLLECTION_TITLE = "Global shoreline morphodynamics"
    UNITS = "m"
    PLOT_SERIES = "scenario"
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
    #     "data", "tmp", "global_shoreline_morphodynamics.zarr"
    # )
    # ds = xr.open_zarr(fpath)

    # cast zero terminated bytes to str because json library cannot write handle bytes
    ds = zero_terminated_bytes_as_str(ds)

    # load coclico data catalog
    catalog = pystac.Catalog.from_file(os.path.join(rel_root, STAC_DIR, "catalog.json"))

    # generate pystac collection from stac collection file
    collection = Collection.from_file(
        os.path.join(rel_root, STAC_DIR, "collection.json")
    )

    # get description/title from dataset, but if not exists just use stac collection name
    title = ds.attrs.get("title", STAC_COLLECTION_NAME)

    # generate stac_obj for dataset
    stac_obj = get_stac_obj_from_template(
        collection,
        template_fn=TEMPLATE,
        collection_id=STAC_COLLECTION_NAME,
        title=STAC_COLLECTION_TITLE,
        description=DATASET_DESCRIPTION,
    )

    # add datacube dimensions derived from xarray dataset to dataset stac_obj
    stac_obj = add_datacube(
        stac_obj=stac_obj,
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
    layout = Layout()

    # create stac collection per variable and add to dataset collection
    for var in VARIABLES:

        # add zarr store as asset to stac_obj
        stac_obj.add_asset("data", gen_zarr_asset(var, gcs_api_zarr_store))

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
            stac_obj.add_item(feature, strategy=layout)

    # if no variables present we still need to add zarr reference at colleciton level
    if not VARIABLES:
        stac_obj.add_asset("data", gen_zarr_asset(title, gcs_api_zarr_store))

    # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    stac_obj.summaries = Summaries({})
    # TODO: check if maxcount is required (inpsired on xstac library)
    # stac_obj.summaries.maxcount = 50
    for k, v in dimvals.items():
        stac_obj.summaries.add(k, v)

    # this calls CollectionCoclicoExtension since stac_obj==pystac.Collection
    coclico_ext = CoclicoExtension.ext(stac_obj, add_if_missing=True)

    # Add frontend properties defined above to collection extension properties. The
    # properties attribute of this extension is linked to the extra_fields attribute of
    # the stac collection.
    coclico_ext.units = UNITS
    coclico_ext.plot_series = PLOT_SERIES
    coclico_ext.min_ = MIN
    coclico_ext.max_ = MAX
    coclico_ext.linear_gradient = LINEAR_GRADIENT

    # set extra link properties
    extend_links(stac_obj, dimvals.keys())

    # save and limit number of folders
    # TODO: delete commented line below when migrated to catalog.json
    # collection.add_child(stac_obj)
    catalog.add_child(stac_obj)

    stac_obj.normalize_hrefs(
        os.path.join(rel_root, STAC_DIR, STAC_COLLECTION_NAME), strategy=layout
    )

    # TODO: delete commented lines below when migrated to catalog.json
    # collection.save( catalog_type=CatalogType.SELF_CONTAINED,
    #     dest_href=os.path.join(rel_root, STAC_DIR),
    #     stac_io=IO(),
    # )

    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(rel_root, STAC_DIR),
        # dest_href=str(tmp_dir),
        stac_io=IO(),
    )
