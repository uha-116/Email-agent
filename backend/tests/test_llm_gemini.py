import importlib
import subprocess
import sys
from unittest import mock

import pytest

from backend.error_handling import (
    AuthenticationError,
    LLMAPIError,
    NetworkError,
    RateLimitError,
    ServiceUnavailableError,
)


def load_llm_gemini(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    sys.modules.pop("backend.email_analyser.llm_gemini", None)
    return importlib.import_module("backend.email_analyser.llm_gemini")


def print_test_header(title, scenario, expected):
    print("\n==============================")
    print(f"TEST: {title}")
    print(f"Scenario: {scenario}")
    print(f"Expected: {expected}")
    print("==============================")


def patch_common_runtime(monkeypatch, module):
    monkeypatch.setattr(module.time, "sleep", mock.Mock())


def test_call_llm_success(monkeypatch):
    print_test_header(
        "Gemini subprocess success",
        'subprocess.run returns stdout="valid response"',
        "call_llm should return the stdout text unchanged",
    )
    module = load_llm_gemini(monkeypatch)
    patch_common_runtime(monkeypatch, module)

    mock_run = mock.Mock(return_value=mock.Mock(stdout="valid response"))
    monkeypatch.setattr(module.subprocess, "run", mock_run)

    result = module.call_llm("hello prompt", "gemini-model", 0.2)

    print(f"Actual: subprocess.run call count = {mock_run.call_count}")
    print(f"Actual: returned value = {result!r}")
    assert mock_run.call_count == 1
    assert result == "valid response"
    print("Result: Passed - subprocess success output was returned correctly")


def test_call_llm_subprocess_timeout(monkeypatch):
    print_test_header(
        "Gemini subprocess timeout",
        "subprocess.run raises subprocess.TimeoutExpired",
        "LLMAPIError should be raised for worker timeout",
    )
    module = load_llm_gemini(monkeypatch)
    patch_common_runtime(monkeypatch, module)

    mock_run = mock.Mock(
        side_effect=subprocess.TimeoutExpired(cmd="worker", timeout=60)
    )
    monkeypatch.setattr(module.subprocess, "run", mock_run)

    with pytest.raises(LLMAPIError) as exc_info:
        module.call_llm("hello prompt", "gemini-model", 0.2)

    print(f"Actual: subprocess.run call count = {mock_run.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert mock_run.call_count == 1
    assert "timed out" in str(exc_info.value).lower()
    print("Result: Passed - subprocess timeout was converted into LLMAPIError")


def test_call_llm_empty_response(monkeypatch):
    print_test_header(
        "Gemini empty worker response",
        'subprocess.run returns stdout=""',
        "LLMAPIError should be raised for empty worker output",
    )
    module = load_llm_gemini(monkeypatch)
    patch_common_runtime(monkeypatch, module)

    mock_run = mock.Mock(return_value=mock.Mock(stdout=""))
    monkeypatch.setattr(module.subprocess, "run", mock_run)

    with pytest.raises(LLMAPIError) as exc_info:
        module.call_llm("hello prompt", "gemini-model", 0.2)

    print(f"Actual: subprocess.run call count = {mock_run.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert mock_run.call_count == 1
    assert "empty response" in str(exc_info.value).lower()
    print("Result: Passed - empty stdout was treated as LLMAPIError")


@pytest.mark.parametrize(
    "worker_output,expected_exception,title,expected_text",
    [
        ("ERROR::NetworkError", NetworkError, "Gemini worker network error", "NetworkError should be raised"),
        ("ERROR::RateLimitError", RateLimitError, "Gemini worker rate limit", "RateLimitError should be raised"),
        ("ERROR::AuthenticationError", AuthenticationError, "Gemini worker authentication error", "AuthenticationError should be raised"),
        ("ERROR::ServiceUnavailableError", ServiceUnavailableError, "Gemini worker service unavailable", "ServiceUnavailableError should be raised"),
    ],
)
def test_call_llm_known_worker_error_mappings(
    monkeypatch, worker_output, expected_exception, title, expected_text
):
    print_test_header(
        title,
        f"subprocess.run returns stdout={worker_output!r}",
        expected_text,
    )
    module = load_llm_gemini(monkeypatch)
    patch_common_runtime(monkeypatch, module)

    mock_run = mock.Mock(return_value=mock.Mock(stdout=worker_output))
    monkeypatch.setattr(module.subprocess, "run", mock_run)

    with pytest.raises(expected_exception) as exc_info:
        module.call_llm("hello prompt", "gemini-model", 0.2)

    print(f"Actual: subprocess.run call count = {mock_run.call_count}")
    print(f"Actual: raised exception type = {type(exc_info.value).__name__}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert mock_run.call_count == 1
    print("Result: Passed - worker error output mapped to the correct exception")


def test_call_llm_unknown_error_format(monkeypatch):
    print_test_header(
        "Gemini unknown worker error format",
        'subprocess.run returns stdout="ERROR::LLMAPIError::something"',
        "LLMAPIError should be raised for unrecognized worker error output",
    )
    module = load_llm_gemini(monkeypatch)
    patch_common_runtime(monkeypatch, module)

    mock_run = mock.Mock(
        return_value=mock.Mock(stdout="ERROR::LLMAPIError::something")
    )
    monkeypatch.setattr(module.subprocess, "run", mock_run)

    with pytest.raises(LLMAPIError) as exc_info:
        module.call_llm("hello prompt", "gemini-model", 0.2)

    print(f"Actual: subprocess.run call count = {mock_run.call_count}")
    print(f"Actual: raised exception = {exc_info.value}")
    assert mock_run.call_count == 1
    assert "llm api failed" in str(exc_info.value).lower()
    print("Result: Passed - unknown worker error format fell back to LLMAPIError")
