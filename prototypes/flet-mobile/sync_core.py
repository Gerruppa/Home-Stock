"""Copy the app's NiceGUI-free layers (domain/, persistence/, sources/) into src/home_stock, which flet build packs.

Run before flet run or flet build; the copy is git-ignored and replaced each time."""

import shutil
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE.parents[1] / "src" / "home_stock"
TARGET = HERE / "src" / "home_stock"

shutil.rmtree(TARGET, ignore_errors=True)
TARGET.mkdir(parents=True)
shutil.copy2(SOURCE / "__init__.py", TARGET)
for layer in ("domain", "persistence", "sources"):
    shutil.copytree(SOURCE / layer, TARGET / layer, ignore=shutil.ignore_patterns("__pycache__"))
print(f"Copied {SOURCE} -> {TARGET}")
