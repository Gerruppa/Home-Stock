import ast
from pathlib import Path

FORBIDDEN = {"nicegui", "sqlalchemy", "alembic", "webview"}
DOMAIN = Path(__file__).parent.parent / "src" / "home_stock" / "domain"


def test_domain_has_no_framework_imports() -> None:
    for path in DOMAIN.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert name.split(".")[0] not in FORBIDDEN, f"{path.name} imports {name}"
