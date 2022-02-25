from pystac import Catalog
from pystac.validation import validate_all

# href = "https://raw.githubusercontent.com/openearth/coclico/main/"
href = "./current/catalog.json"
root_catalog = Catalog.from_file(href)
root_catalog.describe()

def test_catalog_is_valid():
    assert root_catalog.validate_all() is None

