from pystac import Collection, CatalogType
from os import environ

branch = environ.get("GITHUB_REF_NAME", "test-groups")

href = "https://raw.githubusercontent.com/openearth/coclico/test-groups/"

collection = Collection.from_file("./current/collection.json")
collection.describe()
collection.normalize_hrefs(href)
collection.save(catalog_type=CatalogType.ABSOLUTE_PUBLISHED, dest_href="test-groups")
