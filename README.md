# CoCliCo Data

This repository contains code to maintain the CoCliCo STAC catalog. Please note that
this is a **relative** STAC catalog for development purposes.

## Installation instructions

Given that `coclicodata` is under active development, it's recommended to clone the repository and then install it in 'editable' mode. This way, any changes made to the package are immediately available without needing a reinstall.

Follow these steps for installation:

1. Install GitHub Desktop for your OS: https://desktop.github.com/ 
2. Install the Mamba Package Manager (miniforge3) for your OS: https://github.com/conda-forge/miniforge#mambaforge 
3. Open a miniforge prompt (by searching “miniforge” in the task bar) and run “mamba –version” to check if the installation was complete. 
4. Clone the `coclicodata` repo by adding (“Add” --> “clone repository” --> "URL") URL in GitHub Desktop, you can find the URL under the green “code” button in this `coclicodata` repo. Please change the local path to something like: `C:\Users\***\Documents\GitHub` (where you create the GitHub folder yourself). The repo will be cloned here. 
5. In the miniforge prompt, change the directory to the cloned repo by running `cd C:\Users\***\Documents\GitHub\coclicodata`, where *** needs to be replaced to your system variables.
6. This directory contains an `environment.yml` file with all the necessary packages describing the software dependencies. Create the software environment by running the following command in the miniforge prompt (note, this will take about 10 minutes to run): 

   ``` bash
   mamba env create -f environment.yml
   ```

7. Now you can activate the environment we just created, in your miniforge prompt please run the following:

   ``` bash
   mamba activate coclico
   ```

8. You can look which environments you have installed by running: `mamba env list`. It places a star to indicate in which environment you are situated now (also indicated in front of your command line).
9. In principle, mamba should have installed the pip dependencies as well. If it fails to install these, you can install the ones requiring pip in the `environment.yml` file manually by running (note list might not be complete, check against the `environment.yml` file):

   ``` bash
   pip install stactools-geoparquet-items odc-ui odc-stac odc-algo odc-io odc-cloud[ASYNC] mapbox mapboxcli xstac
   ```

10. To check if all went well you can run `mamba list` to list all installed packages and search for, for instance `mapbox`. If it is present, you can continue. 
11. Now, this is a bit confusing, but we still need to install our `coclicodata` package. This is available in the repo you just cloned with the same name in the folder `src/coclicodata`. As this package is not published online, we cannot do pip or mamba installations, we need to install it from our clone. 
12. Install the coclicodata package by running (if you are still in the `C:\Users\***\Documents\GitHub\coclicodata` directory):

   ``` bash
   pip install -e . 
   ```
13. For running jupyter notebooks and / or python scripts, we recommend to install VS Code editor: https://code.visualstudio.com/ as it offers flexibility in selecting environments, directories and python interpreters as well as offers various useful extensions all in one user interface.
14. Open VS Code and select the cloned coclicodata folder as your working directory. As a test, you can open `01_storm_surge.ipynb` in notebooks. Select your kernel (the `coclicodata` env) in the top right corner and run cells by pressing shift-enter. You should be able to progress through the notebook without any errors in case you put the NC files present in `docs\example` in the right directory. Please change `coclico_data_dir` and `dataset_dir` accordingly. 
15. Might you run into trouble with these installation guidelines, please reach out to @EtienneKras, @mathvansoest or @FlorisCalkoen for help.  

## Use pre-commit locally

Ensure consistent code formatting and avoid big repositories by removing output with pre-commit.

In the root of the repository run:

```bash
pre-commit install
```

If the hooks catch issues when you commit your changes, they will fix them automatically.:

```bash
git commit -m "Your message"
```
Once hooks pass, push your changes.

## Test

You can run `pytest` to check whether you current STAC collection is valid. The command
will automatically run the test scripts that are maintained in `tests/test_*.py`

## Release

On successful validation of STAC catalog in the main branch, an **absolute** version
of the catalog will be published in the `live` branch that can be used externally.

## CoCliCoData repository structure

- **ci**
  - `convert.py`: CI script to convert current to live stacs.

- **current**: STAC catalog that is used for web portal development.

- **docs**: Various documentation images like flowcharts and diagrams representing data formats and workflows.

- **json-schema**
  - `schema.json`: JSON schema definition for the frontend Deltares STAC extension.

- **notebooks**: Jupyter notebooks used to load, explore and transform the data;
  typically one per dataset, to make it CF compliant.

- **scripts**
  - **bash**: Shell scripts, like `build-stacs.sh` and `upload-stacs-to-azure.sh`, for various automation tasks.
  - **create_stacs**: Python scripts for creating STACs, each typically corresponding to a specific dataset or processing step.
  - **utils**: Utility scripts, like `coclico_common_vocab_from_stac.py` and `upload_and_generate_geojson.py`, for various data operations.

- **src/coclicodata**
  - `__init__.py`: Main package initialization.
  - `drive_config.py`: Configuration settings for the drive or storage medium.
  - **etl**
    - `__init__.py`: Subpackage initialization.
    - `cf_compliancy_checker.py`: Checks for compliancy with the Climate and Forecast (CF) conventions.
    - `cloud_utils.py`: Utilities for cloud-based operations and data processing.
    - `extract.py`: Data extraction and transform functionalities.

  - **coclico_stac**
    - `__init__.py`: Subpackage initialization.
    - `datacube.py`: Functions for extracting dimension shapes and metadata from zarr stores.
    - `extension.py`: CoCliCo STAC extension that is used for frontend visualization.
    - `io.py`: Defines the CoCLiCo JSON I/O strategy for STAC catalogs.
    - `layouts.py`: Provides CoCliCo layout strategies for STAC for the data formats used.
    - `templates.py`: Defines CoCliCo templates for generating STAC items, assets and collections.
    - `utils.py`: Utility functions for data migration and other STAC-related operations.

- **stories**: Contains narrative data and associated images.

- **tests**: Contains test scripts to ensure code quality and functionality.

- `.pre-commit-config.yaml`: Hooks that will be run when making a commit.
- `metadata_template.json`: Template file for a STAC collection from a dataset. For a full and formal explanation on metadata attributes see below.

## Metadata

The following attributes are required at dataset level:

- title -
- title abbreviation -
- description - description that will be used to as dataset explanation in the web portal.
- short description - description which is convenient when loading the data into a
  programming environment
- institution - data producer
- providers - data host (Deltares / CoCliCo)
  - name
  - url
  - roles - e.g., providers, licensor
  - description -
- history - list of institutions and people who have processed the data
- media_type - [also known as mime type](https://www.iana.org/assignments/media-types/media-types.xhtml)
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
- cell_bnds

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
