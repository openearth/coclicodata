# Notebooks used for CoCliCo fast-track preprocessing

## CF conventions

Datasets should follow CF conventions where possible. These conventions are described [here](https://cfconventions.org/).

### Attribute requirements for CoCliCo datasets

The following attributes are required at dataset level

- title
- history
- institution
- source

The following attributes are required at variable level

- units
- long_name
- standard_name

The following coordinate labels are required:

- crs or crs_wkt
- time  

## Name tables

The following variables are found in the CoCliCo datasets. When adding a datasets, please
check if the variable is already present in the tables below.

### Dimension name table

| name        | standard_name               | xr_type | dtype        |
|-------------|-----------------------------|---------|--------------|
| lon         | longitude                   | dim     | int          |
| lat         | latitude                    | dim     | int          |
| stations    | stations                    | dim     | int          |
| regions     | regions                     | dim     | int          |
| rp          | return_period               | dim     | int          |
| scenarios   | scenarios                   | dim     | int          |
| time        | time                        | dim     | int          |

#### Variable name table

| name        | standard_name               | xr_type | dtype        |
|-------------|-----------------------------|---------|--------------|
| ssl         | sea_surface_level           | var     | float64      |
| wef         | wave_energy_flux            | var     | float64      |
| esl         |                             | var     |              |
| eewl        |                             | var     |              |
| ffd         | fossil_fuel_development     | var     | float64      |
| sustain     | sustainability              | var     | float64      |

### Coordinates name table

| name        | standard_name               | xr_type | dtype        |
|-------------|-----------------------------|---------|--------------|
| lon         | longitude                   | coord   | float64      |
| lat         | latitude                    | coord   | float64      |
| time        | time                        | coord   | str          |
| geometry    | geometry                    | coord   | geometry wkt |
| crs         | coordinate_reference_system | coord   | crs wkt      |
| nuts_region | nuts_region                 | coord   | str          |

### Additional notes for the name conventions

Please have a look at [the cf convention](https://cfconventions.org/).

Some important conventions adopted in the CoCliCo project:

- "time" is used for the time dimension, including dimensions such as decades. The units
  attributes of the time dimensions defines the sampling rate and time starting point.
- "stations" represents the station dimension for data that is sampled at certain
  observation points.
- "regions" represents the region dimension for data that describes regions.
- "geometry" attribute coordinate can be used to describe the region in well known text
  (WKT) format.
