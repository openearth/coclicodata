# -*- coding: utf-8 -*-
"""
Created on Tue Jul 19 07:05:09 2022

@author: kras
"""

import re
import unittest.mock as mock
from ctypes import CDLL

import requests
from bs4 import BeautifulSoup


def check_compliancy(testfile, working_dir, update_versions=True, download_tables=False):
    """
    Check compliancy of NetCDF files against CF standards: https://cfconventions.org/
    
    Input arguments:
        testfile        - location of the file that is checked against CF standards
        working_dir     - directory to save output check files
        update_versions - search for most recent CF tables if True (default), if False use default numbers in table_dict
        update_tables   - download ans save CF tables if True (default), if False only use them from homepage
        
    # TODO: enable multiple file checking by incorporating looped processes
    
    """
    
    # CF check initialization
    table_dict = {
        "cf-standard-name-table": {
            "version": 76,
            "page": "http://cfconventions.org/Data/cf-standard-names/current/build/cf-standard-name-table.html", # default number
        },
        "area-type-table": {
            "version": 9,
            "page": "http://cfconventions.org/Data/area-type-table/current/build/area-type-table.html", # default number
        },
        "standardized-region-list": {
            "version": 4,
            "page": "http://cfconventions.org/Data/standardized-region-list/standardized-region-list.current.html", # default number
        },
    }
    
    # function to retrieve recent CF tables from the CF convention website if update_versions == True
    def _get_recent_versions(page):
        response = requests.get(page)
        parsed_html = BeautifulSoup(response.content, features="lxml")
        return int(str(parsed_html).split("Version")[1].split(",")[0])

    # update table_dict if update_version == True
    if update_versions:
        for idx, key in enumerate(table_dict.keys()):
            table_dict[key]["version"] = _get_recent_versions(table_dict[key]["page"])
            
    # extend table_dict with CF tables URL from CF conventions website
    table_dict["cf-standard-name-table"][
        "url"
    ] = "http://cfconventions.org/Data/cf-standard-names/{0}/src/cf-standard-name-table.xml".format(
        table_dict["cf-standard-name-table"]["version"]
    )
    table_dict["area-type-table"][
        "url"
    ] = "http://cfconventions.org/Data/area-type-table/{0}/src/area-type-table.xml".format(
        table_dict["area-type-table"]["version"]
    )
    table_dict["standardized-region-list"][
        "url"
    ] = "http://cfconventions.org/Data/standardized-region-list/standardized-region-list.{0}.xml".format(
        table_dict["standardized-region-list"]["version"]
    )
    
    # extend table_dict with local path to save downloaded CF tables, if enabled
    if download_tables:  # save CF tables to working folder if download_tables == True
        for tablename in table_dict.keys():
            table_dict[tablename]["local_path"] = "{0}\{1}-{2}.xml".format(
                working_folder, tablename, table_dict[tablename]["version"]
            )
        
            response = requests.get(table_dict[tablename]["url"])
            with open(table_dict[tablename]["local_path"], "wb",) as file:
                file.write(response.content)

    # check CF compliancy within the testfile
    with mock.patch.object(
        CDLL.__init__, "__defaults__", (0, None, False, False, 0)
    ):  # monkeypatch workaround for the Windows OS (10) ctypes.dll error: https://stackoverflow.com/questions/59330863/cant-import-dll-module-in-python
        from cfchecker.cfchecks import \
            CFChecker  # import the cfchecker package i.s.o. subprocess application as in https://cmip-data-pool.dkrz.de/quality-assurance-cfchecker-ceda.html
    
        inst = CFChecker(
            useFileName="yes",
            cfStandardNamesXML=table_dict["cf-standard-name-table"]["url"],
            cfAreaTypesXML=table_dict["area-type-table"]["url"],
            cfRegionNamesXML=table_dict["standardized-region-list"]["url"],
            debug=False,
            silent=False,
        )
        inst.checker(str(testfile))
        
def save_compliancy(cap, testfile, working_dir):
    """
    Save checked compliancy from the check_compliancy function
    
    Input arguments:
        cap             - captured cell output (Jupyter Notebook cell magic)
        testfile        - location of the file that is checked against CF standards
        working_dir     - directory to save output check files
        
    # TODO: enable multiple file checking by incorporating looped processes
    
    """
    
    # create output directory 
    working_dir.joinpath(str(testfile).split("\\")[-2]).mkdir(
        parents=True, exist_ok=True
    )
    
    # save captured cell output to a .check file
    with open(
        working_dir.joinpath(
            str(testfile).split("\\")[-2],
            str(testfile).split("\\")[-1].replace(".nc", ".check"),
        ),
        "w",
    ) as f:
        f.write(cap.stdout)
    
    # open the created .check file
    with open(
        working_dir.joinpath(
            str(testfile).split("\\")[-2],
            str(testfile).split("\\")[-1].replace(".nc", ".check"),
        )
    ) as f:
        file = f.read()
    
    # print an in-line summary of the CF checker
    files = [
        fileline.split(": ")[1]
        for fileline in file.split("\n")
        if "CHECKING NetCDF FILE" in fileline
    ]
    warnings = [
        warningline.split(": ")[1]
        for warningline in file.split("\n")
        if "WARNINGS given" in warningline
    ]
    errors = [
        errorline.split(": ")[1]
        for errorline in file.split("\n")
        if "ERRORS detected" in errorline
    ]
    
    result_dict = {}
    for idx, f in enumerate(files):
        result_dict[f] = {"warnings": warnings[idx], "errors": errors[idx]}
     
    print(result_dict)    print(result_dict)