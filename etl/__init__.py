import pathlib
import platform

# Deltares drive configurations.
if platform.system() == "Windows":
    p_drive = pathlib.Path("P:/")
else:  # linux or other
    p_drive = pathlib.Path("/p/")

rel_root = pathlib.Path(__file__).parent.parent
