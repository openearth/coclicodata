import geojson


def get_point_feature(idx, lon, lat):
    point = geojson.Point([lon, lat])
    feature = geojson.Feature(geometry=point)
    feature["properties"]["locationId"] = idx

    # # TODO: Check with Etienne if the variable values have to be stored in geojson
    # # hopefully not, because the files will become very large. However, if they need to
    # # be stored we could do it something like this:
    # stac_keys = [get_stac_summary_keys(i) for i in dimension_combinations]
    # for stac_key, dimension_indices in zip(stac_keys, dimension_combinations):
    #     # Wrong type to assign geojson property iff extracted without .flatten()[0]
    #     value = ds.sel(dimension_indices)[variable].values.flatten()[0]
    #     feature["properties"][stac_key] = value

    return feature


def get_polygon_feature(idx, geometry):
    raise NotImplementedError(": not implemented yet. ")


def get_geojson(ds, variable, dimension_combinations):

    lons = ds["longitude"].values
    lats = ds["latitude"].values
    idxs = range(len(lons))

    features = list(
        map(lambda lon, lat, idx: get_point_feature(idx, lon, lat), lons, lats, idxs)
    )

    return geojson.FeatureCollection(features)
