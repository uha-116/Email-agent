import pytest

from backend.error_handling import NetworkDownError, NetworkError, retry


def test_retry_retries_then_succeeds(capsys, scenario_printer):
    state = {"calls": 0}

    @retry(max_attempts=2)
    def flaky():
        state["calls"] += 1
        if state["calls"] == 1:
            raise NetworkError("temporary")
        return "ok"

    assert flaky() == "ok"
    assert state["calls"] == 2
    scenario_printer(
        "Retry success case",
        "First call raises NetworkError, second call succeeds",
        "Decorator retries once and returns success",
        "Function retried once and returned 'ok'",
    )
    assert "Retry 1/2 for flaky" in capsys.readouterr().out


def test_retry_raises_after_exhausting_attempts(capsys, scenario_printer):
    state = {"calls": 0}

    @retry(max_attempts=2)
    def flaky():
        state["calls"] += 1
        raise NetworkError("temporary")

    with pytest.raises(NetworkError):
        flaky()

    output = capsys.readouterr().out
    assert state["calls"] == 2
    scenario_printer(
        "Retry exhaustion case",
        "Every call raises NetworkError",
        "Decorator retries up to max_attempts then raises final error",
        "Function retried twice and raised NetworkError",
    )
    assert "Retry 1/2 for flaky" in output
    assert "Failed in flaky" in output


def test_retry_does_not_retry_non_retryable_error(capsys, scenario_printer):
    state = {"calls": 0}

    @retry(max_attempts=3)
    def fail_fast():
        state["calls"] += 1
        raise NetworkDownError("offline")

    with pytest.raises(NetworkDownError):
        fail_fast()

    output = capsys.readouterr().out
    assert state["calls"] == 1
    scenario_printer(
        "Non-retryable stop case",
        "Function raises NetworkDownError",
        "Decorator should not retry",
        "Function was called once and failed immediately",
    )
    assert "Retry" not in output
    assert "Failed in fail_fast" in output


def test_retry_ignores_non_base_app_errors(scenario_printer):
    @retry(max_attempts=2)
    def crash():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        crash()
    scenario_printer(
        "Non-BaseAppError passthrough",
        "Function raises RuntimeError",
        "Decorator should not intercept non-BaseAppError exceptions",
        "RuntimeError propagated directly",
    )
