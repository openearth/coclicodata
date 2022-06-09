import os
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union, cast

import pystac
from etl import rel_root
from pystac.extensions.base import ExtensionManagementMixin, PropertiesExtension

from stac.blueprint import gen_default_item_props

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
                f"Datacube extension does not apply to type '{type(obj).__name__}'"
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


# class DeltaresExtension(
#     PropertiesExtension, ExtensionManagementMixin[Union[pystac.Item, pystac.Collection]]
# ):
#     """
#     Add static frontend properties to item using this Deltares extension.

#     #TODO: Define schema
#     #TODO: setter/getter per property

#     """

#     def __init__(
#         self, item: Union[pystac.Item, pystac.Collection], default_static_settings: Dict
#     ):
#         self.item = item

#         # TODO: check if this is in line with pystac guidelines
#         # add properties dictionary if not exists
#         if not item.properties:
#             item.properties = {}
#         self.properties = item.properties

#         # TODO: refactor to setter/getter per property
#         # add default visualization settings to properties dictionary
#         for k, v in default_static_settings.items():
#             self.properties[k] = v

#     def apply(self) -> None:
#         pass

#     @classmethod
#     def get_schema_uri(cls) -> str:
#         return SCHEMA_URI

#     @classmethod
#     def ext(
#         cls,
#         obj: pystac.Item,
#         add_if_missing: bool = False,
#         default_static_properties={},
#     ) -> "DeltaresExtension":
#         if isinstance(obj, pystac.Item):
#             cls.validate_has_extension(obj, add_if_missing)
#             return DeltaresExtension(obj, default_static_properties)
#         else:
#             raise pystac.ExtensionTypeError(
#                 f"DeltaresExtension does not apply to type '{type(obj).__name__}'"
#             )


# def add_deltares_properties(stac_obj: pystac.Item) -> pystac.Item:
#     """Add deltares properties to stac."""

#     default_properties = gen_default_props(key="supertester")

#     DeltaresExtension.ext(
#         stac_obj, add_if_missing=True, default_static_properties=default_properties
#     )

#     return stac_obj


if __name__ == "__main__":

    item_fp = os.path.join(
        rel_root,
        "temp",
        "ssl",
        "ssl-mapbox",
        "ssl-mapbox-RP-5.0-scenario-Historical.json",
    )
    item = pystac.read_file(item_fp)
