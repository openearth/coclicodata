# -*- coding: utf-8 -*-
"""
Created on Tue Jul 12 19:56:15 2022 
code from https://cogeotiff.github.io/rio-cogeo/API/

@author: Skoulikaris Ch
"""

import os
import glob
import time
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

# Define the working directory
working_dir = os.getcwd()
output_dir = os.path.join(working_dir, 'cog_outputs')

# Create 'cog_outputs' directory if it does not exist
os.makedirs(output_dir, exist_ok=True)

def translate_to_cog(src_path, dst_path, profile="deflate", profile_options={}, **options):
    try:
        start_time = time.time()
        
        # Convert image to COG
        output_profile = cog_profiles.get(profile)
        output_profile.update(profile_options)

        # Dataset Open option (see gdalwarp `-oo` option)
        config = dict(
            GDAL_NUM_THREADS="ALL_CPUS",
            GDAL_TIFF_INTERNAL_MASK=True,
            GDAL_TIFF_OVR_BLOCKSIZE="128",  # It is used for setting blocksize in Geotiff overviews, in gdal is 256 by default
        )

        cog_translate(
            src_path,
            dst_path,
            output_profile,
            config=config,
            in_memory=False,
            quiet=True,
            **options,
        )
        end_time = time.time()
        print(f"Translation of {src_path} completed in {end_time - start_time:.2f} seconds")
        return True
    except Exception as e:
        print(f"Error during translation of {src_path}: {e}")
        return False

# Find all .tif files in the working directory
tif_files = glob.glob(os.path.join(working_dir, '*.tif'))

# Iterate over each .tif file
for tif_file in tif_files:
    filename = os.path.basename(tif_file)
    dst_path = os.path.join(output_dir, filename[:-4] + '.cog.tif')  # Remove '.tif' and add '.cog.tif'

    if translate_to_cog(tif_file, dst_path):
        print(f"Translation and validation successful for {filename}")
    else:
        print(f"Translation and validation failed for {filename}")
