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


## Metadata

The following attributes are required at dataset level:

- title - 
- description - description that will be used to as dataset explanation in the web portal. 
- short description - description which is convenient when loading the data into a
  programming environment
- institution - data producer
- providers - data host (Deltares / CoCliCo)
  - name
  - url
  - roles - e.g., providers, licensor
  - description - the
- source - 
- history - list of institutions and people who have processed the data 
- media_type - [also known as mime type](https://en.wikipedia.org/wiki/Media_type)
- spatial extent - bbox [minx, miny, maxx, maxy]
- temporal extent - time interval in [iso 8601](https://en.wikipedia.org/wiki/ISO_8601), i.e., YYYY-MM-DDTHH:mm:ssZ
- license - 
- author - 

The following attributes are optional at dataset level:
- keywords - these can be used to search using the STAC API
- tags - these can be used to search using the STAC API
- citation - if available, preferably following Creator (PublicationYear): Title.
  Publisher. (resourceTypeGeneral). Identifier format (Zenodo specification)
- doi - following [Zenodo specification](https://about.zenodo.org/principles/)
- thumbnail asset image - image that will be shown to represent the dataset
- columns - when data is tabular and has column names 

The following attributes are required at variable level

- long_name - descriptive name
- standard_name - iff available in [CF convention standard table](https://cfconventions.org/Data/cf-standard-names/current/build/cf-standard-name-table.html)
- units - follow CF conventions where possible; leave blank when no units. 

The following attributes are optional at variable level:
- comment - provide extra information about variable

The following coordinate labels are required:

- crs or spatial_ref
- time  

### Controlled vocabulary
| **name**    | **long_name**                                                                               | **standard_name** | **data_structure_type** | **dtype**             |
|-------------|---------------------------------------------------------------------------------------------|-------------------|-------------------------|-----------------------|
| lat         | Latitude                                                                                    | latitude          | dim                     | float                 |
| lon         | Longitude                                                                                   | longitude         | dim                     | float                 |
| nensemble   | Number of ensembles                                                                         |                   | dim                     | int                   |
| nscenario   | Number of scenarios                                                                         |                   | dim                     | int                   |
| nstation   | Number of station                                                                          |                   | dim                     | int                   |
| rp          | Return period                                                                               |                   | dim                     | int                   |
| time        | Time                                                                                        | time              | dim                     | cftime                |
| ensemble    | Ensemble                                                                                    |                   | coord                   | zero-terminated bytes |
| scenario    | Scenario                                                                                    |                   | coord                   | zero-terminated bytes |
| stations    | Stations                                                                                    |                   | coord                   | zero-terminated bytes |
| geometry    | Geometry                                                                                    |                   | coord                   | well-known binary     |
| spatial_ref | Coordinate system and its properties                                                        |                   | coord                   | zero-terminated bytes |
| country     | Country                                                                                     |                   | var                     | zero-terminated bytes |
| esl         | Extreme sea level                                                                           |                   | var                     | float                 |
| ssl         | Sea surface level                                                                           |                   | var                     | float                 |
| sustain     | Sustainability                                                                              |                   | var                     | float                 |
| wef         | Wave energy flux                                                                            |                   | var                     | float                 |
| benefit     | Benefits of raising coastal defences along the European coastline in view of climate change |                   | var                     | float                 |
| cbr         | Benefits of raising coastal defences along the European coastline in view of climate change |                   | var                     | float                 |
| cost        | Cost of raising coastal defences along the European coastline in view of climate change     |                   | var                     | float                 |
| ead         | Expected annual damage                                                                      |                   | var                     | float                 |
| ead_gdp     | Expected annual damage per GDP                                                              |                   | var                     | float                 |
| eapa        | Expected annual people affected                                                             |                   | var                     | float                 |
| eb          | Expected benefit to cost ratios of raising coastal protection per NUTS2 region              |                   | var                     | float                 |
| eewl        | Episodic extreme water level                                                                |                   | var                     | float                 |
| sc          | Shoreline change                                                                            |                   | var                     | float                 |
| ssl         | Storm surge level                                                                           |                   | var                     | float                 |
| wef         | Wave energy flux                                                                            |                   | var                     | float                 |
