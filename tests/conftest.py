"""Shared test setup."""

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark the tests of every module that drives the UI through user_simulation, so ``-m "not ui"`` skips them."""
    for item in items:
        module = getattr(item, "module", None)
        if module is not None and hasattr(module, "user_simulation"):
            item.add_marker(pytest.mark.ui)
