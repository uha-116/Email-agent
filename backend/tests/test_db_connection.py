from unittest.mock import MagicMock

import pytest

import backend.db_storage.db_connection as db_connection
from backend.error_handling import DBConnectionError, NetworkDownError


def test_get_db_connection_raises_when_database_url_missing(monkeypatch, scenario_printer):
    monkeypatch.setattr(db_connection, "DATABASE_URL", None)

    with pytest.raises(DBConnectionError, match="DATABASE_URL not configured"):
        db_connection.get_db_connection()
    scenario_printer(
        "Missing DATABASE_URL",
        "DATABASE_URL unset",
        "Connection helper should raise DBConnectionError",
        "DBConnectionError raised before any connect attempt",
    )


def test_get_db_connection_retries_then_succeeds(monkeypatch, scenario_printer):
    calls = {"count": 0}
    fake_conn = MagicMock()

    def flaky_connect(url):
        calls["count"] += 1
        if calls["count"] == 1:
            raise db_connection.psycopg2.OperationalError("temporary failure")
        return fake_conn

    monkeypatch.setattr(db_connection, "DATABASE_URL", "postgres://example")
    monkeypatch.setattr(db_connection.psycopg2, "connect", flaky_connect)

    conn = db_connection.get_db_connection()

    assert conn is fake_conn
    assert calls["count"] == 2
    assert fake_conn.autocommit is False
    scenario_printer(
        "DB retry success",
        "First psycopg2.connect call raises OperationalError, second succeeds",
        "Helper should retry once and return a configured connection",
        "Connection returned on second attempt with autocommit disabled",
    )


def test_get_db_connection_translates_dns_failure(monkeypatch, scenario_printer):
    monkeypatch.setattr(db_connection, "DATABASE_URL", "postgres://example")
    monkeypatch.setattr(
        db_connection.psycopg2,
        "connect",
        lambda url: (_ for _ in ()).throw(
            db_connection.psycopg2.OperationalError("could not translate host name")
        ),
    )

    with pytest.raises(NetworkDownError):
        db_connection.get_db_connection()
    scenario_printer(
        "DB hard network failure",
        "psycopg2 OperationalError contains DNS failure text",
        "Helper should translate it to NetworkDownError",
        "NetworkDownError raised",
    )


def test_get_db_connection_raises_db_connection_error_after_retries(monkeypatch, scenario_printer):
    monkeypatch.setattr(db_connection, "DATABASE_URL", "postgres://example")

    def always_fail(url):
        raise db_connection.psycopg2.OperationalError("temporary failure")

    monkeypatch.setattr(db_connection.psycopg2, "connect", always_fail)

    with pytest.raises(DBConnectionError, match="Database connection failed"):
        db_connection.get_db_connection()
    scenario_printer(
        "DB retry exhaustion",
        "Every psycopg2.connect call raises OperationalError",
        "Helper should retry then raise DBConnectionError",
        "DBConnectionError raised after retry exhaustion",
    )
