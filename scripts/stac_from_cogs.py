from __future__ import annotations

import datetime
import itertools
import operator
import os
import pathlib
from typing import List, Mapping, Optional

import datacube
import fsspec
import numpy as np
import pandas as pd
import pystac
import rasterio.warp
import shapely.geometry
import xarray as xr
from datacube.utils.cog import write_cog
from etl import p_drive, rel_root
from etl.cloud_services import dataset_from_google_cloud
from etl.extract import get_mapbox_url, zero_terminated_bytes_as_str
from pystac import CatalogType, Collection, Summaries
from stac.blueprint import (
    IO,
    Layout,
    extend_links,
    gen_default_collection_props,
    gen_default_item,
    gen_default_item_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_stac_obj_from_template,
)
from stac.coclico_extension import CoclicoExtension
from stac.datacube import add_datacube
from stac.utils import (
    get_dimension_dot_product,
    get_dimension_values,
    get_mapbox_item_id,
)


def make_cf_compliant(ds: xr.Dataset) -> xr.Dataset:

    # TODO: check with etienne if nv is also used for time bounds
    ds = ds.rename_dims({"ens": "nensemble", "bnds": "nv"})  # nv = number of vertices

    ds = ds.rename_vars({"modelname": "ensemble"})

    # # set some data variables to coordinates to avoid duplication of dimensions in later stage
    ds = ds.set_coords(["ensemble", "time_bnds"])

    # TODO: check with Etienne why this is required
    ds.time_bnds.encoding[
        "_FillValue"
    ] = None  # xarray sets _FillValue automatically to None for float types, prevent this when needed

    # TODO: check with Etienne if equal dimensions for ensembles are also necessary for cog's - I don't think so.
    # code can be found in notebook file.

    # remove extra spaces in model names and use the updated values as coordinate axis for ensemble
    model_names = np.array(
        [s.strip() for s in ds["ensemble"].astype(str).values], dtype="S"
    )
    ds = ds.assign_coords(ensemble=("nensemble", model_names))

    # this long name is copied from netcdf description
    ds["ensemble"].attrs[
        "long_name"
    ] = "Model names in the same order as in totslr_ens var"

    # add some extra attributes (found at https://www.cen.uni-hamburg.de/en/icdc/data/ocean/ar5-slr.html#zugang)
    ds.attrs["title"] = "Sea level rise from AR5"
    ds.attrs["institution"] = "Institute of Oceanography / CEN / University of Hamburg"
    ds.attrs["comment"] = (
        "Here are the files which contain the ocean and ice components, sums and"
        " uncertainties as used in preparing the IPCC AR5 report (2014), with some"
        " slight modifications.  One small choice I made here was to combine the ocean"
        " and inverse barometer effect into one field, both for the mean and the"
        " uncertainty.  I also have provided better smoothed maps for the *time series*"
        " (the 20-mean-difference maps are the same as in the report).  This actually"
        " shouldn't be the cause for any difference in the report figures, as I didn't"
        " use this field for anything but the coastal stations in Fig. 13.23, and they"
        " have the same interpolation scheme at the coast now, just a better"
        " interpolation scheme in the open ocean (bilinear; not shown in any figure in"
        " the report). "
        "\n"
        "One thing to note: I made a choice as to how to provide the 5%"
        " and 95% (upper and lower 90 %% confidence interval) uncertainty estimates for"
        " the various fields.  I have provided the maps of these similar to the way"
        " Jonathan Gregory provided the time series to me, as the individual component"
        " upper and lower bounds. However, to combine these errors in the same way as"
        " in the report, you will need to take the difference between the upper bound"
        " and the middle value (for combining the upper uncertainty total estimate) or"
        " the lower bound and middle value (for combining the lower uncertainty total"
        " estimate), and use the formula shown in the Supplementary Material for"
        " Chapter 13 of the AR5 (SM13) - minus the IBE which is combined with the ocean"
        " field here."
    )
    ds.attrs["references"] = (
        "Chapter 13 paper: Church, J. A., P. Clark, A. Cazenave, J. Gregory, S."
        " Jevrejeva, A. Levermann, M. Merrifield, G. Milne, R.S.Nerem, P. Nunn, A."
        " Payne, W. Pfeffer, D. Stammer, and A. Unnikrishnan (2013), Sea level change,"
        " in Climate Change 2013: The Physical Science Basis, edited by T. F. Stocker,"
        " D. Qin, G.-K. Plattner, M. Tignor, S. Allen, J. Boschung, A. Nauels, Y. Xia,"
        " V. Bex, and P. Midgley, Cambridge University Press, Cambridge, UK and New"
        " York, NY. USA."
    )

    return ds


