import pathlib
import platform

# Deltares drive configurations.
if platform.system() == "Windows":
    p_drive = pathlib.Path("P:/")
else:  # linux or other
    p_drive = pathlib.Path("/p/")

# write test for proj==""
abs_proj_path = pathlib.Path(__file__).parent.parent
proj = pathlib.Path(__file__).parent.relative_to(abs_proj_path)
