import importlib
import io
import sys
from unittest import mock


def load_llm_worker():
    sys.modules.pop("backend.email_analyser.llm_worker", None)
    return importlib.import_module("backend.email_analyser.llm_worker")


def print_test_header(title, scenario, expected):
    print("\n==============================")
    print(f"TEST: {title}")
    print(f"Scenario: {scenario}")
    print(f"Expected: {expected}")
    print("==============================")


def run_worker_and_capture(module, monkeypatch):
    captured = io.StringIO()
    original_stdout = sys.stdout
    monkeypatch.setattr(sys, "stdout", captured)
    module.run()
    monkeypatch.setattr(sys, "stdout", original_stdout)
    return captured.getvalue().strip()


def configure_worker_io(monkeypatch, prompt="prompt text", model="gemini-model", temp="0.1"):
    monkeypatch.setattr(sys, "stdin", io.StringIO(prompt))
    monkeypatch.setattr(sys, "argv", ["llm_worker.py", model, temp])


def test_worker_success_response(monkeypatch):
    print_test_header(
        "Worker success response",
        "Gemini returns a response object with text",
        "The response text should be printed to stdout",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.return_value = mock.Mock(text="hello from gemini")
    client_factory = mock.Mock(return_value=mock_client)
    monkeypatch.setattr(module.genai, "Client", client_factory)

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    print(f"Actual: genai.Client call count = {client_factory.call_count}")
    print(
        "Actual: generate_content call count =",
        mock_client.models.generate_content.call_count,
    )
    assert client_factory.call_count == 1
    assert mock_client.models.generate_content.call_count == 1
    assert output == "hello from gemini"
    print("Result: Passed")


def test_worker_empty_response(monkeypatch):
    print_test_header(
        "Worker empty response",
        "Gemini returns an object with empty text",
        "ERROR::LLMAPIError should be printed",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.return_value = mock.Mock(text="")
    monkeypatch.setattr(module.genai, "Client", mock.Mock(return_value=mock_client))

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    assert output == "ERROR::LLMAPIError::Empty response"
    print("Result: Passed")


def test_worker_network_down(monkeypatch):
    print_test_header(
        "Worker network down",
        'Gemini throws an exception containing "getaddrinfo failed"',
        "ERROR::NetworkDownError should be printed",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.side_effect = Exception("getaddrinfo failed")
    monkeypatch.setattr(module.genai, "Client", mock.Mock(return_value=mock_client))

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    assert output == "ERROR::NetworkDownError"
    print("Result: Passed")


def test_worker_network_error(monkeypatch):
    print_test_header(
        "Worker network error",
        'Gemini throws retryable timeout/connection errors twice',
        "ERROR::NetworkError should be printed after one retry",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.side_effect = [
        Exception("timeout while connecting"),
        Exception("timeout while connecting"),
    ]
    sleep_mock = mock.Mock()
    monkeypatch.setattr(module.genai, "Client", mock.Mock(return_value=mock_client))
    monkeypatch.setattr(module.time, "sleep", sleep_mock)

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    print(
        "Actual: generate_content call count =",
        mock_client.models.generate_content.call_count,
    )
    print(f"Actual: time.sleep call count = {sleep_mock.call_count}")
    assert mock_client.models.generate_content.call_count == 2
    assert sleep_mock.call_count == 1
    assert output == "ERROR::NetworkError"
    print("Result: Passed")


def test_worker_rate_limit(monkeypatch):
    print_test_header(
        "Worker rate limit",
        'Gemini throws an exception containing "quota exceeded"',
        "ERROR::RateLimitError should be printed",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.side_effect = Exception("quota exceeded")
    monkeypatch.setattr(module.genai, "Client", mock.Mock(return_value=mock_client))

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    assert output == "ERROR::RateLimitError"
    print("Result: Passed")


def test_worker_auth_error(monkeypatch):
    print_test_header(
        "Worker authentication error",
        'Gemini throws an exception containing "api key invalid"',
        "ERROR::AuthenticationError should be printed",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.side_effect = Exception("api key invalid")
    monkeypatch.setattr(module.genai, "Client", mock.Mock(return_value=mock_client))

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    assert output == "ERROR::AuthenticationError"
    print("Result: Passed")


def test_worker_service_unavailable(monkeypatch):
    print_test_header(
        "Worker service unavailable",
        'Gemini throws an exception containing "503 service unavailable"',
        "ERROR::ServiceUnavailableError should be printed",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.side_effect = Exception("503 service unavailable")
    monkeypatch.setattr(module.genai, "Client", mock.Mock(return_value=mock_client))

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    assert output == "ERROR::ServiceUnavailableError"
    print("Result: Passed")


def test_worker_unknown_error(monkeypatch):
    print_test_header(
        "Worker unknown error",
        "Gemini throws an unrelated exception message",
        "ERROR::LLMAPIError::<message> should be printed",
    )
    module = load_llm_worker()
    configure_worker_io(monkeypatch)

    mock_client = mock.Mock()
    mock_client.models.generate_content.side_effect = Exception("something unexpected happened")
    monkeypatch.setattr(module.genai, "Client", mock.Mock(return_value=mock_client))

    output = run_worker_and_capture(module, monkeypatch)

    print(f"Actual Output: {output}")
    assert output == "ERROR::LLMAPIError::something unexpected happened"
    print("Result: Passed")
