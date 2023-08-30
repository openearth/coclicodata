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
import pystac_client
import rasterio.warp
import shapely.geometry
import xarray as xr
from etl import p_drive, rel_root

# rename or swap dimension names, the latter in case the name already exists as coordinate
if __name__ == "__main__":

    # hard-coded input params at project level

    catalog = pystac_client.Client.open(
        "https://storage.googleapis.com/dgds-data-public/coclico/coclico-stac/catalog.json"
    )

    common_vocab_fp = p_drive.joinpath(
        "11205479-coclico", "data", "common_vocabulary.csv"
    )

    result = []
    for c in catalog.get_all_collections():
        dict_ = c.to_dict()

        if "cube:variables" in dict_:
            for k, v in dict_["cube:variables"].items():
                if "attrs" in v:

                    # if "long_name" in v["attrs"]:
                    #     d = {k: v["attrs"]["long_name"]}
                    #     result.append(d)
                    # if "standard_name" in v["attrs"]:
                    #     d = {k: v["attrs"]["standard_name"]}
                    #     result.append(d)

                    d = dict()
                    d["name"] = k
                    if "long_name" in v["attrs"]:
                        d["long_name"] = v["attrs"]["long_name"]
                        # d = {k: v["attrs"]["long_name"]}
                    if "standard_name" in v["attrs"]:
                        d["standard_name"] = v["attrs"]["standard_name"]
                        # d = {k: v["attrs"]["standard_name"]}
                        # result.append(d)
                    result.append(d)

        if "cube:dimension" in dict_:
            for k, v in dict_["cube:dimension"].items():
                if "attrs" in v:
                    d = dict()
                    d["name"] = k
                    if "long_name" in v["attrs"]:

                        d["long_name"] = v["attrs"]["long_name"]
                        # d = {k: v["attrs"]["long_name"]}
                    if "standard_name" in v["attrs"]:
                        d["standard_name"] = v["attrs"]["standard_name"]
                        # d = {k: v["attrs"]["standard_name"]}
                        # result.append(d)
                    result.append(d)

    common_vocab = pd.read_csv(common_vocab_fp)

    df = pd.DataFrame(result)
    # result = list({v["id"]: v for v in result}.values())
    # df = pd.DataFrame(
    #     [(i, j) for a in result for i, j in a.items()], columns=["name", "long_name"]
    # )

    df = pd.merge(
        df,
        common_vocab,
        how="outer",
        left_on=["name", "long_name", "standard_name"],
        right_on=["name", "long_name", "standard_name"],
    )
    df = df.drop_duplicates()

    df["data_structure_type"] = pd.Categorical(
        df["data_structure_type"], ["dim", "coord", "var"]
    )
    df = df.sort_values(["data_structure_type", "name"])
    # df = df.sort_values(["name", "standard_name"])
    outpath = pathlib.Path.home().joinpath("data", "tmp", "common_vocabulary.csv")
    df.to_csv(outpath, index=False)
