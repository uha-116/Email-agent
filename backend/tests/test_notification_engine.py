import importlib
import sys
from unittest import mock

import pytest

from backend.error_handling import DBConnectionError, NetworkError


def load_notification_engine(monkeypatch):
    """Import notification_engine with the top-level error_handling alias in place."""
    import backend.error_handling as backend_error_handling

    monkeypatch.setitem(sys.modules, "error_handling", backend_error_handling)
    sys.modules.pop("backend.agent_services.notification_engine", None)
    return importlib.import_module("backend.agent_services.notification_engine")


def print_test_header(title, scenario, expected):
    print("\n==============================")
    print(f"TEST: {title}")
    print(f"Scenario: {scenario}")
    print(f"Expected: {expected}")
    print("==============================")


def make_db_bundle(rows):
    """Build a mock connection/cursor pair for the DB fetch flow."""
    cursor = mock.Mock(name="cursor")
    cursor.fetchall.return_value = rows

    connection = mock.Mock(name="connection")
    connection.cursor.return_value = cursor

    return connection, cursor


def test_notification_handle_returns_early_when_no_ids(monkeypatch):
    print_test_header(
        "Empty opportunity change list",
        "INSERT and UPDATE lists are both empty",
        "Function should return immediately without touching the DB",
    )
    module = load_notification_engine(monkeypatch)

    get_db_mock = mock.Mock()
    send_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [], "UPDATE": []}})

    print(f"Actual: get_db_connection call count = {get_db_mock.call_count}")
    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert get_db_mock.call_count == 0
    assert send_mock.call_count == 0
    print("Result: Passed - empty change set short-circuited correctly")


def test_notification_handle_db_success_builds_message_and_sends_telegram(monkeypatch):
    print_test_header(
        "DB success flow and message building",
        "DB returns mixed pipeline stages for the same notification batch",
        "Rows should be grouped by stage, formatted into one message, and sent once",
    )
    module = load_notification_engine(monkeypatch)

    rows = [
        ("Alpha Corp", "Engineer", "SELECTED", None, None, "gm-selected"),
        ("Beta Inc", "Analyst", "INTERVIEW", None, "2026-04-10", "gm-interview"),
        ("Gamma LLC", "Scientist", "ASSESSMENT", "2026-04-08", None, "gm-assessment"),
        ("Delta Labs", "Designer", "OPPORTUNITY_FOUND", None, None, "gm-opportunity"),
        ("Epsilon Co", "Manager", "REJECTED", None, None, "gm-rejected"),
    ]
    connection, cursor = make_db_bundle(rows)
    get_db_mock = mock.Mock(return_value=connection)
    send_mock = mock.Mock(return_value=None)

    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    result = module.notification_handle(
        {"opportunity_changes": {"INSERT": [101, 102], "UPDATE": [103]}}
    )

    print(f"Actual: get_db_connection call count = {get_db_mock.call_count}")
    print(f"Actual: cursor.execute call args = {cursor.execute.call_args}")
    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    print(f"Actual: function returned = {result}")

    expected_ids = ([101, 102, 103],)
    assert get_db_mock.call_count == 1
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[1] == expected_ids
    assert cursor.close.call_count == 1
    assert connection.close.call_count == 1
    assert send_mock.call_count == 1
    assert result is None

    final_message = send_mock.call_args.args[0]
    assert "Congratulations! Selected by Alpha Corp" in final_message
    assert "Interview with Beta Inc" in final_message
    assert "Assessment from Gamma LLC" in final_message
    assert "You got 1 new opportunities." in final_message
    assert "Application rejected" in final_message

    assert final_message.index("Selected by Alpha Corp") < final_message.index("Interview with Beta Inc")
    assert final_message.index("Interview with Beta Inc") < final_message.index("Assessment from Gamma LLC")
    assert final_message.index("Assessment from Gamma LLC") < final_message.index("You got 1 new opportunities.")
    assert final_message.index("You got 1 new opportunities.") < final_message.index("Application rejected")

    assert "https://mail.google.com/mail/u/0/#all/gm-selected" in final_message
    assert "https://mail.google.com/mail/u/0/#all/gm-interview" in final_message
    assert "https://mail.google.com/mail/u/0/#all/gm-assessment" in final_message
    assert "https://mail.google.com/mail/u/0/#all/gm-rejected" in final_message
    print("Result: Passed - DB rows were formatted and sent in stage priority order")


def test_notification_handle_db_connection_error(monkeypatch):
    print_test_header(
        "DBConnectionError handling",
        "get_db_connection raises DBConnectionError",
        "Function should log the DB error and return without sending Telegram",
    )
    module = load_notification_engine(monkeypatch)

    get_db_mock = mock.Mock(side_effect=DBConnectionError("db unavailable"))
    send_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [1], "UPDATE": []}})

    print(f"Actual: get_db_connection call count = {get_db_mock.call_count}")
    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert get_db_mock.call_count == 1
    assert send_mock.call_count == 0
    print("Result: Passed - DBConnectionError was handled cleanly")


