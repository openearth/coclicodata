import os
import pathlib
import platform
import sys

# read version from installed packag# Hacky solution for vscode debugger in modular mode.
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
# Deltares drive configurations.

operating_system = platform.system()

if operating_system == "Windows":
    p_drive = pathlib.Path("P:/")
elif operating_system == "Darwin":
    p_drive = pathlib.Path("/Volumes/p/")
elif operating_system == "Linux":
    p_drive = pathlib.Path("/p/")
else:
    raise ValueError(f"Cannot set p drive path for {operating_system}")

proj_dir = pathlib.Path(__file__).parent.parent
