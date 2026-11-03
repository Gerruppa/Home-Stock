import ast
from collections.abc import Iterator
from pathlib import Path

FORBIDDEN = {"nicegui", "sqlalchemy", "alembic", "webview", "flet"}
PACKAGE = Path(__file__).parent.parent / "src" / "home_stock"


def _imports(folder: Path) -> Iterator[tuple[Path, str]]:
    for path in folder.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                yield from ((path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                yield path, node.module


def test_domain_has_no_framework_imports() -> None:
    for path, name in _imports(PACKAGE / "domain"):
        assert name.split(".")[0] not in FORBIDDEN, f"{path.name} imports {name}"


def test_the_android_and_windows_apps_never_import_each_other() -> None:
    # Each goes on its own: the Android build leaves ui/ and app.py out, and the Windows app will be removed
    windows = ("nicegui", "webview", "home_stock.ui", "home_stock.app")
    for path, name in _imports(PACKAGE / "mobile"):
        assert not name.startswith(windows), f"mobile/{path.name} imports {name}"
    for path, name in _imports(PACKAGE / "ui"):
        assert not name.startswith(("flet", "home_stock.mobile")), f"ui/{path.name} imports {name}"
