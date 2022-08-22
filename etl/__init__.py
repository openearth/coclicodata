import pathlib
import platform
from importlib.resources import path

# Deltares drive configurations.

operating_system = platform.system()

if operating_system == "Windows":
    p_drive = pathlib.Path("P:/")
elif operating_system == "Darwin":
    p_drive = pathlib.Path("/Volumes/p/")
elif operating_system == "Linux":
    p_drive = pathlib.Path("/p/")
else:  # linux or other
    raise ValueError(f"Cannot set p drive path for {operating_system}")

rel_root = pathlib.Path(__file__).parent.parent
