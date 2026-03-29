import importlib
import sys

import pytest

from backend.error_handling import LLMValidationError, NetworkError


def import_llm_module(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    if "backend.email_analyser.llm_gemini" in sys.modules:
        del sys.modules["backend.email_analyser.llm_gemini"]
    return importlib.import_module("backend.email_analyser.llm_gemini")


def import_email_analyser_module(monkeypatch):
    monkeypatch.setenv("EMAIL_EXTRACTION_MODEL", "test-model")
    if "backend.email_analyser.email_analyser" in sys.modules:
        del sys.modules["backend.email_analyser.email_analyser"]
    return importlib.import_module("backend.email_analyser.email_analyser")


def test_extract_json_supports_fenced_json(monkeypatch, scenario_printer):
    analyser = import_email_analyser_module(monkeypatch)

    data = analyser.extract_json(
        '```json\n[{"index": 0, "payload": {"email_type": "IGNORE"}}]\n```'
    )

    assert data[0]["payload"]["email_type"] == "IGNORE"
    scenario_printer(
        "Fenced JSON extraction",
        "LLM response wrapped in ```json fence",
        "extract_json should strip fencing and parse JSON",
        "IGNORE payload parsed successfully",
    )


def test_extract_json_rejects_invalid_json(monkeypatch, scenario_printer):
    analyser = import_email_analyser_module(monkeypatch)

    with pytest.raises(Exception):
        analyser.extract_json("not json at all")
    scenario_printer(
        "Invalid JSON extraction",
        "LLM response is not JSON",
        "extract_json should raise a parsing-related exception",
        "Invalid response was rejected",
    )


def test_analyze_email_batch_retries_then_succeeds(monkeypatch, scenario_printer):
    analyser = import_email_analyser_module(monkeypatch)
    calls = {"count": 0}

    def flaky_call(prompt, model, temp):
        calls["count"] += 1
        if calls["count"] == 1:
            raise NetworkError("temporary")
        return '[{"index": 0, "payload": {"email_type": "IGNORE"}}]'

    monkeypatch.setattr(analyser, "call_llm", flaky_call)

    result = analyser.analyze_email_batch([{"index": 0, "text": "hello"}])

    assert result[0]["payload"]["email_type"] == "IGNORE"
    assert calls["count"] == 2
    scenario_printer(
        "Analyzer retry success",
        "First call_llm raises NetworkError, second returns valid JSON",
        "Analyzer should retry and return validated payload",
        "Analyzer retried once and returned valid IGNORE payload",
    )


def test_analyze_email_batch_returns_partial_valid_items(monkeypatch, capsys, scenario_printer):
    analyser = import_email_analyser_module(monkeypatch)
    monkeypatch.setattr(
        analyser,
        "call_llm",
        lambda prompt, model, temp: (
            '[{"index": 0, "payload": {"email_type": "IGNORE"}}, '
            '{"index": 1, "payload": {"email_type": "JOB_PIPELINE", "opportunities": [{}]}}]'
        ),
    )

    result = analyser.analyze_email_batch(
        [{"index": 0, "text": "one"}, {"index": 1, "text": "two"}]
    )

    output = capsys.readouterr().out
    assert len(result) == 1
    assert result[0]["index"] == 0
    scenario_printer(
        "Analyzer partial-valid batch",
        "One LLM item valid and one invalid",
        "Analyzer should keep valid item and log invalid one",
        "One item returned and invalid item logged",
    )
    assert "Skipping LLM output at index 1" in output


def test_analyze_email_batch_raises_when_all_items_invalid(monkeypatch, scenario_printer):
    analyser = import_email_analyser_module(monkeypatch)
    monkeypatch.setattr(
        analyser,
        "call_llm",
        lambda prompt, model, temp: '[{"index": 0, "payload": {"email_type": "JOB_PIPELINE", "opportunities": [{}]}}]',
    )

    with pytest.raises(LLMValidationError, match="All items failed validation"):
        analyser.analyze_email_batch([{"index": 0, "text": "one"}])
    scenario_printer(
        "Analyzer all-invalid batch",
        "LLM returns only invalid items",
        "Analyzer should raise LLMValidationError",
        "LLMValidationError raised after validation found no valid items",
    )

