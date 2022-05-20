import os
from copy import deepcopy
from itertools import product

from generate import (IO, Layout, extend_links, gen_default_item,
                      gen_default_props, gen_mapbox_asset, gen_zarr_asset)
from pystac import CatalogType, Collection, Summaries
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable

from etl import rel_root
from etl.cloud_services import dataset_from_google_cloud
from etl.extract import get_geojson
from etl.keys import load_env_variables
from etl.stac_utils import (get_cube_dimensions, get_dimdict,
                            get_dimension_combinations, get_stac_summary_keys)


def etienne_code(
    dataset_fn,
    template_fn,
    variable,
    zarr_fn,
    cube_dimensions,
    ds,
    stac_keys,
    local_stac,
):

    # update STAC
    mapbox_url = f"mapbox://global-data-viewer.{dataset_fn}"
    datasetid = f"{variable}-mapbox"

    # Get initial STAC
    collection = Collection.from_file("./current/collection.json")
    # collection.describe()  # display hierarchy

    # Get template and set items
    templatedataset = collection.get_child(template_fn)
    dataset = templatedataset.full_copy()
    dataset.id = datasetid
    dataset.title = variable
    dataset.description = variable

    # Drop existing items, dimensions and summaries
    dataset._resolved_objects
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
    var.unit = ds.attrs.get("units", "-")
    dc_ext.variables = {variable: var}

    # Add summaries
    dimvals = {k: v.values for k, v in cube_dimensions.items() if v.values}
    dataset.summaries = Summaries(summaries=dimvals)

    # Add children
    layout = Layout()
    for values, key in zip(product(*dimvals.values()), stac_keys):
        feature = gen_default_item(f"{variable}-mapbox-{key}")
        feature.add_asset("mapbox", gen_mapbox_asset(mapbox_url, dataset_fn))
        feature.properties = gen_default_props(key=key)
        for (k, v) in zip(dimvals.keys(), values):
            feature.properties[k] = v
        dataset.add_item(feature, strategy=layout)

    # Set extra link properties
    extend_links(dataset, cube_dimensions.keys())

    # Save and limit number of folders
    collection.add_child(dataset)
    dataset.normalize_hrefs(
        os.path.join(local_stac, f"current/{variable}"), strategy=layout
    )
    collection.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(local_stac, "current"),
        stac_io=IO(),
    )


if __name__ == "__main__":

    load_env_variables(env_var_keys=["MAPBOX_ACCESS_TOKEN"])

    # network_dir = coclico_data_dir.joinpath("06_adaptation_jrc")
    # zarr_dir = "cost_and_benefits_of_coastal_adaptation.zarr"
    # dataset_path = network_dir.joinpath(zarr_dir)

    # dataset_to_google_cloud(
    #     ds=dataset_path,
    #     gcs_project="DGDS - I1000482-002",
    #     bucket_name="dgds-data-public",
    #     root_path="coclico",
    #     zarr_name=zarr_dir,
    # )

    # specify input variables
    dataset_fn = "CoastAlRisk_Europe_EESSL.zarr"
    variable = "ssl"
    template = "deltares-coclico-xssl"
    datasetid = f"{variable}-mapbox"

    # google cloud
    bucket_name = "dgds-data-public"
    root_path = "coclico"

    ds = dataset_from_google_cloud(
        bucket_name=bucket_name, root_path=root_path, zarr_store=dataset_fn
    )

    cube_dimensions = get_cube_dimensions(ds, variable="ssl")
    dimension_combinations = get_dimension_combinations(cube_dimensions=cube_dimensions)
    stac_summaries = [get_stac_summary_keys(i) for i in dimension_combinations]
    collection = get_geojson(
        ds, variable="ssl", dimension_combinations=dimension_combinations
    )

    etienne_code(
        dataset_fn=dataset_fn,
        template_fn=template,
        variable=variable,
        zarr_fn=dataset_fn,
        cube_dimensions=cube_dimensions,
        ds=ds,
        stac_keys=stac_summaries,
        local_stac=rel_root,
    )
