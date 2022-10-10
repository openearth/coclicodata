import os
import pathlib
import re
from copy import deepcopy
from itertools import product
from typing import Any, Dict, List, Union

import numpy as np
import pystac
import xarray as xr
from pystac import Collection
from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable


def rm_special_characters(
    ds: xr.Dataset,
    dimensions_to_check: List[str] = [],
    characters: List[str] = [],
) -> xr.Dataset:
    """Remove special characters from coordinate axes.

    Args:
        ds (xr.Dataset): _description_
        dimensions_to_check (List[str  |  None]): _description_
        characters (List[str  |  None]): _description_

    Returns:
        xr.Dataset: _description_
    """

    # datasets are cf compliant, so strings will only be present in coordinate axes
    for coord in ds.coords:
        if coord in dimensions_to_check:
            # only check axes that are strings (those will be in unicodes)
            if ds.coords[coord].dtype.kind == np.dtype("U"):
                # replace characters with empty strings
                values = ds.coords[coord].str.replace(pat=characters, repl="").data
                # use assign coords to preserve attributes of coordinate axis
                ds = ds.assign_coords({coord: (coord, values, ds.coords[coord].attrs)})
    return ds


def filter_characters(v):
    """Remove characters which are difficult to read in frontend from strings."""
    return re.sub("[%]", "", v)


def get_mapbox_item_id(dimdict: Dict[str, Any]) -> str:
    """Join key-values pairs of dictionary by hypen.

    These are used as stac feature item id's for the mapbox layers.

    """

    list_of_key_hyphen_value = [f"{k}-{v}" for k, v in dimdict.items()]
    return "-".join(list_of_key_hyphen_value)


def get_dimension_values(ds, dimensions_to_ignore: List[str]) -> dict:
    """Dataset values per dimensions to dictionary."""

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
