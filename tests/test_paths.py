from pathlib import Path

import pytest

from home_stock.persistence.paths import database_path


def test_env_overrides_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME_STOCK_DATA_DIR", str(tmp_path))
    assert database_path() == tmp_path / "home_stock.sqlite3"


def test_default_data_dir_is_outside_the_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOME_STOCK_DATA_DIR", raising=False)
    assert "Home Stock" in str(database_path().parent)
    assert Path(__file__).parents[1] not in database_path().parents
