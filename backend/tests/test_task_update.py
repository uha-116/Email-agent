import importlib
import sys
from unittest import mock

import pytest

from backend.error_handling import DBConnectionError


def load_task_update(monkeypatch, bot_token="test-bot-token", chat_id="12345"):
    """Import task_update with aliases for its top-level imports."""
    if bot_token is None:
        monkeypatch.delenv("BOT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("BOT_TOKEN", bot_token)

    if chat_id is None:
        monkeypatch.delenv("BOT_CHAT_ID", raising=False)
    else:
        monkeypatch.setenv("BOT_CHAT_ID", chat_id)

    import backend.error_handling as backend_error_handling
    import backend.db_storage as backend_db_storage
    import backend.db_storage.db_connection as backend_db_connection

    monkeypatch.setitem(sys.modules, "error_handling", backend_error_handling)
    monkeypatch.setitem(sys.modules, "db_storage", backend_db_storage)
    monkeypatch.setitem(sys.modules, "db_storage.db_connection", backend_db_connection)

    sys.modules.pop("backend.agent_services.task_update", None)
    return importlib.import_module("backend.agent_services.task_update")


def print_test_header(title, scenario, expected):
    print("\n==============================")
    print(f"TEST: {title}")
    print(f"Scenario: {scenario}")
    print(f"Expected: {expected}")
    print("==============================")


def make_db_bundle(rows):
    """Create a mock DB connection/cursor pair for the task_update tests."""
    cursor = mock.Mock(name="cursor")
    cursor.fetchall.return_value = rows

    connection = mock.Mock(name="connection")
    connection.cursor.return_value = cursor

    return connection, cursor


def make_response(payload):
    response = mock.Mock(name="response")
    response.json.return_value = payload
    return response


def test_fetch_pending_confirmations_success(monkeypatch):
    print_test_header(
        "fetch_pending_confirmations success",
        "DB returns two pending confirmation rows",
        "Rows should be queued and send_next_question should be triggered once",
    )
    module = load_task_update(monkeypatch)
    module.pending_questions.clear()

    rows = [
        (1, "Acme", "ASSESSMENT", "2026-04-01", None),
        (2, "Beta", "INTERVIEW", None, "2026-04-03"),
    ]
    connection, cursor = make_db_bundle(rows)

    get_db_mock = mock.Mock(return_value=connection)
    send_next_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_next_question", send_next_mock)

    module.fetch_pending_confirmations()

    print(f"Actual: pending_questions = {module.pending_questions}")
    print(f"Actual: send_next_question call count = {send_next_mock.call_count}")
    assert get_db_mock.call_count == 1
    assert cursor.execute.call_count == 1
    assert len(module.pending_questions) == 2
    assert module.pending_questions[0]["company"] == "Acme"
    assert module.pending_questions[1]["stage"] == "INTERVIEW"
    assert send_next_mock.call_count == 1
    print("Result: Passed - pending confirmations were fetched and queued")


def test_fetch_pending_confirmations_db_failure(monkeypatch):
    print_test_header(
        "fetch_pending_confirmations DB failure",
        "get_db_connection raises DBConnectionError",
        "Function should log the failure and return without queueing work",
    )
    module = load_task_update(monkeypatch)
    module.pending_questions.clear()

    get_db_mock = mock.Mock(side_effect=DBConnectionError("db unavailable"))
    send_next_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_next_question", send_next_mock)

    module.fetch_pending_confirmations()

    print(f"Actual: pending_questions = {module.pending_questions}")
    print(f"Actual: send_next_question call count = {send_next_mock.call_count}")
    assert get_db_mock.call_count == 1
    assert module.pending_questions == []
    assert send_next_mock.call_count == 0
    print("Result: Passed - DB failure was handled cleanly")


def test_fetch_pending_confirmations_empty_db(monkeypatch):
    print_test_header(
        "fetch_pending_confirmations empty DB",
        "DB returns no rows",
        "Function should print the empty-state message and stop",
    )
    module = load_task_update(monkeypatch)
    module.pending_questions.clear()

    connection, cursor = make_db_bundle([])
    get_db_mock = mock.Mock(return_value=connection)
    send_next_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_next_question", send_next_mock)

    module.fetch_pending_confirmations()

    print(f"Actual: cursor.fetchall return value = {cursor.fetchall.return_value}")
    print(f"Actual: pending_questions = {module.pending_questions}")
    print(f"Actual: send_next_question call count = {send_next_mock.call_count}")
    assert get_db_mock.call_count == 1
    assert module.pending_questions == []
    assert send_next_mock.call_count == 0
    print("Result: Passed - empty DB result was handled safely")


def test_send_confirmation_success(monkeypatch):
    print_test_header(
        "send_confirmation success",
        "Telegram API accepts the POST and returns normally",
        "The confirmation message should be sent once with the expected payload",
    )
    module = load_task_update(monkeypatch)

    response = mock.Mock(status_code=200, text="OK")
    response.json.return_value = {"ok": True}

    post_mock = mock.Mock(return_value=response)
    monkeypatch.setattr(module.requests, "post", post_mock)

    module.send_confirmation(
        company="Acme",
        stage="ASSESSMENT",
        opportunity_id=42,
        deadline="2026-04-05",
        event_date=None,
    )

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    assert post_mock.call_count == 1
    payload = post_mock.call_args.kwargs["json"]
    assert payload["text"] == "Did you complete Acme assessment?\nDeadline: 2026-04-05"
    assert payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "confirm_42"
    print("Result: Passed - confirmation message was built and sent")


def test_send_confirmation_timeout(monkeypatch):
    print_test_header(
        "send_confirmation timeout",
        "requests.post raises Timeout",
        "Function should catch the timeout and continue without crashing",
    )
    module = load_task_update(monkeypatch)

    post_mock = mock.Mock(side_effect=module.requests.exceptions.Timeout)
    monkeypatch.setattr(module.requests, "post", post_mock)

    module.send_confirmation(
        company="Acme",
        stage="INTERVIEW",
        opportunity_id=43,
        deadline=None,
        event_date="2026-04-06",
    )

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    assert post_mock.call_count == 1
    print("Result: Passed - timeout was handled without a crash")


def test_send_confirmation_connection_error(monkeypatch):
    print_test_header(
        "send_confirmation connection error",
        "requests.post raises ConnectionError",
        "Function should catch the connection error and continue safely",
    )
    module = load_task_update(monkeypatch)

    post_mock = mock.Mock(side_effect=module.requests.exceptions.ConnectionError)
    monkeypatch.setattr(module.requests, "post", post_mock)

    module.send_confirmation(
        company="Acme",
        stage="INTERVIEW",
        opportunity_id=44,
        deadline=None,
        event_date="2026-04-07",
    )

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    assert post_mock.call_count == 1
    print("Result: Passed - connection error was handled without a crash")


@pytest.mark.parametrize(
    "callback_data,expected_query_fragment,expected_log_label",
    [
        ("confirm_7", "SET action_required = FALSE", "confirm"),
        ("remove_7", "DELETE FROM opportunities", "remove"),
        ("pending_7", "SET last_updated_at = CURRENT_TIMESTAMP", "pending"),
    ],
)
def test_handle_response_routes_and_commits(monkeypatch, callback_data, expected_query_fragment, expected_log_label):
    print_test_header(
        f"handle_response {expected_log_label}",
        f"Callback data is {callback_data}",
        "The correct SQL branch should run, commit should happen, and the queue should advance",
    )
    module = load_task_update(monkeypatch)
    module.pending_questions[:] = [
        {
            "id": 7,
            "company": "Acme",
            "stage": "ASSESSMENT",
            "deadline": "2026-04-05",
            "event_date": None,
        }
    ]

    connection, cursor = make_db_bundle([])
    get_db_mock = mock.Mock(return_value=connection)
    send_next_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_next_question", send_next_mock)

    module.handle_response(callback_data)

    print(f"Actual: cursor.execute call args = {cursor.execute.call_args}")
    print(f"Actual: connection.commit call count = {connection.commit.call_count}")
    print(f"Actual: send_next_question call count = {send_next_mock.call_count}")
    assert get_db_mock.call_count == 1
    assert expected_query_fragment in cursor.execute.call_args.args[0]
    assert connection.commit.call_count == 1
    assert send_next_mock.call_count == 1
    print(f"Result: Passed - {expected_log_label} callback was routed correctly")


def test_handle_response_rollback_triggered(monkeypatch):
    print_test_header(
        "handle_response rollback path",
        "Database update raises an Exception during execution",
        "The transaction should rollback and the queue should still advance",
    )
    module = load_task_update(monkeypatch)
    module.pending_questions[:] = [
        {
            "id": 9,
            "company": "Rollback Co",
            "stage": "INTERVIEW",
            "deadline": None,
            "event_date": "2026-04-08",
        }
    ]

    connection, cursor = make_db_bundle([])
    cursor.execute.side_effect = Exception("db write failed")
    get_db_mock = mock.Mock(return_value=connection)
    send_next_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_next_question", send_next_mock)

    module.handle_response("confirm_9")

    print(f"Actual: connection.rollback call count = {connection.rollback.call_count}")
    print(f"Actual: send_next_question call count = {send_next_mock.call_count}")
    assert connection.rollback.call_count == 1
    assert send_next_mock.call_count == 1
    print("Result: Passed - rollback was triggered after the DB failure")


def test_handle_response_rollback_failure_handled(monkeypatch):
    print_test_header(
        "handle_response rollback failure",
        "Rollback itself raises an Exception",
        "The rollback failure should be swallowed and the function should still finish",
    )
    module = load_task_update(monkeypatch)
    module.pending_questions[:] = [
        {
            "id": 10,
            "company": "Rollback Fail Co",
            "stage": "ASSESSMENT",
            "deadline": "2026-04-09",
            "event_date": None,
        }
    ]

    connection, cursor = make_db_bundle([])
    cursor.execute.side_effect = Exception("primary db failure")
    connection.rollback.side_effect = Exception("rollback failed")
    get_db_mock = mock.Mock(return_value=connection)
    send_next_mock = mock.Mock()
    monkeypatch.setattr(module, "get_db_connection", get_db_mock)
    monkeypatch.setattr(module, "send_next_question", send_next_mock)

    module.handle_response("remove_10")

    print(f"Actual: connection.rollback call count = {connection.rollback.call_count}")
    print(f"Actual: send_next_question call count = {send_next_mock.call_count}")
    assert connection.rollback.call_count == 1
    assert send_next_mock.call_count == 1
    print("Result: Passed - rollback failure was handled without crashing")


def test_listen_for_responses_valid_callback(monkeypatch):
    print_test_header(
        "listen_for_responses valid callback",
        "Telegram getUpdates returns one callback_query update",
        "handle_response should receive the callback data and the loop should stop after one cycle",
    )
    module = load_task_update(monkeypatch)

    response = make_response(
        {
            "result": [
                {
                    "update_id": 101,
                    "callback_query": {"data": "confirm_123"},
                }
            ]
        }
    )

    get_mock = mock.Mock(return_value=response)
    handle_mock = mock.Mock()
    sleep_mock = mock.Mock(side_effect=StopIteration("stop after one loop"))
    monkeypatch.setattr(module.requests, "get", get_mock)
    monkeypatch.setattr(module, "handle_response", handle_mock)
    monkeypatch.setattr(module.time, "sleep", sleep_mock)

    with pytest.raises(StopIteration):
        module.listen_for_responses()

    print(f"Actual: requests.get call count = {get_mock.call_count}")
    print(f"Actual: handle_response call args = {handle_mock.call_args}")
    print(f"Actual: time.sleep call count = {sleep_mock.call_count}")
    assert get_mock.call_count == 1
    assert handle_mock.call_count == 1
    assert handle_mock.call_args.args[0] == "confirm_123"
    assert sleep_mock.call_count == 1
    print("Result: Passed - valid callback was dispatched to handle_response")


def test_listen_for_responses_malformed_update(monkeypatch):
    print_test_header(
        "listen_for_responses malformed update",
        "Telegram update payload lacks callback_query",
        "The update should be ignored without calling handle_response",
    )
    module = load_task_update(monkeypatch)

    response = make_response({"result": [{"update_id": 102, "message": {"text": "hello"}}]})
    get_mock = mock.Mock(return_value=response)
    handle_mock = mock.Mock()
    sleep_mock = mock.Mock(side_effect=StopIteration("stop after one loop"))
    monkeypatch.setattr(module.requests, "get", get_mock)
    monkeypatch.setattr(module, "handle_response", handle_mock)
    monkeypatch.setattr(module.time, "sleep", sleep_mock)

    with pytest.raises(StopIteration):
        module.listen_for_responses()

    print(f"Actual: requests.get call count = {get_mock.call_count}")
    print(f"Actual: handle_response call count = {handle_mock.call_count}")
    print(f"Actual: time.sleep call count = {sleep_mock.call_count}")
    assert get_mock.call_count == 1
    assert handle_mock.call_count == 0
    assert sleep_mock.call_count == 1
    print("Result: Passed - malformed update was ignored safely")


def test_listen_for_responses_timeout(monkeypatch):
    print_test_header(
        "listen_for_responses timeout",
        "requests.get raises Timeout",
        "The loop should print the timeout message, sleep once, and continue until the test stops it",
    )
    module = load_task_update(monkeypatch)

    get_mock = mock.Mock(side_effect=module.requests.exceptions.Timeout)
    sleep_mock = mock.Mock(side_effect=StopIteration("stop after timeout"))
    monkeypatch.setattr(module.requests, "get", get_mock)
    monkeypatch.setattr(module.time, "sleep", sleep_mock)

    with pytest.raises(StopIteration):
        module.listen_for_responses()

    print(f"Actual: requests.get call count = {get_mock.call_count}")
    print(f"Actual: time.sleep call count = {sleep_mock.call_count}")
    assert get_mock.call_count == 1
    assert sleep_mock.call_count == 1
    print("Result: Passed - timeout path was handled and retried once")


def test_listen_for_responses_connection_error(monkeypatch):
    print_test_header(
        "listen_for_responses connection error",
        "requests.get raises ConnectionError",
        "The loop should catch the connection error, sleep once, and continue until the test stops it",
    )
    module = load_task_update(monkeypatch)

    get_mock = mock.Mock(side_effect=module.requests.exceptions.ConnectionError)
    sleep_mock = mock.Mock(side_effect=StopIteration("stop after connection error"))
    monkeypatch.setattr(module.requests, "get", get_mock)
    monkeypatch.setattr(module.time, "sleep", sleep_mock)

    with pytest.raises(StopIteration):
        module.listen_for_responses()

    print(f"Actual: requests.get call count = {get_mock.call_count}")
    print(f"Actual: time.sleep call count = {sleep_mock.call_count}")
    assert get_mock.call_count == 1
    assert sleep_mock.call_count == 1
    print("Result: Passed - connection error path was handled and retried once")
