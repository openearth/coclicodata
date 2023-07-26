import datetime
import os
import pathlib
import sys
from re import S, template
import json

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from typing import List, Mapping, Optional

import cftime
import numpy as np
import pandas as pd
import pystac
import rasterio
import rioxarray as rio
import shapely
import xarray as xr
from datacube.utils.cog import write_cog
from etl import p_drive, rel_root
from pystac import Catalog, CatalogType, Collection, Summaries
from etl.keys import load_google_credentials
from etl.cloud_services import dir_to_google_cloud
from stac.blueprint import (
    IO,
    LayoutCoG,
    extend_links,
    gen_default_collection_props,
    gen_default_item,
    gen_default_item_props,
    gen_default_summaries,
    gen_mapbox_asset,
    gen_zarr_asset,
    get_template_collection,
)
from stac.coclico_extension import CoclicoExtension  # self built stac extension


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


# TODO: move itemize to ETL or stac.blueprint when generalized
def itemize(
    da,
    item: pystac.Item,
    blob_name: str,
    asset_roles: "List[str] | None" = None,  # "" enables Python 3.8 development not to crash: https://github.com/tiangolo/typer/issues/371
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
    item.datetime = pd.Timestamp(
        da["time"].item().decode("utf-8")
    ).to_pydatetime()  # dataset specific
    # item.datetime = cftime_to_pdts(da["time"].item()).to_pydatetime() # dataset specific

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
        GCS_PROTOCOL,
        BUCKET_NAME,
        BUCKET_PROJ,
        metadata["TITLE_ABBREVIATION"],
        blob_name,
    )

    # TODO: We need to generalize this `href` somewhat.
    asset = pystac.Asset(
        href=href,
        media_type=asset_media_type,
        roles=roles,
    )

    item.add_asset("data", asset)

    return item


