# CoCliCo STAC tools

This directory contains python files with functions to define and generate a STAC
catalogue based upon datasets available in zarr format.

[generate_stac.py](../scripts/generate_stac.py) provides an example of how the functions
in this directory can be used to build a stac catalogue from a zarr store.

## Table of contents

[blueprint.py](./blueprint.py) contains the STAC layout class and functions to generate
the default CoCliCo STAC collections and items.

[datacube.py](./datacube.py) contains functions to extract dimension shapes and metadata
from zarr stores. The methods rely and are inspired on
[xstac](https://github.com/TomAugspurger/xstac).

[utils.py](./utils.py) contains a few custom functins useful for migrating xarray data to
a stac catalogue.
