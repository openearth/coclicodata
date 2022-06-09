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
    gen_default_item,
    gen_default_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_stac_obj_from_template,
)
from stac.datacube import add_datacube
from stac.deltares_extension import DeltaresExtension
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
)

if __name__ == "__main__":

    # hard-coded input params
    DATASET_FILENAME = "test.zarr"
    VARIABLE = "ssl"
    TEMPLATE = "ssl-mapbox"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_BASENAME = "mapbox://global-data-viewer"
    # TODO: add hard coded variables which will change per dataset (spatial dims etc.)

    # semi hard-coded input params
    gcs_zarr_store = os.path.join("gcs://", BUCKET_NAME, BUCKET_PROJ, DATASET_FILENAME)
    mapbox_url = f"{MAPBOX_BASENAME}.{DATASET_FILENAME}"

    # read data from gcs zarr store
    ds = dataset_from_google_cloud(
        bucket_name=BUCKET_NAME, bucket_proj=BUCKET_PROJ, zarr_filename=DATASET_FILENAME
    )

    # generate pystac collection from stac collection file
    collection = Collection.from_file(
        os.path.join(rel_root, "current", "collection.json")
    )

    # generate stac_obj for dataset
    stac_obj = get_stac_obj_from_template(
        collection, template_fn=TEMPLATE, variable="ssl"
    )

    # add zarr store as asset to stac_obj
    stac_obj.add_asset("data", gen_zarr_asset(VARIABLE, gcs_zarr_store))

    # add datacube dimensions derived from xarray dataset to dataset stac_obj
    stac_obj = add_datacube(
        stac_obj=stac_obj,
        ds=ds,
        x_dimension="longitude",
        y_dimension="latitude",
        temporal_dimension=False,
        additional_dimensions=["RP", "scenario"],
    )

    # generate stac feature keys (strings which will be stac item ids) for mapbox layers
    dimvals = get_dimension_values(ds, dimensions_to_ignore=["stations"])
    dimcombs = get_dimension_dot_product(dimvals)
    # mapbox_item_ids = [get_mapbox_item_id(i) for i in dimcombs]

    # TODO: check can be customized in the layout
    layout = Layout()

    # stac items are generated per additional dimension (non spatial)
    for dimcomb in dimcombs:

        # generate stac item key and add link to asset to the stac item
        item_id = get_mapbox_item_id(dimcomb)
        feature = gen_default_item(f"{VARIABLE}-mapbox-{item_id}")
        feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url, DATASET_FILENAME))

        # TODO: check with Iona which default properties have to be added for frontend
        # TODO: migrate default properties to Deltares stac extensions (otherwise stac validations fails)
        # add default frontend properties to stac items
        props = gen_default_props(key=item_id)
        DeltaresExtension.ext(
            feature, add_if_missing=True, default_static_properties=props
        )

        # add dimension key-value pairs to stac item properties dict
        for k, v in dimcomb.items():
            feature.properties[k] = v

        # add stac item to collection
        stac_obj.add_item(feature, strategy=layout)

    # dict with summaries which is fed into pystac.Summaries and added to stac_obj
    # TODO: improve summary keys/values; these are inspired on xstac.
    summaries = gen_default_summaries(
        groups=["CoCliCo Consortium"],
        license="proprietary",
        coords=list(ds[VARIABLE].coords),
        dims=list(ds[VARIABLE].dims),
        **dimvals,
    )
    stac_obj.summaries = Summaries({})
    # TODO: check if maxcount is required (inpsired on xstac library)
    stac_obj.summaries.maxcount = 50
    for k, v in summaries.items():
        stac_obj.summaries.add(k, v)

    # set extra link properties
    extend_links(stac_obj, dimvals.keys())

    # save and limit number of folders
    collection.add_child(stac_obj)
    stac_obj.normalize_hrefs(
        os.path.join(rel_root, "current", VARIABLE), strategy=layout
    )

    collection.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(rel_root, "temp"),
        stac_io=IO(),
    )
