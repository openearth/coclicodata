# Example scripts to generate STAC catalog based on a multidimensional array for CoCliCo.

import json
from copy import deepcopy
from datetime import datetime
from itertools import product
from typing import Any, Dict

import zarr
from pystac import Asset, CatalogType, Collection, Item, Summaries
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable
from pystac.layout import BestPracticesLayoutStrategy
from pystac.stac_io import DefaultStacIO
from pystac.utils import JoinType, join_path_or_url, safe_urlparse


class IO(DefaultStacIO):
    """Custom IO to ident our STAC json with 4."""

    def json_dumps(self, json_dict: Dict[str, Any], *args: Any, **kwargs: Any) -> str:
        return json.dumps(json_dict, *args, indent=4, **kwargs)


class Layout(BestPracticesLayoutStrategy):
    """Custom layout for CoCliCo STAC collections.

    Set the item path to
    variable-mapbox/variable-mapbox-dim-value-dim-value.json
    instead of
    /variable-mapbox-dim-value-dim-value/variable-mapbox-dim-value-dim-value.json
    """

    def get_item_href(self, item, parent_dir) -> str:
        parsed_parent_dir = safe_urlparse(parent_dir)
        join_type = JoinType.from_parsed_uri(parsed_parent_dir)

        custom_id = "-".join(item.id.split("-")[0:2])
        item_root = join_path_or_url(join_type, parent_dir, "{}".format(custom_id))
        return join_path_or_url(join_type, item_root, "{}.json".format(item.id))


layout = Layout()


def gen_default_item(name="unique", **kwargs):
    return Item(
        id=name,
        datetime=datetime.now(),
        properties=None,
        geometry={
            "type": "Polygon",
            "coordinates": [
                [
                    [-180.0, -90.0],
                    [180.0, -90.0],
                    [180.0, 90.0],
                    [-180.0, 90.0],
                    [-180.0, -90.0],
                ]
            ],
        },
        bbox=[-180, -90, 180, 90],
    )


def gen_mapbox_asset(
    url="mapbox://global-data-viewer.7677kvzd",
    source="CoastAlRisk_Europe_EESSL_RCP4-c0krjv",
):
    return Asset(
        href=url,
        extra_fields={
            "type": "vector",
            "source": source,
        },
        title="Point locations",
        description="Mapbox url",
        roles=["mapbox"],
    )


def gen_default_props(
    key="rp_5",
    **kwargs,
):

    return {
        **kwargs,
        "deltares:stations": "locationId",
        "deltares:type": "circle",
        "deltares:paint": {
            "circle-color": [
                "interpolate",
                ["linear"],
                ["get", key],
                -1,
                "hsl(0, 90%, 80%)",
                0,
                "hsla(55, 88%, 53%, 0.15)",
                1,
                "hsl(110, 90%, 80%)",
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
            "circle-stroke-color": "hsl(0, 72%, 100%)",
        },
        "deltares:onClick": {},
    }


def gen_zarr_asset(
    variable="ESL",
    url="gcs://dgds-data-public/coclico/CoastAlRisk_Europe_EESSL.zarr",
):
    return Asset(
        href=url,
        title=f"{variable} zarr root",
        description=f"The root of the {variable} zarr dataset on public Google Cloud Storage.",
        roles=["data", "zarr-root", "gcs"],
    )


def generate_stac():
    """Generate STAC collection specific to CoCliCo.

    Creates a STAC Feature (layer in website) for the cross product
    of the dimensions in the zarr input file. Links to a GeoJSON
    which stores a preview for a single slice at each location.

    Can copy existing catalogs for templating.
    """


if __name__ == "__main__":
    zarr_fn = "gcs://dgds-data-public/coclico/CoastAlRisk_Europe_EESSL.zarr"
    mapbox_url, mapbox_source = "https://", "adsasd"
    template = "deltares-coclico-ssl"
    variable = "elevation"
    datasetid = f"deltares-coclico-{variable}"
    dimensions = ["RP", "scenario"]  # could be automatic

    nddata = zarr.open(zarr_fn)
    # nddata.tree()  # display hierarchy
    cube_dimensions = {}
    for dimension in dimensions:
        dim = nddata[dimension]
        # Only applicable in proper CF convention zarr
        if dimension == "stations":
            dimdict = {
                "type": "stations",
                "extent": [min(dim), max(dim)],
                "unit": "-",
            }
        else:
            dimdict = {
                "type": "temporal",  # to be customized?
                "values": dim[:].tolist(),
                "unit": dim.attrs.get("units", "-"),
            }
        dim = Dimension.from_dict(dimdict)
        cube_dimensions[dimension] = dim

    collection = Collection.from_file("./current/collection.json")
    # collection.describe()  # display hierarchy

    # Get template and set items
    templatedataset = collection.get_child(template)
    dataset = templatedataset.full_copy()
    dataset.id = datasetid
    dataset.title = variable
    dataset.description = variable

    # Drop existing items, dimensions and summaries
    # dataset._resolved_objects
    dataset.normalize_hrefs(f"current/{variable}", strategy=layout)
    dataset.set_root(None)
    dataset.clear_items()
    dataset.assets = {}
    dataset.extra_fields = deepcopy(
        dataset.extra_fields
    )  # workaround for https://github.com/stac-utils/pystac/issues/787
    dataset.summaries = None
    dataset.extra_fields.pop("cube:dimensions", None)
    dataset.extra_fields.pop("cube:variables", None)
    dataset.extra_fields.pop("summaries", None)

    # Add zarr asset
    dataset.add_asset("data", gen_zarr_asset(variable, zarr_fn))

    # Add dimension info
    dc_ext = DatacubeExtension.ext(dataset)
    dc_ext.apply(cube_dimensions)

    var = Variable({})
    var.description = ""
    var.dimensions = list(cube_dimensions.keys())
    var.type = "data"
    var.unit = "m"  # TODO Get this from zarr as well
    dc_ext.variables = {variable: var}

    # Add summaries
    dimvals = {k: v.values for k, v in cube_dimensions.items() if v.values}
    dataset.summaries = Summaries(summaries=dimvals)

    # Add children
    dataset.normalize_hrefs(f"current/{variable}")
    for values in product(*dimvals.values()):
        # TODO Improve key gen and align with geojson generation
        key = "-".join(
            map(lambda x: "-".join(x), zip(dimvals.keys(), map(str, values)))
        )
        feature = gen_default_item(f"{variable}-mapbox-{key}")
        feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url, mapbox_source))
        feature.properties = gen_default_props(key=key)
        for (k, v) in zip(dimvals.keys(), values):
            feature.properties[k] = v
        dataset.add_item(feature, strategy=layout)
        feature.set_self_href(f"../{variable}-mapbox")

    # Save and limit number of folders
    collection.add_child(dataset)
    dataset.set_self_href(f"current/{variable}/collection.json")
    collection.save(
        catalog_type=CatalogType.SELF_CONTAINED, dest_href=f"current", stac_io=IO()
    )