if __name__ == "__main__":
    # hard-coded input params at project level
    GCS_PROTOCOL = "https://storage.googleapis.com"
    GCS_PROJECT = "DGDS - I1000482-002"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"

    STAC_DIR = "current"
    TEMPLATE_COLLECTION = "template"  # stac template for dataset collection
    COLLECTION_ID = "slp5"  # name of stac collection

    # hard-coded input params which differ per dataset
    METADATA = "metadata_AR5_slp.json"
    DATASET_DIR = "18_AR5_SLP_IPCC"
    CF_FILE = "total-ens-slr_CF.nc"

    # these are added at collection level, determine dashboard graph layout using all items
    PLOT_SERIES = "scenarios"
    PLOT_X_AXIS = "time"
    PLOT_TYPE = "line"
    MIN = 0
    MAX = 3
    LINEAR_GRADIENT = [
        {"color": "hsl(110,90%,80%)", "offset": "0.000%", "opacity": 100},
        {"color": "hsla(55,88%,53%,0.5)", "offset": "50.000%", "opacity": 100},
        {"color": "hsl(0,90%,70%)", "offset": "100.000%", "opacity": 100},
    ]

    # define local directories
    home = pathlib.Path().home()
    tmp_dir = home.joinpath("data", "tmp")
    coclico_data_dir = p_drive.joinpath(
        "11205479-coclico", "FASTTRACK_DATA"
    )  # remote p drive

    # use local or remote data dir
    use_local_data = False

    if use_local_data:
        ds_dir = tmp_dir.joinpath(DATASET_DIR)
    else:
        ds_dir = coclico_data_dir.joinpath(DATASET_DIR)

    if not ds_dir.exists():
        raise FileNotFoundError(f"Data dir does not exist, {str(ds_dir)}")

    # directory to export result
    cog_dirs = ds_dir.joinpath("cogs")

    # load metadata template
    metadata_fp = ds_dir.joinpath(METADATA)
    with open(metadata_fp, "r") as f:
        metadata = json.load(f)

    catalog = Catalog.from_file(os.path.join(rel_root, STAC_DIR, "catalog.json"))

    template_fp = os.path.join(
        rel_root, STAC_DIR, TEMPLATE_COLLECTION, "collection.json"
    )

    # generate collection for dataset
    collection = get_template_collection(
        template_fp=template_fp,
        collection_id=COLLECTION_ID,
        title=metadata["TITLE"],
        description=metadata["SHORT_DESCRIPTION"],
        keywords=metadata["KEYWORDS"],
        license=metadata["LICENSE"],
        # spatial_extent=metadata["SPATIAL_EXTENT"],
        # temporal_extent=metadata["TEMPORAL_EXTENT"],
        # providers=metadata["PROVIDERS"],
    )

    layout = LayoutCoG()

    # open the dataset
    ds_fp = ds_dir.joinpath(CF_FILE)
    ds = xr.open_dataset(ds_fp)

    # loop over gdal / nc folder struct (max depth = 3)
    # NOTE, does not work as we open the geotiff which contains to little information to itemize objects (need dataArrays)
    # for scen_str in os.listdir(cog_dirs):  # search in the scenarios (the highest level)

    #     for var_ens in os.listdir(
    #         cog_dirs.joinpath(scen_str)
    #     ):  # search in the variables / ensembles (the middle level)

    #         for fname in os.listdir(
    #             cog_dirs.joinpath(scen_str, var_ens)
    #         ):  # search in the file name (the lowest level)

    #             blob_name = pathlib.Path(scen_str, var_ens, fname)
    #             outpath = cog_dirs.joinpath(blob_name)
    #             da = rio.open_rasterio(outpath, masked=True)

    # TODO: check what we can generalize and put into a function for temporal CoGs
    # loop over CF compliant NC file, same code as in related .ipynb
    for idx, scen in enumerate(ds["scenarios"].values):
        rcp = scen.decode("utf-8")

        # format rcp name for filenaming
        rcp_name = "rcp=%s" % rcp.strip("RCP")
        print(rcp_name)

        # extract list of data variables
        variables = set(ds.variables) - set(ds.dims) - set(ds.coords)

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
                da = ds2.sel({"nscenarios": idx})[var_name]

                for idv, ens in enumerate(da["ensemble"].values):
                    da2 = da.isel({"ensemble": idv})

                    # add crs and spatial dims
                    da2.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
                    if not da2.rio.crs:
                        da2 = da2.rio.write_crs("EPSG:4326")

                    # reset some variables and attributes
                    da2["time"] = np.array(
                        cftime_to_pdts(da2["time"].item()).strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        dtype="S",
                    )
                    da2["time"].attrs["standard_name"] = "time"
                    da2["time_bnds"] = np.array(time_name, dtype="S")
                    da2["time_bnds"].attrs["long_name"] = "time boundaries"

                    # compose tif name
                    fname = time_name + ".tif"
                    blob_name = pathlib.Path(
                        rcp_name, var_name + "_ens%s" % int(ens), fname
                    )
                    outpath = cog_dirs.joinpath(blob_name)
                    template_item = pystac.Item(
                        "id", None, None, datetime.datetime(2000, 1, 1), {}
                    )

                    item = itemize(da2, template_item, blob_name=str(blob_name))
                    collection.add_item(item, strategy=layout)

    # TODO: use gen_default_summaries() from blueprint.py after making it frontend compliant.
    collection.summaries = Summaries({})

    # this calls CollectionCoclicoExtension since stac_obj==pystac.Collection
    coclico_ext = CoclicoExtension.ext(collection, add_if_missing=True)

    # Add frontend properties defined above to collection extension properties. The
    # properties attribute of this extension is linked to the extra_fields attribute of
    # the stac collection.
    coclico_ext.units = metadata["UNITS"]
    coclico_ext.plot_series = PLOT_SERIES
    coclico_ext.plot_x_axis = PLOT_X_AXIS
    coclico_ext.plot_type = PLOT_TYPE
    coclico_ext.min_ = MIN
    coclico_ext.max_ = MAX
    coclico_ext.linear_gradient = LINEAR_GRADIENT

    # add collection to catalog
    catalog.add_child(collection)

    # normalize the paths
    collection.normalize_hrefs(
        os.path.join(rel_root, STAC_DIR, COLLECTION_ID), strategy=layout
    )

    # save updated catalog to local drive
    catalog.save(
        catalog_type=CatalogType.SELF_CONTAINED,
        dest_href=os.path.join(rel_root, STAC_DIR),
        # dest_href=str(tmp_dir),
        stac_io=IO(),
    )
    print("Done!")

    # upload directory with cogs to google cloud
    load_google_credentials(
        google_token_fp=coclico_data_dir.joinpath("google_credentials.json")
    )

    dir_to_google_cloud(
        dir_path=str(cog_dirs),
        gcs_project=GCS_PROJECT,
        bucket_name=BUCKET_NAME,
        bucket_proj=BUCKET_PROJ,
        dir_name=metadata["TITLE_ABBREVIATION"],
    )
