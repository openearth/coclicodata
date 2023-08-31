from pystac import Catalog


def test_catalog_is_valid():
    href = "../current/catalog.json"
    root = Catalog.from_file(href)
    # this will raise a Pystac exception if the catalog is not valid
    n_validated = (
        root.validate_all()
    )  # validate all returns the number of items validated, but in older versions it returned None
    assert type(n_validated) == int  # we used to test for None, but now we test for int
