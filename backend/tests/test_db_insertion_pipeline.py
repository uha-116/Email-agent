import importlib
import sys
import types
from unittest.mock import MagicMock

from backend.error_handling import AuthenticationError, DBConnectionError, NetworkDownError, NetworkError


def import_pipeline_module():
    if "backend.db_storage.db_insertion" in sys.modules:
        del sys.modules["backend.db_storage.db_insertion"]
    return importlib.import_module("backend.db_storage.db_insertion")


def fake_service(messages, metadata_by_id):
    class Request:
        def __init__(self, response):
            self.response = response

        def execute(self):
            if isinstance(self.response, Exception):
                raise self.response
            return self.response

    class MessagesApi:
        def list(self, **kwargs):
            return Request({"messages": messages})

        def get(self, userId, id, format):
            if format == "metadata":
                return Request(metadata_by_id[id])
            raise AssertionError(f"Unexpected format {format}")

    class UsersApi:
        def messages(self):
            return MessagesApi()

    return types.SimpleNamespace(users=lambda: UsersApi())


def fake_db():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def test_main_stops_when_gmail_service_fails(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    monkeypatch.setattr(
        pipeline, "get_gmail_service", lambda: (_ for _ in ()).throw(NetworkDownError())
    )

    pipeline.main()

    scenario_printer(
        "Pipeline STOP on Gmail setup failure",
        "get_gmail_service raises NetworkDownError",
        "main should stop immediately and print critical error",
        "Pipeline returned early and printed CRITICAL message",
    )
    assert "CRITICAL" in capsys.readouterr().out


def test_main_skips_duplicate_email_without_downstream_calls(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    service = fake_service(
        messages=[{"id": "dup-1"}],
        metadata_by_id={"dup-1": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "dup"}},
    )
    conn, cur = fake_db()
    get_clean = MagicMock()
    analyze = MagicMock()
    persist = MagicMock()

    monkeypatch.setattr(pipeline, "get_gmail_service", lambda: service)
    monkeypatch.setattr(pipeline, "compute_start_date", lambda: "2026/03/01")
    monkeypatch.setattr(pipeline, "get_db_connection", lambda: conn)
    monkeypatch.setattr(pipeline, "email_already_processed", lambda cur, msg_id: True)
    monkeypatch.setattr(pipeline, "get_clean_email_text", get_clean)
    monkeypatch.setattr(pipeline, "analyze_email_batch", analyze)
    monkeypatch.setattr(pipeline, "persist_email_payload", persist)

    pipeline.main()

    output = capsys.readouterr().out
    scenario_printer(
        "Duplicate email SKIP",
        "email_already_processed returns True",
        "Pipeline should skip current email and avoid content/LLM/DB persistence",
        "Email skipped with no downstream calls",
    )
    assert "Already processed" in output
    get_clean.assert_not_called()
    analyze.assert_not_called()
    persist.assert_not_called()


def test_main_skips_low_confidence_and_continues(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    service = fake_service(
        messages=[{"id": "m1"}, {"id": "m2"}],
        metadata_by_id={
            "m1": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "one"},
            "m2": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "two"},
        },
    )
    conn, cur = fake_db()
    clean_calls = []
    analyze = MagicMock()

    def get_clean(service, message_id):
        clean_calls.append(message_id)
        return {"received_at": None, "raw_text": f"text-{message_id}"}

    conf_scores = {"m1": 0.1, "m2": 0.9}

    def compute_conf(raw_text):
        return conf_scores[raw_text.split("-")[-1]]

    monkeypatch.setattr(pipeline, "get_gmail_service", lambda: service)
    monkeypatch.setattr(pipeline, "compute_start_date", lambda: "2026/03/01")
    monkeypatch.setattr(pipeline, "get_db_connection", lambda: conn)
    monkeypatch.setattr(pipeline, "email_already_processed", lambda cur, msg_id: False)
    monkeypatch.setattr(pipeline, "get_clean_email_text", get_clean)
    monkeypatch.setattr(pipeline, "compute_job_confidence", compute_conf)
    monkeypatch.setattr(pipeline, "analyze_email_batch", analyze)
    monkeypatch.setattr(pipeline.time, "sleep", lambda n: None)

    pipeline.main()

    output = capsys.readouterr().out
    scenario_printer(
        "Low-confidence email SKIP",
        "First processed email scores below threshold",
        "Pipeline should skip low-confidence email and continue scanning",
        "Low-confidence branch triggered and later email was still fetched",
    )
    assert "Skipped (low confidence)" in output
    assert clean_calls == ["m2", "m1"]
    analyze.assert_not_called()


