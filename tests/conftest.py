import pytest

from drive_tidy import steam


@pytest.fixture(autouse=True)
def no_real_steam(monkeypatch):
    """Keep the real Steam client's records out of every test."""
    monkeypatch.setattr(steam, "find_steam", lambda: None)
