from typing import Dict, Union

import numpy as np
import pandas as pd
import pystac
import rioxarray
import xarray as xr
from pystac.extensions.datacube import (
    AdditionalDimension,
    DatacubeExtension,
    Dimension,
    DimensionType,
    HorizontalSpatialDimension,
    TemporalDimension,
    Variable,
)
from xstac._xstac import (
    build_horizontal_dimension,
    build_temporal_dimension,
    build_variables,
    maybe_infer_reference_system,
    maybe_infer_step,
)


def build_additional_dimension(ds, name, extent, values, step, reference_system):
    """Additional dimension should be of type datacube type temporal.

    You can distinguish 'Temporal Dimension"from an 'Additional Dimension' by checking
    whether the extent exists and contains strings. So if the 'type' equals 'temporal'
    and 'extent is an array of strings/null, then you have a 'Temporal Dimension' otherwise
    you have an 'Additional Dimension'

    # TODO: include this type checking in the build_temporal_dimension function.

    For more info, see https://github.com/stac-extensions/datacube/issues/

    """
    da = ds[name]

    da_is_str = type(name) == str

    if not da_is_str:
        if step is None:
            # infer the step
            delta = da.diff(name)
            if len(delta) > 1 and (delta[0] == delta[1:]).all():
                step = delta[0].item()
        step = maybe_infer_step(da, step)
    else:
        step = None

    if values is True or da_is_str:
        values = np.asarray(da).tolist()

    elif values is False:
        values = None

    return AdditionalDimension(
        properties=dict(
            extent=extent,
            step=step,
            values=values,
            description=da.attrs.get("long_name"),
            reference_system=reference_system,
            type=DimensionType.TEMPORAL.value,
        )
    )


def add_datacube(
    ds: xr.Dataset,
    stac_obj: pystac.Collection,
    temporal_dimension=None,
    temporal_extent=None,
    temporal_values=False,
    temporal_step=None,
    x_dimension=None,
    x_extent=None,
    x_values=False,
    x_step=None,
    y_dimension=None,
    y_extent=None,
    y_values=False,
    y_step=None,
    additional_dimensions=[],
    reference_system=None,
    add_variables=True,
) -> pystac.Collection:
    """
    Add cube stac descriptions at collection level.

    Snippet is adopted from xstac._xstac

    """

    dimensions = {}

    if temporal_dimension is not False:

        # convert time formatted year ([%Y]) to datetime. Without this conversion build_temporal_dimension
        # from xstac will interpret the time integer as 1970-01-01 00:00:00.000002015
        if ds[temporal_dimension].dtype.kind in np.typecodes["AllInteger"]:
            time_values = pd.to_datetime(ds[temporal_dimension].values, format="%Y")
            ds = ds.assign_coords(
                {
                    temporal_dimension: (
                        temporal_dimension,
                        time_values,
                        ds[temporal_dimension].attrs,
                    )
                }
            )

        dimensions[temporal_dimension] = build_temporal_dimension(
            ds, temporal_dimension, temporal_extent, temporal_values, temporal_step
        )

    if x_dimension:

        dimensions[x_dimension] = build_horizontal_dimension(
            ds,
            x_dimension,
            "x",
            x_extent,
            x_values,
            x_step,
            reference_system=reference_system,
        )

    if y_dimension:
        dimensions[y_dimension] = build_horizontal_dimension(
            ds,
            y_dimension,
            "y",
            y_extent,
            y_values,
            y_step,
            reference_system=reference_system,
        )

    for additional_dimension in additional_dimensions:

        dimensions[additional_dimension] = build_additional_dimension(
            ds,
            additional_dimension,
            extent=None,
            values=True,
            step=None,
            reference_system=reference_system,
        )

    variables = build_variables(ds)

    ext = DatacubeExtension.ext(stac_obj, add_if_missing=True)

    ext.dimensions = dimensions
    # doesn't have a setter: https://github.com/stac-utils/pystac/issues/681
    # ext.variables = variables
    ext.properties["cube:variables"] = {k: v.properties for k, v in variables.items()}

    # remove unset values, otherwise we might hit bizare jsonschema issues
    # when validating
    for obj in ["cube:variables", "cube:dimensions"]:
        for var in ext.properties[obj]:
            for k, v in list(ext.properties[obj][var].items()):
                if v is None:
                    del ext.properties[obj][var][k]
    return stac_obj
