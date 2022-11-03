# Notebooks used for CoCliCo fast-track preprocessing

## CF conventions

Datasets should follow CF conventions where possible. These conventions are described
[here](https://cfconventions.org/).

## TODO: Description dimension, coordinates, variables


### Controlled vocabulary  

#### TODO: Description use controlled vocabulary

| src_name         | dst_name            | long_name           | standard_name | cf_type | dtype                 |
|------------------|---------------------|---------------------|---------------|---------|-----------------------|
| RP               | rp                  | return period       |               | dim     | int                   |
| decades          | time                | time                | time          | dim     | cftime                |
| id               | nstations           | number of stations  |               | dim     | int                   |
| lat              | lat                 | latitude            | latitude      | dim     | float                 |
| latitude         | lat                 | latitude            | latitude      | dim     | float                 |
| lon              | lon                 | longitude           | longitude     | dim     | float                 |
| longitude        | lon                 | longitude           | longitude     | dim     | float                 |
| nens             | nensemble           | number of ensembles |               | dim     | int                   |
| nlayers          | nlayers             | number of layers    |               | dim     | int                   |
| npoints          | nstations           | number of stations  |               | dim     | int                   |
| nrp              | rp                  | return period       |               | dim     | int                   |
| nscenarios       | nscenarios          | number of scenarios |               | dim     | int                   |
| nsdec            | time                | time                |               | dim     | cftime                |
| ntransect        | nstations           | number of stations  |               | dim     | int                   |
| ptid             | nstations           | number of stations  |               | dim     | int                   |
| rp               | rp                  | return period       |               | dim     | int                   |
| ensmbl           | ensemble            | ensemble            |               | coord   | zero-terminated bytes |
| id               | stations            | stations            |               | coord   | zero-terminated bytes |
| ptid             | stations            | stations            |               | coord   | zero-terminated bytes |
| layers           | layers              | layers              |               | coord   | zero-terminated bytes |
| scenario         | scenario            | scenario            |               | coord   | zero-terminated bytes |
| transect         | stations            | stations            |               | coord   | zero-terminated bytes |
| activezonetoland | active_zone_to_land | active zone to land |               | var     | float                 |
| activezonetosea  | active_zone_to_sea  | active zone to sea  |               | var     | float                 |
| eewl             | eewl                |                     |               | var     | float                 |
| errorid          | error_id            | error id            |               | var     | str                   |
| esl              | esl                 | extreme sea level   |               | var     | float                 |
| landid           | country             | country             |               | var     | str                   |
| landtoactivezone | land_to_active_zone | land to active zone |               | var     | float                 |
| landtosea        | land_to_sea         | land to sea         |               | var     | float                 |
| ssl              | ssl                 | sea surface level   |               | var     | float                 |
| sustain          | sustain             | sustainability      |               | var     | float                 |
| wef              | wef                 | wave energy flux    |               | var     | float                 |
| base2000         |                     |                     |               |         |                       |
| cfpi             |                     |                     |               |         |                       |
| col              |                     |                     |               |         |                       |
| copula           |                     |                     |               |         |                       |
| cor              |                     |                     |               |         |                       |
| dd10             |                     |                     |               |         |                       |
| ffbd2050         | scenario?           |                     |               |         |                       |
| ffbd2100         | scenario?           |                     |               |         |                       |
| ffd              | ffd                 |                     |               |         |                       |
| firstYear        | first_year          |                     |               |         |                       |
| firstlandlat     | first_land_lat      |                     |               |         |                       |
| firstlandlon     | first_land_lot      |                     |               |         |                       |
| frag2050         | scenario?           |                     |               |         |                       |
| frag2100         | scenario?           |                     |               |         |                       |
| landfound        | land_found          |                     |               |         |                       |
| lastYear         | last_year           |                     |               |         |                       |
| latland          | lat_land            |                     |               |         |                       |
| latsea           | lat_sea             |                     |               |         |                       |
| lonland          | lon_land            |                     |               |         |                       |
| lonsea           | lon_sea             |                     |               |         |                       |
| perc1            |                     |                     |               |         |                       |
| perc17           |                     |                     |               |         |                       |
| perc5            |                     |                     |               |         |                       |
| perc50           |                     |                     |               |         |                       |
| perc83           |                     |                     |               |         |                       |
| perc95           |                     |                     |               |         |                       |
| perc99           |                     |                     |               |         |                       |
| pp10             |                     |                     |               |         |                       |
| qualityflag      | quality_flag        |                     |               |         |                       |
| ret_per          | ret_per             |                     |               |         |                       |
| row              | stations?           |                     |               |         |                       |
| seatoactivezone  | sea_to_active_zone  |                     |               |         |                       |
| seatoland        | sea_to_land         |                     |               |         |                       |
| segmentid        | instance?           |                     |               |         |                       |
| spuriousratio    | spurious_ratio      |                     |               |         |                       |
| ss10             |                     |                     |               |         |                       |
| sust2050         | scenario?           |                     |               |         |                       |
| sust2100         | scenario?           |                     |               |         |                       |
