import json
from copy import deepcopy
from datetime import datetime
from itertools import product
from sre_constants import GROUPREF_EXISTS
from typing import Any, Dict

import zarr
from pystac import Asset, CatalogType, Collection, Item, RelType, Summaries
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable
from pystac.layout import BestPracticesLayoutStrategy
from pystac.stac_io import DefaultStacIO
from pystac.utils import JoinType, join_path_or_url, safe_urlparse
import pystac


class IO(DefaultStacIO):
    """Custom IO to ident our STAC json with 4."""

    # enabling a GitHub Actions compatible Windows created STAC --> i.e. replacing '\\' by '/'
    def _dict_replace_value(self, d, old, new):
        x = {}
        for k, v in d.items():
            if isinstance(v, dict):
                v = self._dict_replace_value(v, old, new)
            elif isinstance(v, list):
                v = self._list_replace_value(v, old, new)
            elif isinstance(v, str):
                v = v.replace(old, new)
            x[k] = v
        return x

    def _list_replace_value(self, l, old, new):
        x = []
        for e in l:
            if isinstance(e, list):
                e = self._list_replace_value(e, old, new)
            elif isinstance(e, dict):
                e = self._dict_replace_value(e, old, new)
            elif isinstance(e, str):
                e = e.replace(old, new)
            x.append(e)
        return x

    def json_dumps(self, json_dict: Dict[str, Any], *args: Any, **kwargs: Any) -> str:
        return json.dumps(
            self._dict_replace_value(json_dict, "\\", "/"), *args, indent=4, **kwargs
        )


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


def get_stac_obj_from_template(
    collection: pystac.Collection,
    template_fn: str,
    variable: str,
) -> pystac.Collection:
    """Deltares CoCliCo STAC Obj from template file.

    # TODO: Dynamic input and more extensive description.

    Args:
        rel_root (pathlib.Path): Relative root (project directory).
        template_fn (str): Template file for STAC Obj.
        variable (str): Variable which is described in the collection.

    Returns:
        pystac.Collection: Template STAC Obj collection.
    """
    datasetid = f"{variable}-mapbox"

    # Get template and set items
    templatedataset = collection.get_child(template_fn)
    stac_obj = templatedataset.full_copy()
    stac_obj.id = datasetid
    stac_obj.title = variable
    stac_obj.description = variable

    # Drop existing items, dimensions and summaries
    # dataset._resolved_objects  # @Maarten, why accessing this hidden attribute?
    stac_obj.set_root(None)
    stac_obj.clear_items()
    stac_obj.assets = {}
    stac_obj.extra_fields = deepcopy(
        stac_obj.extra_fields
    )  # workaround for https://github.com/stac-utils/pystac/issues/787
    stac_obj.summaries = None
    stac_obj.extra_fields.pop("cube:dimensions", None)
    stac_obj.extra_fields.pop("cube:variables", None)
    stac_obj.extra_fields.pop("summaries", None)

    return stac_obj


def gen_mapbox_asset(
    # TODO: default walues for variables  below can be deleted right?
    url="mapbox://global-data-viewer.7677kvzd",
    source="CoastAlRisk_Europe_EESSL_RCP4-c0krjv",
):
    return Asset(
        href=url,
        extra_fields={
            "type": "vector",
            "source": source,
        },
        # TODO: change title for region/
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
    # TODO: add media type?
    return Asset(
        href=url,
        title=f"{variable} zarr root",
        description=(
            f"The root of the {variable} zarr dataset on public Google Cloud Storage."
        ),
        roles=["data", "zarr-root", "gcs"],
    )


def extend_links(collection, dimension_names):
    """Extend Link objects with certain properties
    from the linked item itself."""
    for link in collection.get_links(RelType.ITEM):
        link.resolve_stac_object()
        props = link.extra_fields.setdefault("properties", {})
        for dim in dimension_names:
            value = link.target.properties.get(dim)
            # TODO: if not value:?
            if value is not None:
                props[dim] = value


def gen_default_summaries(groups, license, coords, dims, **kwargs):

    summaries = {
        "groups": groups,
        "license": license,
        "coords": coords,
        "dims": dims,
    }

    # possibly just summaries.update(kwargs)
    for k, v in kwargs.items():
        summaries[k] = v

    return summaries
