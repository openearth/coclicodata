import datetime
import os
import pathlib
import sys
from re import S, template

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from typing import List, Mapping, Optional

import cftime
import numpy as np
import pandas as pd
import pystac
import rasterio
import shapely
import xarray as xr
from datacube.utils.cog import write_cog
from etl import p_drive, rel_root
from pystac import Catalog, CatalogType, Collection, Summaries
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
    get_template_collection,
)


def cftime_to_pdts(t: cftime._cftime) -> pd.Timestamp:
    return pd.Timestamp(
        t.year,
        t.month,
        t.day,
        t.hour,
        t.minute,
        t.second,
        t.microsecond,
    )


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


def itemize(
    da,
    item: pystac.Item,
    blob_name: str,
    asset_roles: list[str] | None = None,
    asset_media_type=pystac.MediaType.COG,
) -> pystac.Item:
    """ """
    import rioxarray  # noqa

    item = item.clone()
    dst_crs = rasterio.crs.CRS.from_epsg(4326)

    bbox = rasterio.warp.transform_bounds(da.rio.crs, dst_crs, *da.rio.bounds())
    geometry = shapely.geometry.mapping(shapely.geometry.box(*bbox))

    item.id = blob_name
    item.geometry = geometry
    item.bbox = bbox
    item.datetime = cftime_to_pdts(da["time"].item()).to_pydatetime()
    # item.datetime = pd.Timestamp(da.coords[time_dim].item()).to_pydatetime()

    ext = pystac.extensions.projection.ProjectionExtension.ext(
        item, add_if_missing=True
    )
    ext.bbox = da.rio.bounds()
    ext.shape = da.shape[-2:]
    ext.epsg = da.rio.crs.to_epsg()
    ext.geometry = shapely.geometry.mapping(shapely.geometry.box(*ext.bbox))
    ext.transform = list(da.rio.transform())[:6]
    ext.add_to(item)

    roles = asset_roles or ["data"]

    href = os.path.join(
        GCS_PROTOCOL, BUCKET_NAME, BUCKET_PROJ, DATASET_FILENAME, blob_name
    )
    # TODO: We need to generalize this `href` somewhat.
    asset = pystac.Asset(
        href=href,
        media_type=asset_media_type,
        roles=roles,
    )

    item.add_asset("data", asset)

    return item


# rename or swap dimension names, the latter in case the name already exists as coordinate
if __name__ == "__main__":

    # hard-coded input params at project level
    GCS_PROTOCOL = "https://storage.googleapis.com"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"

    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "slp"  # name of stac collection
    COLLECTION_TITLE = "AR5 Sea level change projections"
    DATASET_DESCRIPTION = "AR5 Sea level change projections"

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "ar5_slp"
    DATASET_DIR = "18_AR5_SLP_IPCC"

    # define local directories
    home = pathlib.Path().home()
    tmp_dir = home.joinpath("data", "tmp")

    # remote p drive
    coclico_data_dir = p_drive.joinpath("11205479-coclico", "data")

    # use local or remote data dir
    use_local_data = True

    if use_local_data:
        ds_dir = tmp_dir.joinpath(DATASET_DIR)
    else:
        ds_dir = coclico_data_dir.joinpath(DATASET_DIR)

    if not ds_dir.exists():
        raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

    # directory to export result (make if not exists)
    cog_dir = ds_dir.joinpath("cogs")
    cog_dir.mkdir(parents=True, exist_ok=True)

    catalog = Catalog.from_file(os.path.join(rel_root, STAC_DIR, "catalog.json"))

    template_fp = os.path.join(
        rel_root, STAC_DIR, TEMPLATE_COLLECTION, "collection.json"
    )

    # generate collection for dataset
    collection = get_template_collection(
        template_fp=template_fp,
        collection_id=COLLECTION_ID,
        title=COLLECTION_TITLE,
        description=DATASET_DESCRIPTION,
    )

    layout = Layout()

    # the dataset contains three different rcp scenario's
    RCPS = ["26", "45", "85"]
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

        ntimes = ds.dims["time"]
        for ntime in range(ntimes):
            ds2 = ds.copy()
            ds2 = ds2.isel({"time": ntime})

            # extract time boundaries for use in tif naming
            time_bounds = [
                cftime_to_pdts(t).strftime("%Y-%m-%d") for t in ds2.time_bnds.values
            ]
            time_name = "_".join([t for t in time_bounds])

            for var_name in variables:

                # time bounds are extracted, so nv dim can be dropped, as tiff should be 2D or 3D.
                da = ds2[var_name]

                # compose tif name
                fname = time_name + ".tif"
                blob_name = pathlib.Path(rcp_name, var_name, fname)
                outpath = cog_dir.joinpath(blob_name)

                # make parent dir if not exists
                outpath.parent.mkdir(parents=True, exist_ok=True)

                # add time name as scalar variable to tif
                da["time_bnds"] = time_name

                template_item = pystac.Item(
                    "id", None, None, datetime.datetime(2000, 1, 1), {}
                )

                item = itemize(da, template_item, blob_name=str(blob_name))
                collection.add_item(item, strategy=layout)

                # set overwrite is false because tifs should be unique
                # write_cog(da, fname=outpath, overwrite=False)

    # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    collection.summaries = Summaries({})

    # add collection to catalog
    catalog.add_child(collection)

    # normalize the paths
    collection.normalize_hrefs(
        os.path.join(rel_root, STAC_DIR, COLLECTION_ID), strategy=layout
    )

    # save updated catalog
    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(rel_root, STAC_DIR),
        # dest_href=str(tmp_dir),
        stac_io=IO(),
    )
    print("done")
