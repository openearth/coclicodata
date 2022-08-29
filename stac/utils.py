import os
import pathlib
import re
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

    def filter_characters(v):
        """Remove characters difficult to read in frontend from strings."""
        return re.sub("[%]", "", v)

    coords = list(ds.coords)
    dims = list(ds.dims)

    # to be CF compliant dimensions with string values were stored in the coordinates
    # while the dimension values became just a range of values. Here we replace those
    # ranges with the strings from the coordinates.
    dims = [
        (dim[1:] if dim.startswith("n") and (dim[1:] in coords) else dim)
        for dim in dims
    ]

    # some dimensions will not be used for visualization
    dims = [dim for dim in dims if dim not in dimensions_to_ignore]

    # make a dictionary with the values per dimension

    dimvals = {dim: ds[dim].values.tolist() for dim in dims}

    for dim, vals in dimvals.items():
        vals = [filter_characters(v) for v in vals]
        dimvals[dim] = vals

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
