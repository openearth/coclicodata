from pystac import Catalog

href = "./current/catalog.json"
root = Catalog.from_file(href)


def test_all_collections_unique():
    collections = root.get_all_collections()
    collection_ids = [collection.id for collection in collections]

    unique_ids = set(collection_ids)

    assert len(collection_ids) == len(
        unique_ids
    ), "Some collections have duplicate IDs!"
