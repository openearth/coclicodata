# %%
# written by Etienne Kras, 15-08-2025
# venv: edito_env
# This script migrates the CoCliCo STAC to the EDITO
# sources: https://pub.pages.mercator-ocean.fr/edito-infra/edito-tutorials-content/#/interactWithTheDataAPI?id=edito-data-catalog-api
# see STAC here: https://radiantearth.github.io/stac-browser/#/external/api.dive.edito.eu/data
# see chatgpt, prompt: "give me some code to create a STAC catalog in Python using the EDITO api here: https://pub.pages.mercator-ocean.fr/edito-infra/edito-tutorials-content/#/interactWithTheDataAPI?id=edito-data-catalog-api"

# import packages
from pystac_client import Client
from pystac import Catalog

# %% EDITO STAC
edito_stac_url = "https://api.dive.edito.eu/data/catalogs"

client = Client.open(edito_stac_url)
client  # check to see if access

# catalog = Catalog(id="edito-coclico", description="CoCliCo STAC catalog", stac_version="1.0.0")
print("test")

# TODO:
# 1. Create a STAC catalog locally
# 2. Add collections to the catalog (childs)
# 3. Optionally, add items to the collections
# 4. Save the catalog to a local file
# 5. Upload the catalog to the EDITO S3 storage (MiniO)? Or publish it to the EDITO STAC?

# %% fetch some collections
# collections = client.get_collections()
# for coll in collections:
#     print(f"Collection: {coll.id}")
#     # Retrieve full STAC Collection metadata
#     full_coll = client.get_collection(coll.id)
#     catalog.add_child(full_coll)


# %% save the catalog to a local file
# 6. Save the assembled catalog locally
# catalog.normalize_hrefs("edito_catalog")
# catalog.save(catalog_type="Catalog", catalog_href="edito_catalog/catalog.json")

# print("STAC catalog built and saved locally.")