def test_main_stops_on_llm_network_down(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    service = fake_service(
        messages=[{"id": "m1"}, {"id": "m2"}],
        metadata_by_id={
            "m1": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "one"},
            "m2": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "two"},
        },
    )
    conn, cur = fake_db()

    monkeypatch.setattr(pipeline, "get_gmail_service", lambda: service)
    monkeypatch.setattr(pipeline, "compute_start_date", lambda: "2026/03/01")
    monkeypatch.setattr(pipeline, "get_db_connection", lambda: conn)
    monkeypatch.setattr(pipeline, "email_already_processed", lambda cur, msg_id: False)
    monkeypatch.setattr(
        pipeline,
        "get_clean_email_text",
        lambda service, message_id: {"received_at": None, "raw_text": "job application"},
    )
    monkeypatch.setattr(pipeline, "compute_job_confidence", lambda text: 0.9)
    monkeypatch.setattr(
        pipeline,
        "analyze_email_batch",
        lambda batch: (_ for _ in ()).throw(NetworkDownError()),
    )

    pipeline.main()

    scenario_printer(
        "Pipeline STOP on LLM network-down",
        "analyze_email_batch raises NetworkDownError",
        "Pipeline should stop immediately",
        "Pipeline returned early with NETWORK DOWN output",
    )
    assert "NETWORK DOWN" in capsys.readouterr().out


def test_main_skips_batch_on_temporary_llm_error(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    service = fake_service(
        messages=[{"id": "m1"}, {"id": "m2"}, {"id": "m3"}],
        metadata_by_id={
            "m1": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "one"},
            "m2": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "two"},
            "m3": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "three"},
        },
    )
    conn, cur = fake_db()
    persisted = []
    calls = {"count": 0}

    def flaky_analyze(batch):
        calls["count"] += 1
        if calls["count"] == 1:
            raise NetworkError("temporary")
        return [{"index": 0, "payload": {"email_type": "IGNORE"}}]

    monkeypatch.setattr(pipeline, "get_gmail_service", lambda: service)
    monkeypatch.setattr(pipeline, "compute_start_date", lambda: "2026/03/01")
    monkeypatch.setattr(pipeline, "get_db_connection", lambda: conn)
    monkeypatch.setattr(pipeline, "email_already_processed", lambda cur, msg_id: False)
    monkeypatch.setattr(
        pipeline,
        "get_clean_email_text",
        lambda service, message_id: {"received_at": None, "raw_text": f"job-{message_id}"},
    )
    monkeypatch.setattr(pipeline, "compute_job_confidence", lambda text: 0.9)
    monkeypatch.setattr(pipeline, "analyze_email_batch", flaky_analyze)
    monkeypatch.setattr(pipeline, "persist_email_payload", lambda **kwargs: persisted.append(kwargs))
    monkeypatch.setattr(pipeline.time, "sleep", lambda n: None)

    pipeline.main()

    output = capsys.readouterr().out
    scenario_printer(
        "Temporary LLM batch SKIP",
        "analyze_email_batch raises NetworkError",
        "Pipeline should skip current batch, clear it, and continue",
        "Batch skipped and no persistence happened",
    )
    assert "LLM TEMP ERROR" in output
    assert calls["count"] == 1
    assert persisted == []


def test_main_stops_on_llm_auth_error(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    service = fake_service(
        messages=[{"id": "m1"}, {"id": "m2"}],
        metadata_by_id={
            "m1": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "one"},
            "m2": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "two"},
        },
    )
    conn, cur = fake_db()

    monkeypatch.setattr(pipeline, "get_gmail_service", lambda: service)
    monkeypatch.setattr(pipeline, "compute_start_date", lambda: "2026/03/01")
    monkeypatch.setattr(pipeline, "get_db_connection", lambda: conn)
    monkeypatch.setattr(pipeline, "email_already_processed", lambda cur, msg_id: False)
    monkeypatch.setattr(
        pipeline,
        "get_clean_email_text",
        lambda service, message_id: {"received_at": None, "raw_text": "job application"},
    )
    monkeypatch.setattr(pipeline, "compute_job_confidence", lambda text: 0.9)
    monkeypatch.setattr(
        pipeline,
        "analyze_email_batch",
        lambda batch: (_ for _ in ()).throw(AuthenticationError("bad key")),
    )

    pipeline.main()

    scenario_printer(
        "Pipeline STOP on LLM auth error",
        "analyze_email_batch raises AuthenticationError",
        "Pipeline should stop immediately",
        "Pipeline returned early with auth error output",
    )
    assert "LLM AUTH ERROR" in capsys.readouterr().out


