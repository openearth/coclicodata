"""
Module implementing the Coclico Extension for STAC items and collections.

The Coclico Extension is a custom extension to the STAC specification that provides
additional properties tailored to specific use-cases. This module offers utility
methods and classes to apply and retrieve these properties.

"""

from typing import Any, Dict, Generic, List, Optional, TypeVar, Union, cast

import pystac
from pystac.extensions.base import ExtensionManagementMixin, PropertiesExtension

T = TypeVar("T", pystac.Collection, pystac.Item, pystac.Asset)

SCHEMA_URI = "https://raw.githubusercontent.com/openearth/coclicodata/refactor-to-python-package/json-schema/schema.json"

PREFIX: str = "deltares:"

# list of properties that are added at item level
ITEM_KEY_PROP: str = PREFIX + "item_key"
STATIONS_PROP: str = PREFIX + "stations"
TYPE_PROP: str = PREFIX + "type"
PAINT_PROP: str = PREFIX + "paint"
ON_CLICK_PROP: str = PREFIX + "onclick"

# list of properties that are added at collection level
UNITS_PROP: str = PREFIX + "units"
PLOT_SERIES_PROP: str = PREFIX + "plotSeries"
PLOT_X_AXIS_PROP: str = PREFIX + "plotxAxis"
PLOT_TYPE_PROP: str = PREFIX + "plotType"
MIN_PROP: str = PREFIX + "min"
MAX_PROP: str = PREFIX + "max"
LINEAR_GRADIENT_PROP: str = PREFIX + "linearGradient"


class CoclicoExtension(
    Generic[T],
    PropertiesExtension,
    ExtensionManagementMixin[Union[pystac.Collection, pystac.Item]],
):

    """A class extending the properties of STAC Collection, Item, or Asset with Coclico properties."""

    def apply(
        self,
        item_key: Optional[str] = None,
        paint: Optional[Dict[str, Any]] = None,
        stations: Optional[str] = None,
        type_: Optional[str] = None,
        on_click: Optional[Dict[str, Any]] = None,
        units: Optional[str] = None,
        plot_series: Optional[str] = None,
        plot_x_axis: Optional[str] = None,
        plot_type: Optional[str] = None,
        min_: Optional[int] = None,
        max_: Optional[int] = None,
        linear_gradient: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Apply Coclico properties to the STAC item or collection."""
        # these are added at item level
        self.item_key = item_key
        self.paint = paint
        self.stations = stations
        self.type_ = type_
        self.on_click = on_click

        # these are added at collection level
        self.units = units
        self.plot_series = plot_series
        self.plot_x_axis = plot_x_axis
        self.plot_type = plot_type
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
    def plot_series(self) -> Optional[str]:
        return self._get_property(PLOT_SERIES_PROP, str)

    @plot_series.setter
    def plot_series(self, v: Optional[str]) -> None:
        self._set_property(PLOT_SERIES_PROP, v)

    @property
    def plot_x_axis(self) -> Optional[str]:
        return self._get_property(PLOT_X_AXIS_PROP, str)

    @plot_x_axis.setter
    def plot_x_axis(self, v: Optional[str]) -> None:
        self._set_property(PLOT_X_AXIS_PROP, v)

    @property
    def plot_type(self) -> Optional[str]:
        return self._get_property(PLOT_TYPE_PROP, str)

    @plot_type.setter
    def plot_type(self, v: Optional[str]) -> None:
        self._set_property(PLOT_TYPE_PROP, v)

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
        """Retrieve the schema URI for the Coclico properties."""
        return SCHEMA_URI

    @classmethod
    def ext(cls, obj: T, add_if_missing: bool = False) -> "CoclicoExtension[T]":
        """Extend the given STAC Object with the Coclico Extension properties.

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
    """A class extending the properties of a STAC Collection with Coclico properties.

    Adopted from both:
        - https://github.com/stac-utils/pystac/blob/3c5176f178a4345cb50d5dab83f1dab504ed2682/pystac/extensions/datacube.py
        - https://pystac.readthedocs.io/en/stable/api/extensions.html


    """

    collection: pystac.Collection
    properties: Dict[str, Any]

    def __init__(self, collection: pystac.Collection):
        """Initialize the extension for a STAC collection."""
        self.collection = collection
        self.properties = collection.extra_fields

    def __repr__(self) -> str:
        return "<CollectionCoclicoExtension Collection id={}>".format(
            self.collection.id
        )


class ItemCoCliCoExtension(CoclicoExtension[pystac.Item]):
    """A class extending the properties of a STAC Item with Coclico properties.

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
