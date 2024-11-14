# -*- coding: utf-8 -*-
# Copyright notice
#   --------------------------------------------------------------------
#   Copyright (C) 2024 Deltares
#       Ioanna Micha
#       ioanna.micha@deltares.nl
#
#
#   This library is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this library.  If not, see <http://www.gnu.org/licenses/>.
#   --------------------------------------------------------------------
#
# This tool is part of <a href="http://www.OpenEarth.eu">OpenEarthTools</a>.
# OpenEarthTools is an online collaboration to share and manage data and
# programming tools in an open source, version controlled environment.
# Sign up to recieve regular updates of this function, and to contribute
# your own tools.

# $HeadURL$
# $Keywords: $


import requests
from requests.auth import HTTPBasicAuth
import os

# Configuration
user = ""
password = ""
geoserver_url = ""
auth = HTTPBasicAuth(user, password)
workspace = ""
style_name = ""


# 1. provide the collection.json
layers_dir = ""
# read all files in the directory
layers = os.listdir(layers_dir)

layer_names = []
for layer in layers:

    layer_name = layer
    store_name = layer_name
    gtif_path = layer

    # Headers for XML data
    headers = {"Content-type": "text/xml"}

    # Step 1: Create the Coverage Store
    data_store_url = f"{geoserver_url}/workspaces/{workspace}/coveragestores"
    data_store_data = f"""
    <coverageStore>
    <name>{store_name}</name>
    <workspace>{workspace}</workspace>
    <type>GeoTIFF</type>
    <url>{gtif_path}</url>
    <enabled>true</enabled>
    </coverageStore>
    """

    response = requests.post(
        data_store_url, auth=auth, headers=headers, data=data_store_data
    )
    if response.status_code == 201:
        print("Store created successfully")
    else:
        print(f"Failed to create store: {response.content}")

    # Step 2: Publish the Layer using PUT
    publish_url = f"{geoserver_url}/workspaces/{workspace}/coveragestores/{store_name}/external.geotiff"
    publish_params = {"configure": "first", "coverageName": layer_name}

    response = requests.put(
        publish_url,
        auth=auth,
        headers={"Content-type": "text/plain"},
        data=gtif_path,
        params=publish_params,
    )

    if response.status_code == 201:
        print(f"Layer: {workspace}:{layer_name} published successfully")
    else:
        print(f"Failed to publish layer: {response.content}")

    # Step 3: Assign the Style to the Layer
    layer_url = f"{geoserver_url}/layers/{workspace}:{layer_name}"
    style_data = f"""
    <layer>
    <defaultStyle>
        <name>{style_name}</name>
    </defaultStyle>
    </layer>
    """

    response = requests.put(layer_url, auth=auth, headers=headers, data=style_data)
    if response.status_code == 200:
        print("Style assigned successfully")
    else:
        print(f"Failed to assign style: {response.content}")