def test_main_handles_partial_db_failure_inside_batch_and_continues(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    service = fake_service(
        messages=[{"id": "m1"}, {"id": "m2"}, {"id": "m3"}, {"id": "m4"}],
        metadata_by_id={
            "m1": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "one"},
            "m2": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "two"},
            "m3": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "three"},
            "m4": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "four"},
        },
    )
    conn, cur = fake_db()
    persisted = []

    monkeypatch.setattr(pipeline, "get_gmail_service", lambda: service)
    monkeypatch.setattr(pipeline, "compute_start_date", lambda: "2026/03/01")
    monkeypatch.setattr(pipeline, "get_db_connection", lambda: conn)
    monkeypatch.setattr(pipeline, "email_already_processed", lambda cur, msg_id: False)
    monkeypatch.setattr(
        pipeline,
        "get_clean_email_text",
        lambda service, message_id: {"received_at": None, "raw_text": f"job-{message_id}"},
    )
    monkeypatch.setattr(pipeline, "compute_job_confidence", lambda text: 0.9)
    monkeypatch.setattr(
        pipeline,
        "analyze_email_batch",
        lambda batch: [
            {"index": 0, "payload": {"email_type": "JOB_PIPELINE"}},
            {"index": 1, "payload": {"email_type": "JOB_PIPELINE"}},
        ],
    )

    def persist(**kwargs):
        msg_id = kwargs["gmail_message_id"]
        persisted.append(msg_id)
        if msg_id == "m2":
            raise Exception("insert failed")

    monkeypatch.setattr(pipeline, "persist_email_payload", persist)
    monkeypatch.setattr(pipeline.time, "sleep", lambda n: None)

    pipeline.main()

    output = capsys.readouterr().out
    scenario_printer(
        "Partial DB failure inside batch",
        "persist_email_payload raises generic Exception for one item",
        "Pipeline should skip failed item and continue with later items",
        "Failure was logged and later batch items were still persisted",
    )
    assert "DB insert failed" in output
    assert persisted == ["m4", "m3", "m2", "m1"]


def test_main_stops_on_db_connection_error_during_insert(monkeypatch, capsys, scenario_printer):
    pipeline = import_pipeline_module()
    service = fake_service(
        messages=[{"id": "m1"}, {"id": "m2"}],
        metadata_by_id={
            "m1": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "one"},
            "m2": {"labelIds": ["INBOX", "CATEGORY_UPDATES"], "snippet": "two"},
        },
    )
    conn, cur = fake_db()
    persisted = []

    monkeypatch.setattr(pipeline, "get_gmail_service", lambda: service)
    monkeypatch.setattr(pipeline, "compute_start_date", lambda: "2026/03/01")
    monkeypatch.setattr(pipeline, "get_db_connection", lambda: conn)
    monkeypatch.setattr(pipeline, "email_already_processed", lambda cur, msg_id: False)
    monkeypatch.setattr(
        pipeline,
        "get_clean_email_text",
        lambda service, message_id: {"received_at": None, "raw_text": "job application"},
    )
    monkeypatch.setattr(pipeline, "compute_job_confidence", lambda text: 0.9)
    monkeypatch.setattr(
        pipeline,
        "analyze_email_batch",
        lambda batch: [
            {"index": 0, "payload": {"email_type": "JOB_PIPELINE"}},
            {"index": 1, "payload": {"email_type": "JOB_PIPELINE"}},
        ],
    )

    def persist(**kwargs):
        persisted.append(kwargs["gmail_message_id"])
        if kwargs["gmail_message_id"] == "m2":
            raise DBConnectionError("db unavailable")

    monkeypatch.setattr(pipeline, "persist_email_payload", persist)
    monkeypatch.setattr(pipeline.time, "sleep", lambda n: None)

    pipeline.main()

    output = capsys.readouterr().out
    scenario_printer(
        "Pipeline STOP on DBConnectionError during insert",
        "persist_email_payload raises DBConnectionError on first processed item",
        "Pipeline should stop immediately and not process later items",
        "Pipeline stopped after first insert attempt",
    )
    assert "DB ERROR during insert" in output
    assert persisted == ["m2"]
