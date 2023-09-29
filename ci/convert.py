from pystac import Collection, CatalogType
from os import environ
from pystac import Catalog

branch = environ.get("GITHUB_REF_NAME", "live")

href = "https://raw.githubusercontent.com/openearth/coclicodata/front-end_deployment/current"

collection = Catalog.from_file("./current/catalog.json")
collection.describe()
collection.normalize_hrefs(href)
collection.save(catalog_type=CatalogType.ABSOLUTE_PUBLISHED, dest_href="live")
