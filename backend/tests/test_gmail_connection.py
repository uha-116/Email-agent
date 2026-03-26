import importlib
import sys
from unittest.mock import MagicMock

import pytest

from backend.error_handling import NetworkDownError, TokenLoadError


def import_connection_module():
    if "backend.email_fetcher.connection" in sys.modules:
        del sys.modules["backend.email_fetcher.connection"]
    return importlib.import_module("backend.email_fetcher.connection")


def test_get_gmail_service_stops_when_internet_unavailable(monkeypatch, scenario_printer):
    connection = import_connection_module()
    monkeypatch.setattr(connection, "is_internet_available", lambda: False)

    with pytest.raises(NetworkDownError):
        connection.get_gmail_service()
    scenario_printer(
        "Gmail internet unavailable",
        "is_internet_available returns False",
        "Service creation should stop with NetworkDownError",
        "NetworkDownError raised before token/service work",
    )


def test_get_gmail_service_removes_corrupt_token_and_recovers(monkeypatch, scenario_printer):
    connection = import_connection_module()
    removed = []
    creds = MagicMock(valid=True)
    creds.to_json.return_value = "{}"

    monkeypatch.setattr(connection, "is_internet_available", lambda: True)
    monkeypatch.setattr(connection.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        connection.Credentials,
        "from_authorized_user_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad token")),
    )
    monkeypatch.setattr(connection, "perform_login", lambda: creds)
    monkeypatch.setattr(connection, "build", lambda *args, **kwargs: "service")
    monkeypatch.setattr(connection.os, "remove", lambda path: removed.append(path))

    assert connection.get_gmail_service() == "service"
    assert removed
    scenario_printer(
        "Corrupt token recovery",
        "Token load raises ValueError, login fallback succeeds",
        "Service creation should remove corrupt token and recover",
        "Token removal happened and service was returned",
    )


def test_get_gmail_service_raises_when_credentials_missing(monkeypatch, scenario_printer):
    connection = import_connection_module()
    monkeypatch.setattr(connection, "is_internet_available", lambda: True)
    monkeypatch.setattr(connection.os.path, "exists", lambda path: False)

    with pytest.raises(TokenLoadError):
        connection.get_gmail_service()
    scenario_printer(
        "Missing credentials.json",
        "credential path reported missing",
        "Service creation should fail with TokenLoadError",
        "TokenLoadError raised",
    )


def test_get_gmail_service_retries_then_succeeds(monkeypatch, scenario_printer):
    connection = import_connection_module()
    creds = MagicMock(valid=True)
    creds.to_json.return_value = "{}"
    calls = {"count": 0}

    def flaky_build(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise Exception("temporary connection issue")
        return "service"

    monkeypatch.setattr(connection, "is_internet_available", lambda: True)
    monkeypatch.setattr(connection.os.path, "exists", lambda path: True)
    monkeypatch.setattr(
        connection.Credentials,
        "from_authorized_user_file",
        lambda *args, **kwargs: creds,
    )
    monkeypatch.setattr(connection, "build", flaky_build)

    assert connection.get_gmail_service() == "service"
    assert calls["count"] == 2
    scenario_printer(
        "Gmail build retry success",
        "First build call raises transient exception, second succeeds",
        "Service creation should retry and recover",
        "Service built successfully on second attempt",
    )
