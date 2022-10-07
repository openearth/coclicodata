from __future__ import annotations

import datetime
import os
import pathlib
import sys
from re import S, template

# make modules importable when running this file as script
sys.path.append(str(pathlib.Path(__file__).parent.parent))

import datetime
import itertools
import operator
import os
from typing import List, Mapping, Optional

import fsspec
import numpy as np
import pandas as pd
import pystac
import rasterio.warp
import shapely.geometry
import xarray as xr
from etl import p_drive, rel_root

# rename or swap dimension names, the latter in case the name already exists as coordinate
if __name__ == "__main__":

    # hard-coded input params at project level
    GCS_PROTOCOL = "https://storage.googleapis.com"
    BUCKET_NAME = "dgds-data-public"
    BUCKET_PROJ = "coclico"
    TEMPLATE = "template-mapbox"  # stac template for dataset collection
    STAC_DIR = "current"

    # hard-coded input params which differ per dataset
    DATASET_FILENAME = "sample.tif"
    STAC_COLLECTION_NAME = "cm"  # name of stac collection

    # define local directories
    home = pathlib.Path().home()
    data_dir = home.joinpath("data", "src")

    # remote p drive
    coclico_data_dir = p_drive.joinpath("11205479-coclico", "data")

    from pystac import Collection

    collection = Collection.from_file(
        os.path.join(rel_root, STAC_DIR, "collection.json")
    )

    result = []
    for c in collection.get_all_collections():
        dict_ = c.to_dict()
        if "cube:variables" in dict_:
            for k, v in dict_["cube:variables"].items():
                if "attrs" in v:
                    if "long_name" in v["attrs"]:
                        d = {k: v["attrs"]["long_name"]}
                        result.append(d)
        if "cube:dimension" in dict_:
            for k, v in dict_["cube:dimension"].items():
                if "attrs" in v:
                    if "long_name" in v["attrs"]:
                        d = {k: v["attrs"]["long_name"]}
                        result.append(d)
    # result = list({v["id"]: v for v in result}.values())
    df = pd.DataFrame(
        [(i, j) for a in result for i, j in a.items()], columns=["keys", "values"]
    )
    df.to_csv(pathlib.Path.home().joinpath("data", "tmp", "common_vocabulary.csv"))
