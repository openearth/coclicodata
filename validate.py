from pystac import Collection

href = "./current/collection.json"
root = Collection.from_file(href)
root.describe()

def test_catalog_is_valid():
    assert root.validate_all() is None

