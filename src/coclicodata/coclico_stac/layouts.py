import pathlib

from pystac import Item
from pystac.layout import BestPracticesLayoutStrategy
from pystac.utils import JoinType, join_path_or_url, safe_urlparse


class CoCliCoZarrLayout(BestPracticesLayoutStrategy):
    """
    Custom layout for Zarrs within CoCliCo STAC collections.

    Modifies the item path to:
        variable-mapbox/variable-mapbox-dim-value-dim-value.json
    Instead of the default:
        /variable-mapbox-dim-value-dim-value/variable-mapbox-dim-value-dim-value.json
    """

    def get_item_href(self, item: Item, parent_dir: str) -> str:
        """
        Determines the item href based on the custom layout for Zarrs.

        Args:
            item (Item): The STAC item.
            parent_dir (str): The parent directory path.

        Returns:
            str: The constructed item href.
        """
        parsed_parent_dir = safe_urlparse(parent_dir)
        join_type = JoinType.from_parsed_uri(parsed_parent_dir)
        custom_id = "-".join(item.id.split("-")[0:2])
        item_root = join_path_or_url(join_type, parent_dir, "{}".format(custom_id))
        return join_path_or_url(join_type, item_root, "{}.json".format(item.id))


class CoCliCoCOGLayout(BestPracticesLayoutStrategy):
    """
    Custom layout for CoGs within CoCliCo STAC collections.

    Modifies the item path to:
        items/variable-mapbox-dim-value-dim-value.json
    Instead of the default:
        /variable-mapbox-dim-value-dim-value/variable-mapbox-dim-value-dim-value.json
    """

    def get_item_href(self, item: Item, parent_dir: str) -> str:
        """
        Determines the item href based on the custom layout for CoGs.

        Args:
            item (Item): The STAC item.
            parent_dir (str): The parent directory path.

        Returns:
            str: The constructed item href.
        """
        parsed_parent_dir = safe_urlparse(parent_dir)
        join_type = JoinType.from_parsed_uri(parsed_parent_dir)
        items_dir = "items"
        custom_id = pathlib.Path(item.id).with_suffix(".json")
        return join_path_or_url(join_type, parent_dir, items_dir, str(custom_id))


class CoCliCoParquetLayout(BestPracticesLayoutStrategy):
    """
    Custom layout for Parquets within CoCliCo STAC collections.

    Items will be stored in a directory named "items", listing different Parquet partitions.
    """

    def get_item_href(self, item: Item, parent_dir: str) -> str:
        """
        Determines the item href based on the custom layout for Parquet.

        Args:
            item (Item): The STAC item.
            parent_dir (str): The parent directory path.

        Returns:
            str: The constructed item href.
        """
        parsed_parent_dir = safe_urlparse(parent_dir)
        join_type = JoinType.from_parsed_uri(parsed_parent_dir)
        items_dir = "items"
        # Assuming the parquet file's ID will be the partition name
        custom_id = pathlib.Path(item.id).with_suffix(".json")
        return join_path_or_url(join_type, parent_dir, items_dir, str(custom_id))
