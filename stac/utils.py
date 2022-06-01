import os
import pathlib
from copy import deepcopy
from itertools import product
from typing import Any, Dict, List

import pystac
from pystac import Collection
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable


def get_mapbox_item_id(dimdict: Dict[str, Any]) -> str:
    """Join key-values pairs of dictionary by hypen.

    These are used as stac feature item id's for the mapbox layers.

    """
    list_of_key_hyphen_value = [f"{k}-{v}" for k, v in dimdict.items()]
    return "-".join(list_of_key_hyphen_value)


def get_dimension_values(ds, dimensions_to_ignore: List[str]) -> dict:
    """Dataset values per dimensions to dictionary."""

    # keep only dimensions that are not spatial (specified in ignore list)
    dimensions = dict(ds.dims)
    dimensions = {k: v for k, v in dimensions.items() if k not in dimensions_to_ignore}
    # [dimensions.pop(key, None) for key in dimensions_to_ignore]

    # key-value pairs of the dimension (key) with its unique values (values)
    dimvals = {dim: ds[dim].values.tolist() for dim in dimensions}
    return dimvals


def get_dimension_dot_product(dimension_values: Dict) -> list:
    """Dot product of (non-spatial) dimensions stored as key:value pairs.

    List of dictionaries with key-value pairs of all dimension combinations. These
    dictionaries are used to derive the feature id's of the stac with mapbox layer id's.

    For CoCliCo STAC use case, spatial dimensions are typically ignored.

    """

    # get all possible dimension combinations by taking the dot product:
    dimcombs = list(product(*dimension_values.values()))

    # store dimcombs in dictionary to keep track of dimension name, e.g,:
    # [{"scenario": "Historical", "RP": 5.0}, ..., {"scenario": "RCP85", "RP": 500}]
    dimcombs = [dict(zip(dimension_values.keys(), i)) for i in dimcombs]
    return dimcombs