if __name__ == "__main__":
    # hard-coded input params at project level
    GCS_PROTOCOL = "https://storage.googleapis.com"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    MAPBOX_PROJ = "global-data-viewer"
    TEMPLATE = "template-mapbox"  # stac template for dataset collection
    STAC_DIR = "current"

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "global_slr_ar5.zarr"
    STAC_COLLECTION_NAME = "slr"  # name of stac collection
    VARIABLES = [
        "hierr",
        "loerr",
        "totslr",
        "totslr_ens",
    ]  # xarray variables in dataset
    X_DIMENSION = "lon"  # False, None or str; spatial lon dim used by datacube
    Y_DIMENSION = "lat"  # False, None or str; spatial lat dim ""
    TEMPORAL_DIMENSION = "time"  # False, None or str; temporal ""
    ADDITIONAL_DIMENSIONS = [
        "ensemble",
    ]  # False, None, or str; additional dims ""
    DIMENSIONS_TO_IGNORE = [
        "lon",
        "lat",
        "time",
        "time_bnds",
        "nensemble",
        "nscenarios",
        "nv",
    ]  # List of str; dims ignored by datacube

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "ar5_slp"
    STAC_COLLECTION_NAME = "slp"  # name of stac collection

    # define local directories
    home = pathlib.Path().home()
    tmp_dir = home.joinpath("data", "tmp")

    # remote p drive
    coclico_data_dir = p_drive.joinpath("11205479-coclico", "data")

    # use local or remote data dir
    use_local_data = True
    ds_dirname = "18_AR5_SLP_IPCC"

    if use_local_data:
        ds_dir = tmp_dir.joinpath(ds_dirname)
    else:
        ds_dir = coclico_data_dir.joinpath(ds_dirname)

    if not ds_dir.exists():
        raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

    # directory to export result (make if not exists)
    cog_dir = ds_dir.joinpath("cogs")
    cog_dir.mkdir(parents=True, exist_ok=True)

    RCPS = ["26", "45", "85"]

    scenarios = [f"RCP{i}" for i in RCPS]

    for rcp in RCPS:

        # load dataset and do some pre-processsing
        ds_fp = ds_dir.joinpath(f"total-ens-slr-{rcp}-5.nc")
        ds = xr.open_dataset(ds_fp)

        # format dataset based upon notebooks/18_SLR_AR5.ipynb
        ds = make_cf_compliant(ds)

        # # convert cf noleap yrs to datetimei
        # ds["time"] = ds.indexes["time"].to_datetimeindex()

        # add crs and spatial dims
        ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
        if not ds.rio.crs:
            ds = ds.rio.write_crs("EPSG:4326")

        # format rcp name for filenaming
        rcp_name = f"rcp={rcp}"

        # extract list of data variables
        variables = set(ds.variables) - set(ds.dims) - set(ds.coords)

        ds["ensemble"] = ds.coords["ensemble"].astype(str)
        # generate pystac collection from stac collection file
        collection = Collection.from_file(
            os.path.join(rel_root, STAC_DIR, "collection.json")
        )

        # generate stac_obj for dataset
        stac_obj = get_stac_obj_from_template(
            collection,
            template_fn=TEMPLATE,
            title=STAC_COLLECTION_NAME,
            description=DATASET_FILENAME,
            hosting_platform="gcs",
        )

        layout = Layout()

        # generate stac feature keys (strings which will be stac item ids) for mapbox layers
        dimvals = get_dimension_values(ds, dimensions_to_ignore=DIMENSIONS_TO_IGNORE)
        dimcombs = get_dimension_dot_product(dimvals)

        # add datacube dimensions derived from xarray dataset to dataset stac_obj
        stac_obj = add_datacube(
            stac_obj=stac_obj,
            ds=ds,
            x_dimension=X_DIMENSION,
            y_dimension=Y_DIMENSION,
            temporal_dimension=TEMPORAL_DIMENSION,
            additional_dimensions=ADDITIONAL_DIMENSIONS,
        )

    print("done")
