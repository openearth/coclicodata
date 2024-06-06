from copy import deepcopy
from datetime import datetime

import pystac
from pystac import Asset, Collection, RelType


def gen_default_item(name="unique"):
    return pystac.Item(
        id=name,
        datetime=datetime.now(),
        properties={},
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


# TODO: incorporate more items from the metadata templates to be delivered (media_tyoe, citation, doi, author, tags?, long_name?, comment?, crs?) and fix license, providers, spatial_extent and temporal_extent
def get_template_collection(
    template_fp: str,
    collection_id: str,
    title: str,
    description: str,
    keywords: list,
    license: str,
    spatial_extent: list,
    temporal_extent: list,
    providers: list,
    # hosting_platform: str,
) -> pystac.Collection:
    """Deltares CoCliCo STAC Obj from template file.

    # TODO: Dynamic input and more extensive description.

    Args:
        rel_root (pathlib.Path): relative root (project directory).
        template_fn (str): template collection for this stac object.
        variable (str): variable which will be described in this stac collection.

    Returns:
        pystac.Collection or pystac.Catalog: Template STAC Obj collection.
    """
    # datasetid = f"{title}-{hosting_platform}"

    # Get template and set items

    template_collection = Collection.from_file(template_fp)
    collection = template_collection.full_copy()
    # stac_obj.id = f"{title}-{hosting_platform}"
    collection.id = collection_id
    collection.title = title
    collection.description = description
    collection.keywords = keywords
    collection.license = license
    collection.extent.spatial.bbox = spatial_extent
    collection.extent.temporal.interval = temporal_extent
    # collection.providers = providers

    # Drop existing items, dimensions and summaries
    collection.set_root(None)
    collection.clear_items()
    collection.assets = {}
    collection.extra_fields = deepcopy(
        collection.extra_fields
    )  # workaround for https://github.com/stac-utils/pystac/issues/787

    # TODO: check what can be used for stac_obj.summaries = None instead because now it
    # raises AttributeError 'dict' object has no attribute 'is_empty' when no summaries
    # added.
    # stac_obj.summaries = None

    collection.extra_fields.pop("cube:dimensions", None)
    collection.extra_fields.pop("cube:variables", None)
    collection.extra_fields.pop("summaries", None)

    return collection


def gen_mapbox_asset(
    # TODO: default walues for variables  below can be deleted right?
    mapbox_url,
):
    source = mapbox_url.split(".")[-1]
    return Asset(
        href=mapbox_url,
        extra_fields={
            "type": "vector",
            "source": source,
        },
        # TODO: change title for region/
        title="Point locations",
        description="Mapbox url",
        roles=["mapbox"],
    )


def gen_default_collection_props(
    **kwargs,
):
    return {
        **kwargs,
        "deltares:units": "m",
        "deltares:plotSeries": "scenario",
        "deltares:min": 0,
        "deltares:max": 3,
        "deltares:linearGradient": [
            {"color": "hsl(0,90%,80%)", "offset": "0.000%", "opacity": 100},
            {"color": "hsla(55,88%,53%,0.5)", "offset": "50.000%", "opacity": 100},
            {"color": "hsl(110,90%,70%)", "offset": "100.000%", "opacity": 100},
        ],
        # "deltares:linearGradient": list(color_gradient.values()),
    }


def gen_default_item_props(
    key,
    color_properties,
    **kwargs,
):
    return {
        "deltares:stations": "locationid",
        "deltares:type": "circle",
        "deltares:paint": {
            "circle-color": [
                "interpolate",
                ["linear"],
                ["get", key],
                color_properties["min"]["val"],
                color_properties["min"]["hsl"],
                color_properties["mid"]["val"],
                color_properties["mid"]["hsl"],
                color_properties["max"]["val"],
                color_properties["max"]["hsl"],
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
        "deltares:onclick": {},
        **kwargs,
    }


def gen_cog_asset(url):
    return pystac.Asset(
        href=url,
        title=f"Cloud Optimized GeoTIFFs",
        description=f"Cloud Optimized GeoTIFFS",
        roles=["data", "cog", "gcs"],
        media_type=pystac.MediaType.COG,
    )


def gen_zarr_asset(variable: str, url: str) -> pystac.Asset:
    """Create pystac.Asset

    Args:
        variable (str): name of variable which is described in this stac collection.
        url (str): url to zarr dataset as hosted in Google Cloud Storage.

    Returns:
        pystac.Asset: pystac object which describes root zarr dataset as asset.
    """

    # TODO: add media type?
    return pystac.Asset(
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
    raise NotImplementedError(
        "Function not implemented because this causes errors in the frontend."
    )
    # TODO: generate default summaries which are compliant with frontend
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
