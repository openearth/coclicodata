import os
from datetime import datetime, timedelta
from pprint import pprint
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import pystac
from etl import rel_root
from pystac.extensions.base import ExtensionManagementMixin, PropertiesExtension
from pystac.utils import (
    StringEnum,
    datetime_to_str,
    get_required,
    map_opt,
    str_to_datetime,
)

from stac.blueprint import gen_default_props

SCHEMA_URI: str = "https://example.com/image-order/v1.0.0/schema.json"
PREFIX: str = "deltares:"

STATIONS_PROP: str = PREFIX + "stations"
TYPE_PROP: str = PREFIX + "type"
PAINT_PROP: str = PREFIX + "paint"
ONCLICK_PROP: str = PREFIX + "onclick"


class DeltaresExtension(
    PropertiesExtension, ExtensionManagementMixin[Union[pystac.Item, pystac.Collection]]
):
    """
    Add static frontend properties to item using this Deltares extension.

    #TODO: Define schema
    #TODO: setter/getter per property

    """

    def __init__(self, item: pystac.Item, default_static_settings: Dict):
        self.item = item

        # TODO: check if this is in line with pystac guidelines
        # add properties dictionary if not exists
        if not item.properties:
            item.properties = {}
        self.properties = item.properties

        # TODO: refactor to setter/getter per property
        # add default visualization settings to properties dictionary
        for k, v in default_static_settings.items():
            self.properties[k] = v

    def apply(self) -> None:
        pass

    @classmethod
    def get_schema_uri(cls) -> str:
        return SCHEMA_URI

    @classmethod
    def ext(
        cls,
        obj: pystac.Item,
        add_if_missing: bool = False,
        default_static_properties={},
    ) -> "DeltaresExtension":
        if isinstance(obj, pystac.Item):
            cls.validate_has_extension(obj, add_if_missing)
            return DeltaresExtension(obj, default_static_properties)
        else:
            raise pystac.ExtensionTypeError(
                f"DeltaresExtension does not apply to type '{type(obj).__name__}'"
            )


def add_deltares_properties(stac_obj: pystac.Item) -> pystac.Item:
    """Add deltares properties to stac."""

    default_properties = gen_default_props(key="supertester")

    DeltaresExtension.ext(
        stac_obj, add_if_missing=True, default_static_properties=default_properties
    )

    return stac_obj


if __name__ == "__main__":

    item_fp = os.path.join(
        rel_root,
        "temp",
        "ssl",
        "ssl-mapbox",
        "ssl-mapbox-RP-5.0-scenario-Historical.json",
    )
    item = pystac.read_file(item_fp)
    item = add_deltares_properties(item)
