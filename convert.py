from pystac import Collection, CatalogType
from os import environ

branch = environ.get("GITHUB_REF_NAME", "live")

href = "https://raw.githubusercontent.com/openearth/coclico/live/"

collection = Collection.from_file("./current/collection.json")
collection.describe()
collection.normalize_hrefs(href)
collection.save(catalog_type=CatalogType.ABSOLUTE_PUBLISHED, dest_href="live")
