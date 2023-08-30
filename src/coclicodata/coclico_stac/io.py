import json
from typing import Any, Dict

from pystac.stac_io import DefaultStacIO


class CoCliCoStacIO(DefaultStacIO):
    "Custom IO to format our CoCliCo STAC json with an indentation of 4 spaces."

    def __init__(self) -> None:
        super().__init__()
        import warnings

        warnings.warn(
            "CoCliCoStacIO will be deprecated in future versions. "
            "Newer versions of pystac (1.8+) should natively handle Windows paths.",
            FutureWarning,
        )

    # enabling a GitHub Actions compatible Windows created STAC --> i.e. replacing '\\' by '/'
    def _dict_replace_value(self, d, old, new):
        x = {}
        for k, v in d.items():
            if isinstance(v, dict):
                v = self._dict_replace_value(v, old, new)
            elif isinstance(v, list):
                v = self._list_replace_value(v, old, new)
            elif isinstance(v, str):
                v = v.replace(old, new)
            x[k] = v
        return x

    def _list_replace_value(self, l, old, new):
        x = []
        for e in l:
            if isinstance(e, list):
                e = self._list_replace_value(e, old, new)
            elif isinstance(e, dict):
                e = self._dict_replace_value(e, old, new)
            elif isinstance(e, str):
                e = e.replace(old, new)
            x.append(e)
        return x

    def json_dumps(self, json_dict: Dict[str, Any], *args: Any, **kwargs: Any) -> str:
        return json.dumps(
            self._dict_replace_value(json_dict, "\\", "/"), *args, indent=4, **kwargs
        )
