from home_stock.app import parse_args, run_options


def test_defaults_open_the_native_window() -> None:
    args = parse_args([])
    assert (args.browser, args.port) == (False, 8080)
    assert run_options(args) == {"native": True, "window_size": (1200, 800)}


def test_browser_serves_on_localhost_without_opening_a_tab() -> None:
    assert run_options(parse_args(["--browser"])) == {"host": "127.0.0.1", "port": 8080, "show": False}
    assert run_options(parse_args(["--browser", "--port", "9000"]))["port"] == 9000


def test_unknown_arguments_are_ignored() -> None:
    assert parse_args(["--browser", "-x", "extra"]).browser is True
