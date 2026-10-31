import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

from home_stock.app import (
    attach_log_when_windowless,
    parse_args,
    run_options,
    start_database,
    start_demo_database,
    update_source,
)
from home_stock.persistence.paths import DATA_DIR_ENV, demo_database_path, log_path
from home_stock.persistence.products import list_products
from home_stock.sources.app_update import UpdateSource


def test_defaults_open_the_native_window() -> None:
    args = parse_args([])
    assert (args.browser, args.port) == (False, 8080)
    assert run_options(args) == {"native": True, "window_size": (1200, 800)}


def test_browser_serves_on_localhost_without_opening_a_tab() -> None:
    assert run_options(parse_args(["--browser"])) == {"host": "127.0.0.1", "port": 8080, "show": False}
    assert run_options(parse_args(["--browser", "--port", "9000"]))["port"] == 9000


def test_unknown_arguments_are_ignored() -> None:
    assert parse_args(["--browser", "-x", "extra"]).browser is True
    assert parse_args(["--demo", "-x"]).demo is True


def test_demo_serves_in_the_browser() -> None:
    assert parse_args([]).demo is False
    assert run_options(parse_args(["--demo"])) == {"host": "127.0.0.1", "port": 8080, "show": False}


def test_the_real_app_checks_for_updates_and_the_demo_does_not() -> None:
    assert isinstance(update_source(parse_args([])), UpdateSource)
    assert isinstance(update_source(parse_args(["--browser"])), UpdateSource)
    assert update_source(parse_args(["--demo"])) is None


def test_every_start_after_the_first_takes_a_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    backups = tmp_path / "backups"

    start_database().dispose()
    assert not backups.exists()

    for _ in range(2):
        start_database().dispose()
    assert len(list(backups.iterdir())) == 2


def test_demo_database_lives_in_temp_and_is_fresh_on_every_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = tmp_path / "real"
    monkeypatch.setenv(DATA_DIR_ENV, str(real))
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path / "temp"))

    counts = []
    for _ in range(2):
        engine = start_demo_database()
        counts.append(len(list_products(engine)))
        engine.dispose()  # Windows will not delete an open file

    assert demo_database_path().is_relative_to(tmp_path / "temp")
    assert demo_database_path().exists()
    assert counts[0] > 0 and counts[0] == counts[1]
    assert not real.exists()
    assert os.environ[DATA_DIR_ENV] == str(real)
    assert not (tmp_path / "temp" / "Home-Stock-demo" / "backups").exists()


def test_a_start_without_a_console_writes_its_output_to_the_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    # pythonw and the frozen exe have no streams; pywebview swaps them for os.devnull when imported
    monkeypatch.setattr(sys, "stdout", None)
    with open(os.devnull, "w") as devnull:
        monkeypatch.setattr(sys, "stderr", devnull)

        attach_log_when_windowless()
        print("hello")
        print("oops", file=sys.stderr)
        sys.stdout.close()

    assert log_path() == tmp_path / "home_stock.log"
    assert log_path().read_text(encoding="utf-8") == "hello\noops\n"


def test_a_start_from_a_console_keeps_writing_there(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    console = io.StringIO()
    monkeypatch.setattr(sys, "stdout", console)
    monkeypatch.setattr(sys, "stderr", console)

    attach_log_when_windowless()

    assert sys.stdout is console and sys.stderr is console
    assert not log_path().exists()
