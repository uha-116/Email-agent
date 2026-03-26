from datetime import datetime
from unittest.mock import MagicMock

import pytest

import backend.db_storage.db_persistor as db_persistor
from backend.error_handling import DBConnectionError, NetworkDownError


def make_fake_db():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def test_persist_job_pipeline_success(monkeypatch, scenario_printer):
    conn, cur = make_fake_db()
    monkeypatch.setattr(db_persistor, "get_db_connection", lambda: conn)
    monkeypatch.setattr(db_persistor, "insert_email", lambda **kwargs: 11)
    monkeypatch.setattr(
        db_persistor,
        "insert_or_update_opportunity",
        lambda **kwargs: (21, "INSERT"),
    )
    details_calls = []
    monkeypatch.setattr(
        db_persistor,
        "insert_opportunity_details",
        lambda **kwargs: details_calls.append(kwargs),
    )

    payload = {
        "email_type": "JOB_PIPELINE",
        "sender": "Acme",
        "subject": "Interview",
        "opportunities": [
            {
                "company": "Acme",
                "role": "Engineer",
                "location": "Bangalore",
                "salary_amount": None,
                "salary_period": None,
                "min_experience_years": None,
                "max_experience_years": None,
                "pipeline_stage": "INTERVIEW",
                "action_required": True,
                "deadline": None,
                "event_date": None,
                "other_important_details": {"round": "HR"},
            }
        ],
    }

    result = db_persistor.persist_email_payload(
        payload=payload,
        gmail_message_id="msg-1",
        received_at=datetime(2026, 3, 23, 10, 0, 0),
        raw_body_text="body",
    )

    assert result["email_id"] == 11
    assert result["opportunity_changes"]["INSERT"] == [21]
    assert details_calls
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    cur.close.assert_called_once()
    conn.close.assert_called_once()
    scenario_printer(
        "Persist JOB_PIPELINE success",
        "No error; repository helpers all succeed",
        "Persistor should commit and return inserted identifiers",
        "Commit executed and result contains email/opportunity ids",
    )


def test_persist_linkedin_success(monkeypatch, scenario_printer):
    conn, cur = make_fake_db()
    monkeypatch.setattr(db_persistor, "get_db_connection", lambda: conn)
    monkeypatch.setattr(db_persistor, "insert_email", lambda **kwargs: 31)
    monkeypatch.setattr(db_persistor, "insert_linkedin_event", lambda **kwargs: 41)

    result = db_persistor.persist_email_payload(
        payload={
            "email_type": "LINKEDIN_NETWORKING",
            "sender": "LinkedIn",
            "subject": "Recruiter reached out",
            "linkedin_event": {
                "person_name": "Jane",
                "person_title": "Recruiter",
                "person_company": "Acme",
                "interaction_type": "RECRUITER_MESSAGE",
                "requires_follow_up": True,
            },
        },
        gmail_message_id="msg-2",
        received_at=datetime(2026, 3, 23, 10, 0, 0),
        raw_body_text="body",
    )

    assert result["email_id"] == 31
    assert result["linkedin_event_id"] == 41
    conn.commit.assert_called_once()
    scenario_printer(
        "Persist LINKEDIN_NETWORKING success",
        "No error; email and linkedin event inserts succeed",
        "Persistor should commit and return linkedin_event_id",
        "LinkedIn payload committed successfully",
    )


def test_ignore_payload_currently_returns_without_storing(monkeypatch, scenario_printer):
    conn, cur = make_fake_db()
    monkeypatch.setattr(db_persistor, "get_db_connection", lambda: conn)
    insert_email = MagicMock()
    monkeypatch.setattr(db_persistor, "insert_email", insert_email)

    result = db_persistor.persist_email_payload(
        payload={"email_type": "IGNORE", "subject": "newsletter"},
        gmail_message_id="msg-3",
        received_at=datetime(2026, 3, 23, 10, 0, 0),
        raw_body_text="body",
    )

    assert result["email_id"] is None
    insert_email.assert_not_called()
    conn.commit.assert_not_called()
    cur.close.assert_called_once()
    conn.close.assert_called_once()
    scenario_printer(
        "IGNORE persistence audit",
        "Payload email_type is IGNORE",
        "Current implementation should return early without storing",
        "Persistor exited early and did not call insert_email",
    )


def test_persist_rolls_back_and_wraps_unknown_error(monkeypatch, scenario_printer):
    conn, cur = make_fake_db()
    monkeypatch.setattr(db_persistor, "get_db_connection", lambda: conn)

    def explode(**kwargs):
        raise RuntimeError("insert failed")

    monkeypatch.setattr(db_persistor, "insert_email", explode)

    with pytest.raises(DBConnectionError, match="DB operation failed"):
        db_persistor.persist_email_payload(
            payload={"email_type": "JOB_PIPELINE", "opportunities": []},
            gmail_message_id="msg-4",
            received_at=datetime(2026, 3, 23, 10, 0, 0),
            raw_body_text="body",
        )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    scenario_printer(
        "Unknown DB insert failure",
        "insert_email raises RuntimeError",
        "Persistor should rollback and wrap error as DBConnectionError",
        "Rollback executed and DBConnectionError raised",
    )


def test_persist_preserves_structured_error(monkeypatch, scenario_printer):
    conn, cur = make_fake_db()
    monkeypatch.setattr(db_persistor, "get_db_connection", lambda: conn)

    def explode(**kwargs):
        raise NetworkDownError("offline")

    monkeypatch.setattr(db_persistor, "insert_email", explode)

    with pytest.raises(NetworkDownError):
        db_persistor.persist_email_payload(
            payload={"email_type": "JOB_PIPELINE", "opportunities": []},
            gmail_message_id="msg-5",
            received_at=datetime(2026, 3, 23, 10, 0, 0),
            raw_body_text="body",
        )

    conn.rollback.assert_called_once()
    scenario_printer(
        "Structured DB error passthrough",
        "insert_email raises NetworkDownError",
        "Persistor should rollback and re-raise the structured error",
        "Rollback executed and NetworkDownError propagated",
    )
