import json
from datetime import datetime, timedelta
from pprint import pprint
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union, cast
from uuid import uuid4

import pystac
from pystac.extensions.base import (ExtensionManagementMixin,
                                    PropertiesExtension)
from pystac.utils import (StringEnum, datetime_to_str, get_required, map_opt,
                          str_to_datetime)

T = TypeVar("T", pystac.Collection, pystac.Item, pystac.Asset)

# host schema at a server, for example:
SCHEMA_URI: str = "https://coclicoservices.eu/coclico-stac-extension/v1.0.0/schema.json"


# TODO: property getters/setters per property. Props below are not used yet.
PREFIX: str = "deltares:"

# list of properties that are added at item level
ITEM_KEY_PROP: str = PREFIX + "item_key"
STATIONS_PROP: str = PREFIX + "stations"
TYPE_PROP: str = PREFIX + "type"
PAINT_PROP: str = PREFIX + "paint"
ON_CLICK_PROP: str = PREFIX + "onclick"

# list of properties that are added at collection level
UNITS_PROP: str = "units"
PLOTSERIES_PROP: str = "plotSeries"
MIN_PROP: str = PREFIX + "min"
MAX_PROP: str = PREFIX + "max"
LINEAR_GRADIENT_PROP: str = PREFIX + "linearGradient"
class OrderEventType(StringEnum):
    SUBMITTED = "submitted"
    STARTED_PROCESSING = "started_processing"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Paint:
    properties: Dict[str, Any]

    def __init__(self, properties: Dict[str, Any]) -> None:
        self.properties = properties

    @property
    def item_key(self) -> str:
        return get_required(
            self.properties.get("item_key"),
            self,
            "item_key"
        )

    @item_key.setter
    def item_key(self, v: str) -> None:
        self.properties["type"] = str(v)

    
    @property
    def paint(self) -> Optional[Dict[str, Any]]:
            get_required(
                self.properties.get("paint"),
                self,
                "paint"
            )

    @paint.setter
    def paint(self, v: Dict[str, Any]) -> None:
        self.properties["paint"] = {
                "circle-color": [
                    "interpolate",
                    ["linear"],
                    ["get", self.item_key],
                    v["min_value"],
                    v["min_hsl"],
                    v["mid_value"],
                    v["mid_hsl"],
                    v["max_value"],
                    v["max_hsl"],
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

    def __repr__(self) -> str:
        return "<OrderEvent " \
            f"item_key={self.item_key} > " 

    def apply(
        self,
        item_key: str,
        paint: dict,
    ) -> None:
        self.item_key = item_key
        self.paint = paint

    @classmethod
    def create(
        cls,
        item_key: str,
        paint: dict,
    ) -> "Paint":
        p = cls({})
        p.apply(
            item_key=item_key,
            paint=paint
        )
        return p

    def to_dict(self) -> Dict[str, Any]:
        return self.properties

class CoclicoExtension(
    Generic[T],
    PropertiesExtension,
    ExtensionManagementMixin[Union[pystac.Collection, pystac.Item]],
):
    """An abstract class that can be used to extend the properties of a
    :class:`~pystac.Collection`, :class:`~pystac.Item`, or :class:`~pystac.Asset` with
    properties from the :stac-ext:`CoCliCo Extension <coclico>`.


    """

    def apply(
        self,
        item_key: Optional[str] = None,
        paint: Optional[Dict[str, Any]] = None,
        stations: Optional[str] = None,
        type_: Optional[str] = None,
        on_click: Optional[Dict[str, Any]] = None,
        units: Optional[str] = None,
        min_: Optional[int] = None,
        max_: Optional[int] = None,
        linear_gradient: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.item_key = item_key
        self.paint = paint
        self.stations = stations
        self.type_ = type_
        self.on_click = on_click
        self.units = units
        self.min_ = min_
        self.max_ = max_
        self.linear_gradient = linear_gradient

    @property
    def item_key(self) -> Optional[str]:
        return self._get_property(ITEM_KEY_PROP, str)

    @item_key.setter
    def item_key(self, v: Optional[str]) -> None:
        self._set_property(ITEM_KEY_PROP, v)

    @property
    def paint(self) -> Optional[Dict[str, Any]]:
        return self._get_property(PAINT_PROP, Dict[str, Any])

    @paint.setter
    def paint(self, v: Optional[Dict[str, Any]]) -> None:
        if v is not None:
            v = {
                "circle-color": [
                    "interpolate",
                    ["linear"],
                    ["get", self.item_key],
                    v["min_value"],
                    v["min_hsl"],
                    v["mid_value"],
                    v["mid_hsl"],
                    v["max_value"],
                    v["max_hsl"],
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

        self._set_property(PAINT_PROP, v)

    @property
    def stations(self) -> Optional[str]:
        return self._get_property(STATIONS_PROP, str)

    @stations.setter
    def stations(self, v: Optional[str]) -> None:
        self._set_property(STATIONS_PROP, v)

    @property
    def type_(self) -> Optional[str]:
        return self._get_property(TYPE_PROP, str)

    @type_.setter
    def type_(self, v: Optional[str]) -> None:
        self._set_property(TYPE_PROP, v)

    @property
    def on_click(self) -> Optional[Dict[str, Any]]:
        return self._get_property(ON_CLICK_PROP, Dict[str, Any])

    @on_click.setter
    def on_click(self, v: Optional[Dict[str, Any]]) -> None:
        self._set_property(ON_CLICK_PROP, v)

    @property
    def units(self) -> Optional[str]:
        return self._get_property(UNITS_PROP, str)

    @units.setter
    def units(self, v: Optional[str]) -> None:
        self._set_property(UNITS_PROP, v)

    @property
    def min_(self) -> Optional[int]:
        return self._get_property(MIN_PROP, int)

    @min_.setter
    def min_(self, v: Optional[int]) -> None:
        self._set_property(MIN_PROP, v)

    @property
    def max_(self) -> Optional[int]:
        return self._get_property(MAX_PROP, int)

    @max_.setter
    def max_(self, v: Optional[int]) -> None:
        self._set_property(MAX_PROP, v)

    @property
    def linear_gradient(self) -> Optional[List[Dict[str, Any]]]:
        return self._get_property(LINEAR_GRADIENT_PROP, List[Dict[str, Any]])

    @linear_gradient.setter
    def linear_gradient(self, v: Optional[List[Dict[str, Any]]]) -> None:
        self._set_property(LINEAR_GRADIENT_PROP, v)

    @classmethod
    def get_schema_uri(cls) -> str:
        return SCHEMA_URI

    @classmethod
    def ext(cls, obj: T, add_if_missing: bool = False) -> "CoclicoExtension[T]":
        """Extends the given STAC Object with properties from the :stac-ext:`Coclico Extension
         <coclico>`. This extension can be applied to instances of :class:`~pystac.Collection`,
        :class:`~pystac.Item`.

        Adopted from both:
            - https://github.com/stac-utils/pystac/blob/3c5176f178a4345cb50d5dab83f1dab504ed2682/pystac/extensions/datacube.py
            - https://pystac.readthedocs.io/en/stable/api/extensions.html

        Raises:
            pystac.ExtensionTypeError : If an invalid object type is passed.
        """
        if isinstance(obj, pystac.Collection):
            cls.validate_has_extension(obj, add_if_missing)
            return cast(CoclicoExtension[T], CollectionCoclicoExtension(obj))
        if isinstance(obj, pystac.Item):
            cls.validate_has_extension(obj, add_if_missing)
            return cast(CoclicoExtension[T], ItemCoCliCoExtension(obj))
        else:
            raise pystac.ExtensionTypeError(
                f"Coclico extension does not apply to type '{type(obj).__name__}'"
            )


class CollectionCoclicoExtension(CoclicoExtension[pystac.Collection]):
    """A concrete implementation of :class:`CoclicoExtension` on an
    :class:`~pystac.Collection` that extends the properties of the Item to include
    properties defined in the :stac-ext:`Coclico Extension <coclico>`.
    This class should generally not be instantiated directly. Instead, call
    :meth:`CoclicoExtension.ext` on an :class:`~pystac.Collection` to extend it.

    Adopted from both:
        - https://github.com/stac-utils/pystac/blob/3c5176f178a4345cb50d5dab83f1dab504ed2682/pystac/extensions/datacube.py
        - https://pystac.readthedocs.io/en/stable/api/extensions.html


    """

    collection: pystac.Collection
    properties: Dict[str, Any]

    def __init__(self, collection: pystac.Collection):
        self.collection = collection
        self.properties = collection.extra_fields

    def __repr__(self) -> str:
        return "<CollectionCoclicoExtension Collection id={}>".format(
            self.collection.id
        )


class ItemCoCliCoExtension(CoclicoExtension[pystac.Item]):
    """A concrete implementation of :class:`DatacubeExtension` on an
    :class:`~pystac.Item` that extends the properties of the Item to include properties
    defined in the :stac-ext:`Datacube Extension <datacube>`.
    This class should generally not be instantiated directly. Instead, call
    :meth:`DatacubeExtension.ext` on an :class:`~pystac.Item` to extend it.

    Adopted from both:
        - https://github.com/stac-utils/pystac/blob/3c5176f178a4345cb50d5dab83f1dab504ed2682/pystac/extensions/datacube.py
        - https://pystac.readthedocs.io/en/stable/api/extensions.html

    """

    item: pystac.Item
    properties: Dict[str, Any]

    def __init__(self, item: pystac.Item):
        self.item = item
        self.properties = item.properties

    def __repr__(self) -> str:
        return "<ItemCoclicoExtension Item id={}>".format(self.item.id)
