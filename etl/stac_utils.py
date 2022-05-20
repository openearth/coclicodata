from itertools import product

from pystac.extensions.datacube import DatacubeExtension, Dimension, Variable


def get_dimdict(ds, var):

    arr = ds[var]

    # TODO: make function dictionary when list of coclico cf conventions are decided
    if var == "stations":

        dimdict = {
            "type": "stations",
            "extent": [int(arr.values.min()), int(arr.values.max())],
            "unit": "-",
        }

    else:
        dimdict = {
            "type": "temporal",
            "values": arr.values.tolist(),
            "unit": arr.attrs.get("units", "-"),
        }

    return dimdict


def get_cube_dimensions(ds, variable) -> dict:

    dims_ = list(ds[variable].dims)

    # keep only vars that have matching dim with dim shape 1
    # TODO: make list of valid names when coclico cf_conventions are decided
    # vars_ = list(ds.variables)
    # vars_ = [x for x in vars_ if x in dims_]
    # vars_ = [x for x in vars_ if len(ds[x].dims) == 1]
    # vars_.append("stations")

    # TODO: dynamic, not hard coded.
    vars_ = ["scenario", "RP", "stations"]

    cube_dims = {}
    for var in vars_:
        dimdict = get_dimdict(ds, var)
        dim = Dimension.from_dict(dimdict)
        cube_dims[var] = dim
    return cube_dims


def get_stac_summary_keys(dimension_combinations):
    """stac summary keys from dictionary with possible dimension combinations

    Args:
        dimension_combinations (_type_): _description_

    Returns:
        _type_: _description_
    """
    list_of_key_hyphen_value = [f"{k}-{v}" for k, v in dimension_combinations.items()]
    return "-".join(list_of_key_hyphen_value)


def get_dimension_combinations(cube_dimensions):
    """"""

    # unnest dimension values
    dimvals = {k: v.values for k, v in cube_dimensions.items() if v.values}

    # get possible dimension combinations by taking the dot product:
    dimcombs = list(product(*dimvals.values()))

    # store dimcombs in dictionary to keep track of dimension name, e.g,:
    # [{"scenario": "Historical", "RP": 5.0}, ..., {"scenario": "RCP85", "RP": 500}]
    dimcombs = [dict(zip(dimvals.keys(), i)) for i in dimcombs]

    return dimcombs
