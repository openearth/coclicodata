# Notebooks used for CoCliCo fast-track preprocessing

## CF conventions

Datasets should follow CF conventions where possible. Detailed description of those can
be found [here](https://cfconventions.org/).

### Attribute requirements for CoCliCo

The following attributes are required at dataset level

- title
- history
- institution
- source

The following attributes are required at variable level

- units
- long_name
- standard_name

The following coordinates are required:

- geometry_container

### Name conventions

- "time" for time domain.
- "stations" for data that obtained/presented at geogrpahic points.
- "instance" for data that describes regions.
- "geometry_container"

### Miscellaneous

- sort dimensions as time, height/depth, latitude, longitude

-
