import os
import pathlib
import sys

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from etl import rel_root
from etl.cloud_services import dataset_from_google_cloud
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
    MAPBOX_BASENAME = "mapbox://global-data-viewer"
    TEMPLATE = "ssl-mapbox"  # stac template for dataset collection
    STAC_DIR = "temp"

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "CoastAlRisk_Europe_EESSL.zarr"
    STAC_COLLECTION_NAME = "ssl"  # name of stac collection
    VARIABLES = ["ssl"]  # xarray variables in dataset
    X_DIMENSION = "longitude"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "latitude"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = False  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = [
        "RP",
        "scenario",
    ]  # False, None, or str; additional dims ""
    DIMENSIONS_TO_IGNORE = ["stations"]  # List of str; dims ignored by datacube

    # hard-coded frontend properties
    # TODO migrate to deltares stac extension, see next todo comment below.
    COLOR_PROPERTIES = {
        "min": {
            "val": 0,
            "hsl": "hsl(110,90%,80%)",
        },
        "mid": {
            "val": 1.5,
            "hsl": "hsla(55, 88%, 53%, 0.5)",
        },
        "max": {
            "val": 3.0,
            "hsl": "hsl(0, 90%, 70%)",
        },
    }
    # TODO: will be implmented when migrating to Deltares stac extansion. Now it doesn't
    # work because the list has to be implemented with pystac string enum class see
    # https://pystac.readthedocs.io/en/stable/tutorials/adding-new-and-custom-extensions.html
    # LINEAR_GRADIENT = [
    #     {"color": COLOR_PROPERTIES["min"]["hsl"], "offset": "0.000%", "opacity": 100},
    #     {"color": COLOR_PROPERTIES["mid"]["hsl"], "offset": "50.000%", "opacity": 100},
    #     {"color": COLOR_PROPERTIES["max"]["hsl"], "offset": "100.000%", "opacity": 100},
    # ]

    # semi hard-coded input params
    gcs_zarr_store = os.path.join("gcs://", BUCKET_NAME, BUCKET_PROJ, DATASET_FILENAME)
    mapbox_url = f"{MAPBOX_BASENAME}.{DATASET_FILENAME}"

    # read data from gcs zarr store
    ds = dataset_from_google_cloud(
        bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    )

    # generate pystac collection from stac collection file
    collection = Collection.from_file(
        os.path.join(rel_root, STAC_DIR, "collection.json")
    )

    # generate stac_obj for dataset
    stac_obj = get_stac_obj_from_template(
        collection, template_fn=TEMPLATE, variable=STAC_COLLECTION_NAME
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
        stac_obj.add_asset("data", gen_zarr_asset(var, gcs_zarr_store))

        # stac items are generated per AdditionalDimension (non spatial)
        for dimcomb in dimcombs:

            # generate stac item key and add link to asset to the stac item
            item_id = get_mapbox_item_id(dimcomb)
            feature = gen_default_item(f"{var}-mapbox-{item_id}")
            feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url, DATASET_FILENAME))

            # TODO: properties/setters for coclico stac extension (see coclico_extension.py)
            # This calls ItemCoclicoExtension and links CoclicoExtension to the stac item
            coclico_ext = CoclicoExtension.ext(feature, add_if_missing=True)

            # generate default frontend properties and add to stac items as properties
            item_props = gen_default_item_props(
                key=item_id, color_properties=COLOR_PROPERTIES
            )
            for k, v in item_props.items():
                coclico_ext.properties[k] = v

            # TODO: include this in our datacube?
            # add dimension key-value pairs to stac item properties dict
            for k, v in dimcomb.items():
                feature.properties[k] = v

            # add stac item to collection
            stac_obj.add_item(feature, strategy=layout)

    # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    stac_obj.summaries = Summaries({})
    # TODO: check if maxcount is required (inpsired on xstac library)
    # stac_obj.summaries.maxcount = 50
    for k, v in dimvals.items():
        stac_obj.summaries.add(k, v)

    # this calls CollectionCoclicoExtension since stac_obj==pystac.Collection
    coclico_ext = CoclicoExtension.ext(stac_obj, add_if_missing=True)

    # generate default properties and add to collection extension properties. The
    # properties attribute of this extension is linked to the extra_fields attribute of
    # the stac collection.
    collection_props = gen_default_collection_props()
    for k, v in collection_props.items():
        coclico_ext.properties[k] = v

    # set extra link properties
    extend_links(stac_obj, dimvals.keys())

    # save and limit number of folders
    collection.add_child(stac_obj)
    stac_obj.normalize_hrefs(
        os.path.join(rel_root, STAC_DIR, STAC_COLLECTION_NAME), strategy=layout
    )

    collection.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(rel_root, STAC_DIR),
        stac_io=IO(),
    )
