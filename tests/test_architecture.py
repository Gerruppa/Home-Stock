import ast
from collections.abc import Iterator
from pathlib import Path

FORBIDDEN = {"sqlalchemy", "alembic", "flet"}
PACKAGE = Path(__file__).parent.parent / "src" / "home_stock"


def _imports(folder: Path) -> Iterator[tuple[Path, str]]:
    for path in folder.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                yield from ((path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                yield path, node.module


def test_nothing_imports_the_removed_windows_app_s_frameworks() -> None:
    # Still installed in an older venv, so an import would not fail on its own
    for path, name in _imports(PACKAGE):
        assert name.split(".")[0] not in {"nicegui", "webview"}, f"{path.name} imports {name}"


def test_domain_has_no_framework_imports() -> None:
    for path, name in _imports(PACKAGE / "domain"):
        assert name.split(".")[0] not in FORBIDDEN, f"{path.name} imports {name}"
