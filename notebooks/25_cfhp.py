# Import standard packages
import os
import pathlib
import sys
import re
import json5
import numpy as np
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import xarray as xr
from dotenv import load_dotenv
import glob
import rioxarray
import rasterio
from datacube.utils.cog import write_cog
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import rioxarray as rio
#load_dotenv()

# Import custom functionality
from coclicodata.drive_config import p_drive
from coclicodata.etl.cf_compliancy_checker import check_compliancy, save_compliancy
from coastmonitor.io.utils import name_block

# Define (local and) remote drives
coclico_data_dir = p_drive.joinpath("11207608-coclico", "FULLTRACK_DATA")

# Workaround to the Windows OS (10) udunits error after installation of cfchecker: https://github.com/SciTools/iris/issues/404
os.environ["UDUNITS2_XML_PATH"] = str(
    pathlib.Path().home().joinpath(  # change to the udunits2.xml file dir in your Python installation
        r"Anaconda3\pkgs\udunits2-2.2.28-h892ecd3_0\Library\share\udunits\udunits2.xml"
    )
)

# use local or remote data dir
use_local_data = False
ds_dirname = "WP4"

if use_local_data: 
    ds_dir = pathlib.Path().home().joinpath("data", "tmp", ds_dirname)
else: 
    ds_dir = coclico_data_dir.joinpath(ds_dirname, "data")

if not ds_dir.exists():
    raise FileNotFoundError("Directory with data does not exist.")

# directory to export result (make if not exists)
cog_dir = ds_dir.parent.joinpath("cog") # for checking CF compliancy
cog_dirs = ds_dir.parent.joinpath("cogs_28nov24") # for making all files CF compliant
cog_dir.mkdir(parents=True, exist_ok=True)

# Set up file structure for coastal flooding hazard maps
def generate_slices(num_chunks: int, chunk_size: int) -> Tuple[slice, slice]:
    """Generate slices for chunk-based iteration."""
    for i in range(num_chunks):
        yield slice(i * chunk_size, (i + 1) * chunk_size)

def extract_info(file_path: Path):

    rps = ["static", "1", "100", "1000"]  # 4 options
    scenarios = ["none", "SSP126", "SSP245", "SSP585", "High_End"]  # 5 options
    times = ["2010", "2030", "2050", "2100", "2150"]  # 5 options

    # Extract the map type (the first part of the path)
    map_type = file_path.parts[0]
    
    # Extract the filename (last part of the path)
    file_name = file_path.parts[-1]
    
    # Initialize variables to None
    rp = rps[0]
    scenario = None
    time = times[0]

    # Check for RP in the filename (if any)
    if "RP1000" in file_name:
        rp = "1000"
    elif "RP100" in file_name:
        rp = "100"
    elif "RP1" in file_name:
        rp = "1"
    
    # Check for scenario in the filename (if any)
    # Normalize the filename for case-insensitive matching
    normalized_file_name = file_name.lower()
    for s in scenarios:
        pattern = re.escape(s.lower()).replace("_", "[-_]*")  # Match variations like "High_End" or "High-End"
        if re.search(pattern, normalized_file_name):
            scenario = s
            break  # stop at the first match
    
    # Check for time in the filename (if any)
    for t in reversed(times):  # Reverse the order to prioritize later matches
        if t in file_name:
            time = t
            break  # stop at the first match
    
    return str(rp), str(scenario), str(time)

item_type = "mosaic"  # "single" or "mosaic"
item_properties = ["defense level", "rp", "scenarios", "time"]
map_types = [
    "HIGH_DEFENDED_MAPS",
    "LOW_DEFENDED_MAPS",
    "UNDEFENDED_MAPS",
]  # 3 options

for map_type in [map_types[2]]:
    print(map_type)

    # Iterate over the original tif files
    tif_list = ds_dir.joinpath(map_type).glob("*.tif")
    
    for cur_tif in tif_list:

        rp,scenario,time = extract_info(Path(*cur_tif.parts[5:]))

        print('currently working on: '+str(cur_tif))
        
        out_dir = pathlib.Path(cog_dirs.joinpath(map_type,rp,scenario,time))
        out_dir.mkdir(parents=True,exist_ok=True)

        print('writing chunks to: ' + str(out_dir))
        print(' ')

        fm = rio.open_rasterio(
            cur_tif, mask_and_scale=False
        )  # .isel({"x":slice(0, 40000), "y":slice(0, 40000)})
        fm = fm.assign_coords(band=("band", [f"B{k+1:02}" for k in range(1)])) # NOTE: hard coded to 1, because one band
        fm = fm.to_dataset("band")

        # chunk size 
        chunk_size = 2**15 # 16384, which is large, but OK for int8 datatype.

        fm_chunked = fm.chunk({"x": chunk_size, "y": chunk_size})

        num_x_chunks = math.ceil(fm_chunked.dims["x"] / chunk_size)
        num_y_chunks = math.ceil(fm_chunked.dims["y"] / chunk_size)

        # Load meta data
        cur_meta_data = open(ds_dir.joinpath(map_type,'metadata',cur_tif.name.replace('.tif','.json')))
        cur_meta = json5.load(cur_meta_data)

        for x_slice in generate_slices(num_x_chunks, chunk_size):
            for y_slice in generate_slices(num_y_chunks, chunk_size):
                chunk = fm_chunked.isel(x=x_slice, y=y_slice)

                chunk = chunk.assign_coords(time=pd.Timestamp(2024, 3, 18).isoformat())

                for var in chunk:

                    da = chunk[var]
                    
                    da = (
                        da.where(da != chunk.attrs['_FillValue'],-9999)
                        .astype("float32")
                        .rio.write_nodata(-9999)
                        .rio.set_spatial_dims(x_dim="x", y_dim="y")
                    )

                    item_name = name_block(
                        da,
                        storage_prefix="",
                        name_prefix=da.name,
                        include_band=None, 
                        time_dim=False,
                        x_dim="x",
                        y_dim="y",
                    )

                    # hacky fix to get rid of the espg=None string
                    if "None" in item_name:
                        item_name = item_name.replace("None", str(rasterio.crs.CRS(da.rio.crs).to_epsg()))

                    print(item_name)

                    # convert to dataset
                    dad = da.to_dataset()

                    # add all attributes (again)
                    for attr_name, attr_val in cur_meta.items():
                        if attr_name == 'PROVIDERS':
                            attr_val = json5.dumps(attr_val)
                        if attr_name == "MEDIA_TYPE": # change media type to tiff, leave the rest as is
                            attr_val = "IMAGE/TIFF"
                        dad.attrs[attr_name] = attr_val

                    dad.attrs['Conventions'] = "CF-1.8"

                    # make parent dir if not exists

                    outpath = out_dir.joinpath(item_name)
                    outpath.parent.mkdir(parents=True, exist_ok=True)

                    # Print nbytes of dad
                    print(f"nbytes: {dad.nbytes}")

                    # export file
                    dad.rio.to_raster(outpath, compress="DEFLATE", driver="COG")

                    del dad, da

                del chunk

        del fm, fm_chunked
                    # set overwrite is false because tifs should be unique
                    # try:
                    #     write_cog(da, fname=outpath, overwrite=False).compute()
                    # except OSError as e:
                    #     continue



# %%
