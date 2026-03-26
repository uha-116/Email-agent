import types

import pytest

from backend.error_handling import Base64DecodeError, GmailFetchError, MessageNotFoundError, NetworkDownError
import backend.email_fetcher.inbox as inbox


class FakeResp:
    def __init__(self, status):
        self.status = status


class FakeHttpError(inbox.HttpError):
    def __init__(self, status, message="http error"):
        super().__init__(resp=FakeResp(status), content=message)
        self.resp = FakeResp(status)

    def __str__(self):
        return str(self.content)


def make_service(response=None, exc=None):
    execute = types.SimpleNamespace(
        execute=(lambda: (_ for _ in ()).throw(exc)) if exc else (lambda: response)
    )
    messages_obj = types.SimpleNamespace(get=lambda **kwargs: execute)
    users_obj = types.SimpleNamespace(messages=lambda: messages_obj)
    return types.SimpleNamespace(users=lambda: users_obj)


def test_get_clean_email_text_returns_plain_text(scenario_printer):
    encoded = "SGVsbG8gd29ybGQ="
    service = make_service(
        response={
            "id": "msg-1",
            "payload": {
                "headers": [{"name": "Subject", "value": "Hi"}],
                "mimeType": "multipart/alternative",
                "parts": [{"mimeType": "text/plain", "body": {"data": encoded}}],
            },
        }
    )

    result = inbox.get_clean_email_text(service, "msg-1")

    assert result["gmail_message_id"] == "msg-1"
    assert result["subject"] == "Hi"
    assert "Hello world" in result["raw_text"]
    scenario_printer(
        "Plain-text email fetch success",
        "No error; Gmail full message includes text/plain body",
        "Fetcher should parse and return raw_text",
        "raw_text returned with decoded plain text",
    )


def test_get_clean_email_text_raises_on_empty_payload(scenario_printer):
    service = make_service(response={"id": "msg-1", "payload": {}})

    with pytest.raises(GmailFetchError, match="Empty payload"):
        inbox.get_clean_email_text(service, "msg-1")
    scenario_printer(
        "Empty payload",
        "Gmail response has empty payload",
        "Fetcher should raise GmailFetchError",
        "GmailFetchError raised for empty payload",
    )


def test_decode_base64_raises_base64_decode_error(monkeypatch, scenario_printer):
    monkeypatch.setattr(
        inbox.base64,
        "urlsafe_b64decode",
        lambda data: (_ for _ in ()).throw(ValueError("bad base64")),
    )

    with pytest.raises(Base64DecodeError):
        inbox.decode_base64("bad")
    scenario_printer(
        "Base64 decode error",
        "urlsafe_b64decode raises ValueError",
        "Decoder should translate it to Base64DecodeError",
        "Base64DecodeError raised",
    )


def test_get_clean_email_text_translates_404_to_message_not_found(scenario_printer):
    service = make_service(exc=FakeHttpError(404, "missing"))

    with pytest.raises(MessageNotFoundError):
        inbox.get_clean_email_text(service, "msg-404")
    scenario_printer(
        "Gmail 404",
        "HttpError with status 404",
        "Fetcher should raise MessageNotFoundError",
        "MessageNotFoundError raised",
    )


def test_get_clean_email_text_translates_dns_failure(scenario_printer):
    service = make_service(exc=RuntimeError("getaddrinfo failed"))

    with pytest.raises(NetworkDownError):
        inbox.get_clean_email_text(service, "msg-net")
    scenario_printer(
        "Gmail DNS failure",
        "Generic exception contains getaddrinfo failed",
        "Fetcher should raise NetworkDownError",
        "NetworkDownError raised",
    )


def test_compute_job_confidence_empty_text_returns_zero(scenario_printer):
    assert inbox.compute_job_confidence("") == 0.0
    scenario_printer(
        "Empty text confidence",
        "No content provided",
        "Confidence score should be zero",
        "Returned 0.0",
    )
