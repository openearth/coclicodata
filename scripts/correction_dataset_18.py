import pathlib
import sys

import numpy as np
import pandas as pd
import rioxarray as rio
import xarray as xr

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from etl import p_drive
from etl.extract import clear_zarr_information

if __name__ == "__main__":

    fpath = p_drive.joinpath(
        "11205479-coclico", "data", "18_AR5_SLP_IPCC", "total-ens-slr.zarr"
    )
    ds = xr.open_zarr(fpath)

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

    ds["ensemble"] = np.array(
        [s.strip() for s in ds["ensemble"].astype(str).values], dtype="S"
    )

    ds = ds.rio.write_crs(ds.attrs["crs"])

    # this step is only required when starting from zarr store. If data is loaded
    # from netcdf this doesn't have to be included.
    ds = clear_zarr_information(ds)

    zarr_fp = pathlib.Path.home().joinpath("ddata", "tmp", "global_slr_ar5.zarr")
    ds.to_zarr(zarr_fp, mode="w")
