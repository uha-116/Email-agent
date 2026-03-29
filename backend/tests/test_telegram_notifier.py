import importlib
import sys
from unittest import mock

import pytest

from backend.error_handling import NetworkError, RateLimitError


def load_telegram_notifier(monkeypatch, bot_token="test-bot-token", chat_id="12345"):
    """Import telegram_notifier with the top-level error_handling alias in place."""
    if bot_token is None:
        monkeypatch.delenv("BOT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("BOT_TOKEN", bot_token)

    if chat_id is None:
        monkeypatch.delenv("BOT_CHAT_ID", raising=False)
    else:
        monkeypatch.setenv("BOT_CHAT_ID", chat_id)

    import backend.error_handling as backend_error_handling

    monkeypatch.setitem(sys.modules, "error_handling", backend_error_handling)
    sys.modules.pop("backend.agent_services.telegram_notifier", None)
    return importlib.import_module("backend.agent_services.telegram_notifier")


def print_test_header(title, scenario, expected):
    print("\n==============================")
    print(f"TEST: {title}")
    print(f"Scenario: {scenario}")
    print(f"Expected: {expected}")
    print("==============================")


def test_send_telegram_success_200(monkeypatch):
    print_test_header(
        "Telegram success",
        "requests.post returns HTTP 200 with valid JSON",
        "send_telegram should post exactly once and finish without error",
    )
    module = load_telegram_notifier(monkeypatch)

    response = mock.Mock()
    response.status_code = 200
    response.text = "OK"
    response.json.return_value = {"ok": True, "result": {"message_id": 10}}

    post_mock = mock.Mock(return_value=response)
    with mock.patch.object(module.requests, "post", post_mock):
        result = module.send_telegram("Hello from the test suite")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: function returned = {result}")
    assert post_mock.call_count == 1
    assert result is None
    print("Result: Passed - Telegram message was sent successfully")


def test_send_telegram_timeout_raises_network_error(monkeypatch):
    print_test_header(
        "Telegram timeout handling",
        "requests.post raises Timeout",
        "NetworkError should be raised with the timeout message",
    )
    module = load_telegram_notifier(monkeypatch)

    with mock.patch.object(
        module.requests,
        "post",
        side_effect=module.requests.exceptions.Timeout,
    ) as post_mock:
        with pytest.raises(NetworkError) as exc_info:
            module.send_telegram("Timeout test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert post_mock.call_count == 1
    assert "Telegram timeout" in str(exc_info.value)
    print("Result: Passed - timeout was converted into NetworkError")


def test_send_telegram_connection_error_raises_network_error(monkeypatch):
    print_test_header(
        "Telegram connection handling",
        "requests.post raises ConnectionError",
        "NetworkError should be raised with the connection failure message",
    )
    module = load_telegram_notifier(monkeypatch)

    with mock.patch.object(
        module.requests,
        "post",
        side_effect=module.requests.exceptions.ConnectionError,
    ) as post_mock:
        with pytest.raises(NetworkError) as exc_info:
            module.send_telegram("Connection error test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert post_mock.call_count == 1
    assert "Telegram connection failed" in str(exc_info.value)
    print("Result: Passed - connection error was converted into NetworkError")


def test_send_telegram_request_exception_raises_network_error(monkeypatch):
    print_test_header(
        "Telegram request exception handling",
        "requests.post raises generic RequestException",
        "NetworkError should wrap the underlying request failure",
    )
    module = load_telegram_notifier(monkeypatch)

    with mock.patch.object(
        module.requests,
        "post",
        side_effect=module.requests.exceptions.RequestException("boom"),
    ) as post_mock:
        with pytest.raises(NetworkError) as exc_info:
            module.send_telegram("Request exception test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert post_mock.call_count == 1
    assert "Telegram request failed" in str(exc_info.value)
    print("Result: Passed - RequestException was wrapped into NetworkError")


def test_send_telegram_rate_limit_raises_rate_limit_error(monkeypatch):
    print_test_header(
        "Telegram rate limit handling",
        "Telegram API returns HTTP 429",
        "RateLimitError should be raised immediately",
    )
    module = load_telegram_notifier(monkeypatch)

    response = mock.Mock()
    response.status_code = 429
    response.text = "Too Many Requests"
    response.json.return_value = {"ok": False}

    with mock.patch.object(module.requests, "post", return_value=response) as post_mock:
        with pytest.raises(RateLimitError) as exc_info:
            module.send_telegram("Rate limit test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert post_mock.call_count == 1
    assert "Telegram rate limit" in str(exc_info.value)
    print("Result: Passed - 429 response mapped to RateLimitError")


def test_send_telegram_server_error_raises_network_error(monkeypatch):
    print_test_header(
        "Telegram server error handling",
        "Telegram API returns HTTP 500",
        "NetworkError should be raised for 5xx responses",
    )
    module = load_telegram_notifier(monkeypatch)

    response = mock.Mock()
    response.status_code = 500
    response.text = "Internal Server Error"
    response.json.return_value = {"ok": False}

    with mock.patch.object(module.requests, "post", return_value=response) as post_mock:
        with pytest.raises(NetworkError) as exc_info:
            module.send_telegram("Server error test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert post_mock.call_count == 1
    assert "Telegram server error" in str(exc_info.value)
    print("Result: Passed - 5xx response mapped to NetworkError")


def test_send_telegram_bad_request_returns_none(monkeypatch):
    print_test_header(
        "Telegram bad request handling",
        "Telegram API returns HTTP 400",
        "Function should log the error and return without raising",
    )
    module = load_telegram_notifier(monkeypatch)

    response = mock.Mock()
    response.status_code = 400
    response.text = "Bad Request"
    response.json.return_value = {"ok": False}

    with mock.patch.object(module.requests, "post", return_value=response) as post_mock:
        result = module.send_telegram("Bad request test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: function returned = {result}")
    assert post_mock.call_count == 1
    assert result is None
    print("Result: Passed - 400 response was handled without crashing")


def test_send_telegram_invalid_json_response(monkeypatch):
    print_test_header(
        "Telegram invalid JSON handling",
        "Telegram API returns HTTP 200 but response.json() raises ValueError",
        "Function should print a warning and return cleanly",
    )
    module = load_telegram_notifier(monkeypatch)

    response = mock.Mock()
    response.status_code = 200
    response.text = "not-json"
    response.json.side_effect = ValueError("invalid json")

    with mock.patch.object(module.requests, "post", return_value=response) as post_mock:
        result = module.send_telegram("Invalid JSON test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: function returned = {result}")
    assert post_mock.call_count == 1
    assert result is None
    print("Result: Passed - invalid JSON response did not crash the notifier")


def test_send_telegram_missing_bot_token_skips_request(monkeypatch):
    print_test_header(
        "Missing BOT_TOKEN handling",
        "BOT_TOKEN is empty at import time",
        "Function should skip the network call and return immediately",
    )
    module = load_telegram_notifier(monkeypatch, bot_token="", chat_id="12345")

    post_mock = mock.Mock()
    with mock.patch.object(module.requests, "post", post_mock):
        result = module.send_telegram("Missing token test")

    print(f"Actual: requests.post call count = {post_mock.call_count}")
    print(f"Actual: module.BOT_TOKEN = {module.BOT_TOKEN!r}")
    print(f"Actual: function returned = {result}")
    assert post_mock.call_count == 0
    assert result is None
    print("Result: Passed - missing token short-circuited before request")