def test_notification_handle_network_error_from_db(monkeypatch):
    print_test_header(
        "NetworkError handling from DB",
        "get_db_connection raises NetworkError",
        "Function should stop after logging the network issue",
    )
    module = load_notification_engine(monkeypatch)

    get_db_mock = mock.Mock(side_effect=NetworkError("temporary network issue"))
    send_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [1], "UPDATE": []}})

    print(f"Actual: get_db_connection call count = {get_db_mock.call_count}")
    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert get_db_mock.call_count == 1
    assert send_mock.call_count == 0
    print("Result: Passed - NetworkError from DB was handled cleanly")


def test_notification_handle_unexpected_db_error(monkeypatch):
    print_test_header(
        "Unexpected DB error handling",
        "get_db_connection raises a generic Exception",
        "Function should catch the unexpected error and return safely",
    )
    module = load_notification_engine(monkeypatch)

    get_db_mock = mock.Mock(side_effect=Exception("boom"))
    send_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [1], "UPDATE": []}})

    print(f"Actual: get_db_connection call count = {get_db_mock.call_count}")
    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert get_db_mock.call_count == 1
    assert send_mock.call_count == 0
    print("Result: Passed - unexpected DB error was swallowed safely")


def test_notification_handle_empty_rows(monkeypatch):
    print_test_header(
        "Empty DB rows",
        "DB query executes successfully but fetchall() returns no rows",
        "Function should exit without building or sending a message",
    )
    module = load_notification_engine(monkeypatch)

    connection, cursor = make_db_bundle([])
    get_db_mock = mock.Mock(return_value=connection)
    send_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [1], "UPDATE": []}})

    print(f"Actual: cursor.fetchall return value = {cursor.fetchall.return_value}")
    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert cursor.execute.call_count == 1
    assert send_mock.call_count == 0
    print("Result: Passed - empty rows short-circuited correctly")


def test_notification_handle_telegram_success(monkeypatch):
    print_test_header(
        "Telegram success after DB fetch",
        "DB returns one INTERVIEW row and Telegram send succeeds",
        "Function should send one notification without retrying",
    )
    module = load_notification_engine(monkeypatch)

    rows = [("Omega Ltd", "Lead", "INTERVIEW", None, "2026-04-12", "gm-omega")]
    connection, cursor = make_db_bundle(rows)
    get_db_mock = mock.Mock(return_value=connection)
    send_mock = mock.Mock(return_value=None)
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [77], "UPDATE": []}})

    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert send_mock.call_count == 1
    assert "Interview with Omega Ltd" in send_mock.call_args.args[0]
    print("Result: Passed - Telegram send was invoked exactly once")


def test_notification_handle_telegram_failure_retries_once(monkeypatch):
    print_test_header(
        "Telegram retry success",
        "First Telegram send raises NetworkError and second send succeeds",
        "Function should retry exactly once and finish cleanly",
    )
    module = load_notification_engine(monkeypatch)

    rows = [("Retry Co", "Analyst", "OPPORTUNITY_FOUND", None, None, "gm-retry")]
    connection, cursor = make_db_bundle(rows)
    get_db_mock = mock.Mock(return_value=connection)
    send_mock = mock.Mock(side_effect=[NetworkError("first attempt failed"), None])
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [88], "UPDATE": []}})

    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert send_mock.call_count == 2
    assert "You got 1 new opportunities." in send_mock.call_args_list[0].args[0]
    print("Result: Passed - retry was triggered exactly once and then succeeded")


def test_notification_handle_telegram_failure_retry_fails(monkeypatch):
    print_test_header(
        "Telegram retry failure",
        "Both Telegram attempts raise NetworkError",
        "Function should retry once and then stop without crashing",
    )
    module = load_notification_engine(monkeypatch)

    rows = [("Fail Co", "Engineer", "REJECTED", None, None, "gm-fail")]
    connection, cursor = make_db_bundle(rows)
    get_db_mock = mock.Mock(return_value=connection)
    send_mock = mock.Mock(side_effect=[NetworkError("first failure"), NetworkError("second failure")])
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_telegram", send_mock)

    module.notification_handle({"opportunity_changes": {"INSERT": [99], "UPDATE": []}})

    print(f"Actual: send_telegram call count = {send_mock.call_count}")
    assert send_mock.call_count == 2
    assert "Application rejected" in send_mock.call_args_list[0].args[0]
    print("Result: Passed - retry failed gracefully after the second attempt")
