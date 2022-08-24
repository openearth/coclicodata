import pathlib
import sys

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from typing import List, Mapping, Optional

import numpy as np
import pandas as pd
import xarray as xr
from datacube.utils.cog import write_cog
from etl import p_drive

__version__ = "0.0.1"


def name_tif(da: xr.DataArray, prefix: str = "", scenario: str = "") -> str:
    """ """
    time = pd.Timestamp(da.coords["time"].item()).isoformat()

    # store files per timestep in seperate dirs (include validate if exists)
    dirname = pathlib.Path(prefix, f"time={time}")
    dirname.mkdir(parents=True, exist_ok=True)

    if scenario:
        scenario = f"rcp={scenario}"

    fname = "-".join([e for e in [da.name, scenario] if e])

    blob_name = dirname.joinpath(f"{fname}.tif")
    return str(blob_name)


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

    # remove extra spaces in modelnames
    ds["ensemble"] = np.array(
        [s.strip() for s in ds["ensemble"].astype(str).values], dtype="S"
    )

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


# rename or swap dimension names, the latter in case the name already exists as coordinate
if __name__ == "__main__":

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

    BOUNDS = 0
    ENSEMBLE = 1
    TIME = 0
    VARIABLES = ["totslr_ens", "totslr", "loerr", "hierr"]
    RCPS = ["26", "45", "85"]

    def get_data_fp(data_dir, rcp_scenario):
        """Function to get the netcdf dataset fp to also keep track of rcp scenario used."""
        return data_dir.joinpath(f"total-ens-slr-{rcp_scenario}-5.nc")

    for rcp in RCPS:

        ds_fp = get_data_fp(ds_dir, rcp)
        ds = xr.open_dataset(ds_fp)

        # format dataset
        ds = make_cf_compliant(ds)

        # convert cf noleap yrs to datetimei
        ds["time"] = ds.indexes["time"].to_datetimeindex()

        # add crs and spatial dims
        ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
        if not ds.rio.crs:
            ds = ds.rio.write_crs("EPSG:4326")

        ntime = ds.dims["time"]
        ds = ds.sel({"nensemble": ENSEMBLE, "nv": BOUNDS})

        for var in VARIABLES:

            ds_ = ds.copy()
            ds_ = ds[var]

            for i in range(ntime):

                da = ds_.isel(time=i)
                fname = name_tif(da, str(cog_dir), scenario=rcp)

                # set overwrite is false because tifs should be unique
                write_cog(da, fname=fname, overwrite=False)

    print("done!")
