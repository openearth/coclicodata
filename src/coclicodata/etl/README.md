# Automate data processing for the CoCliCo web portal

This document describes how the scripts in [the etl module](../etl) directory can be
used to transform, format and process coclico data and store the results in the cloud.

## Table of contents

- [Cloud Services](#cloud-services)
- [Keys](#keys)

## Cloud Services

[cloud_services.py](./cloud_services.py) contains functions to interact with cloud
services including Google Cloud and Mapbox.

[extract.py](./extract.py) contains functions to extract geospatial features from xarray
datasets.

[keys.py](./keys.py) contains functions to manage access keys to cloud services.
