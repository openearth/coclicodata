from typing import Any, Dict, Generic, List, Optional, TypeVar, Union, cast

import pystac
from pystac.extensions.base import ExtensionManagementMixin, PropertiesExtension

T = TypeVar("T", pystac.Collection, pystac.Item, pystac.Asset)

# host schema at a server, for example:
SCHEMA_URI: str = "https://coclicoservices.eu/coclico-stac-extension/v1.0.0/schema.json"


# TODO: property getters/setters per property. Props below are not used yet.
PREFIX: str = "deltares:"
# list of properties which can be added by the extension
STATIONS_PROP: str = PREFIX + "stations"
TYPE_PROP: str = PREFIX + "type"
PAINT_PROP: str = PREFIX + "paint"
ONCLICK_PROP: str = PREFIX + "onclick"


class CoclicoExtension(
    Generic[T],
    PropertiesExtension,
    ExtensionManagementMixin[Union[pystac.Collection, pystac.Item]],
):
    """An abstract class that can be used to extend the properties of a
    :class:`~pystac.Collection`, :class:`~pystac.Item`, or :class:`~pystac.Asset` with
    properties from the :stac-ext:`CoCliCo Extension <coclico>`.


    """

    def apply(self) -> None:
        pass

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
