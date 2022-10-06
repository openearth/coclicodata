from pystac import Catalog

href = "./current/catalog.json"
root = Catalog.from_file(href)
root.describe()


def test_catalog_is_valid():
    assert root.validate_all() is None


# TODO: delete if migrated to catalog
# href = "./current/collection.json"
# root = Collection.from_file(href)
# root.describe()

# def test_catalog_is_valid():
#     assert root.validate_all() is None
