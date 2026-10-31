# PyInstaller recipe for HomeStock.exe; scripts/build_installer.ps1 runs it, then packaging/home-stock.iss.
# A folder build (not one file): it starts faster and Inno Setup installs the folder as it is.
from pathlib import Path

import nicegui

ROOT = Path(SPECPATH).parent
PACKAGE = ROOT / "src" / "home_stock"

datas = [
    # NiceGUI serves its JavaScript and CSS from its package folder
    (str(Path(nicegui.__file__).parent), "nicegui"),
    # Alembic reads the migrations as files, not through imports
    (str(PACKAGE / "persistence" / "migrations"), "home_stock/persistence/migrations"),
    # The icon, which the app also serves as its favicon
    (str(PACKAGE / "ui" / "assets"), "home_stock/ui/assets"),
]
datas += [(str(path), "home_stock/ui") for path in (PACKAGE / "ui").glob("*.md")]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    excludes=["pytest", "mypy", "ruff", "PIL"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HomeStock",
    console=False,
    icon=str(PACKAGE / "ui" / "assets" / "home-stock.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="HomeStock")
