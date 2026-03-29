import importlib
import sys
from unittest.mock import Mock

import pytest

from backend.error_handling import DBConnectionError


def pstart(name, scenario, data, expected):
    print("\n==============================")
    print("TEST:", name)
    print("Scenario:", scenario)
    print("Input:", data)
    print("Expected:", expected)


def pend(actual, ok):
    print("Actual:", actual)
    print(f"RESULT: {'PASS ✅' if ok else 'FAIL ❌'}")


def load_mod(monkeypatch, bot="bot-token", chat="chat-id"):
    if bot is None:
        monkeypatch.delenv("BOT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("BOT_TOKEN", bot)
    if chat is None:
        monkeypatch.delenv("BOT_CHAT_ID", raising=False)
    else:
        monkeypatch.setenv("BOT_CHAT_ID", chat)
    sys.modules.pop("backend.agent_services.task_update", None)
    mod = importlib.import_module("backend.agent_services.task_update")
    mod.pending_questions.clear()
    mod.ACTIVE_SESSION = False
    mod.last_update_id = None
    return mod


def cb(qid="cb-1", chat_id=9, message_id=11):
    data = {"id": qid, "message": {"chat": {"id": chat_id}}}
    if message_id is not None:
        data["message"]["message_id"] = message_id
    return data


class Resp:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        print("Telegram response:", self.payload)
        return self.payload


class Cur:
    def __init__(self, rows=None, rowcounts=None, fail_call=None, fail_exc=None):
        self.rows = list(rows or [])
        self.rowcounts = list(rowcounts or [])
        self.fail_call = fail_call
        self.fail_exc = fail_exc
        self.queries = []
        self.rowcount = 0
        self.calls = 0

    def execute(self, query, params=None):
        self.calls += 1
        print("DB query:", " ".join(query.split()))
        print("DB params:", params)
        self.queries.append((query, params))
        if self.fail_call == self.calls:
            raise self.fail_exc
        if self.rowcounts:
            self.rowcount = self.rowcounts.pop(0)

    def fetchall(self):
        print("DB fetchall:", self.rows)
        return list(self.rows)

    def close(self):
        print("DB cursor closed")


class Conn:
    def __init__(self, cur):
        self.cur = cur
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        print("DB cursor requested")
        return self.cur

    def commit(self):
        self.commits += 1
        print("DB commit")

    def rollback(self):
        self.rollbacks += 1
        print("DB rollback")

    def close(self):
        print("DB connection closed")


def post_stub(calls, payload=None, exc=None):
    def _post(url, json=None, timeout=None):
        print("Telegram POST:", url, json, timeout)
        calls.append((url, json, timeout))
        if exc:
            raise exc
        return Resp(payload or {})

    return _post


def get_stub(calls, payload=None, exc=None):
    def _get(url, timeout=None):
        print("Telegram GET:", url, timeout)
        calls.append((url, timeout))
        if exc:
            raise exc
        return Resp(payload or {})

    return _get


def pmock(label):
    return Mock(side_effect=lambda *a, **k: print(f"{label}: args={a}, kwargs={k}"))


def test_fetch_pending_confirmations_no_rows_and_filters(monkeypatch):
    name = "test_fetch_pending_confirmations_no_rows_and_filters"
    pstart(name, "No pending records from DB.", {"rows": []}, "No queue, session off, and SQL contains the required filters.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    mod.ACTIVE_SESSION = True
    cur = Cur(rows=[])
    conn = Conn(cur)
    nxt = pmock("SEND_NEXT")
    monkeypatch.setattr(mod, "get_db_connection", lambda: conn)
    monkeypatch.setattr(mod, "send_next_question", nxt)
    try:
        mod.fetch_pending_confirmations()
        q = cur.queries[0][0]
        actual = {
            "pending": list(mod.pending_questions),
            "active": mod.ACTIVE_SESSION,
            "send_next": nxt.call_count,
            "action_required": "o.action_required = TRUE" in q,
            "deadline_filter": "o.deadline >= CURRENT_DATE" in q,
            "event_date_filter": "o.event_date::date >= CURRENT_DATE" in q,
            "cooldown_filter": "o.last_notified_at < NOW() - INTERVAL '4 hours'" in q,
            "notification_filter": "FROM notifications n" in q,
        }
        assert mod.pending_questions == []
        assert mod.ACTIVE_SESSION is False
        assert nxt.call_count == 0
        assert all(actual[k] for k in ("action_required", "deadline_filter", "event_date_filter", "cooldown_filter", "notification_filter"))
        ok = True
    finally:
        pend(actual, ok)


def test_fetch_pending_confirmations_adds_records(monkeypatch):
    name = "test_fetch_pending_confirmations_adds_records"
    rows = [(1, "Acme", "ASSESSMENT", "2026-04-01", None), (2, "Beta", "INTERVIEW", None, "2026-04-02")]
    pstart(name, "Valid rows returned from DB.", {"rows": rows}, "Rows enter pending_questions and send_next_question runs once.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    cur = Cur(rows=rows)
    conn = Conn(cur)
    nxt = pmock("SEND_NEXT")
    monkeypatch.setattr(mod, "get_db_connection", lambda: conn)
    monkeypatch.setattr(mod, "send_next_question", nxt)
    try:
        mod.fetch_pending_confirmations()
        actual = {"pending": list(mod.pending_questions), "active": mod.ACTIVE_SESSION, "send_next": nxt.call_count}
        assert [x["id"] for x in mod.pending_questions] == [1, 2]
        assert mod.ACTIVE_SESSION is True
        assert nxt.call_count == 1
        ok = True
    finally:
        pend(actual, ok)


def test_fetch_pending_confirmations_db_failure(monkeypatch):
    name = "test_fetch_pending_confirmations_db_failure"
    pstart(name, "DB connection fails.", {"exception": "DBConnectionError"}, "Function exits without queueing or sending.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    nxt = pmock("SEND_NEXT")
    monkeypatch.setattr(mod, "get_db_connection", Mock(side_effect=DBConnectionError("down")))
    monkeypatch.setattr(mod, "send_next_question", nxt)
    try:
        mod.fetch_pending_confirmations()
        actual = {"pending": list(mod.pending_questions), "active": mod.ACTIVE_SESSION, "send_next": nxt.call_count}
        assert mod.pending_questions == []
        assert nxt.call_count == 0
        ok = True
    finally:
        pend(actual, ok)


def test_send_confirmation_success_and_on_conflict(monkeypatch):
    name = "test_send_confirmation_success_and_on_conflict"
    pstart(name, "Assessment confirmation is sent successfully.", {"stage": "ASSESSMENT", "opportunity_id": 10}, "Telegram payload is correct, message_id is stored, ON CONFLICT is present, and last_notified_at updates.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    cur = Cur()
    conn = Conn(cur)
    posts = []
    monkeypatch.setattr(mod, "get_db_connection", lambda: conn)
    monkeypatch.setattr(mod.requests, "post", post_stub(posts, {"result": {"message_id": 777}}))
    try:
        mod.send_confirmation("Acme", "ASSESSMENT", 10, deadline="2026-04-05")
        payload = posts[0][1]
        actual = {"payload": payload, "queries": [" ".join(q.split()) for q, _ in cur.queries], "params": [p for _, p in cur.queries], "commits": conn.commits}
        assert payload["chat_id"] == "chat-id"
        assert payload["text"] == "Did you complete Acme assessment?\nDeadline: 2026-04-05"
        assert payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "confirm_10"
        assert payload["reply_markup"]["inline_keyboard"][0][1]["callback_data"] == "pending_10"
        assert payload["reply_markup"]["inline_keyboard"][0][2]["callback_data"] == "remove_10"
        assert "ON CONFLICT (opportunity_id) DO NOTHING" in cur.queries[0][0]
        assert cur.queries[0][1] == (10, 777)
        assert cur.queries[1][1] == (10,)
        assert conn.commits == 1
        ok = True
    finally:
        pend(actual, ok)


def test_send_confirmation_missing_env_timeout_and_missing_message_id(monkeypatch):
    name = "test_send_confirmation_missing_env_timeout_and_missing_message_id"
    pstart(name, "Missing env, timeout, and missing message_id edge cases.", {"cases": 3}, "Missing env skips work, timeout skips DB, and missing message_id stores None.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch, bot=None, chat=None)
    posts = []
    get_db = Mock()
    monkeypatch.setattr(mod.requests, "post", post_stub(posts, {"result": {"message_id": 1}}))
    monkeypatch.setattr(mod, "get_db_connection", get_db)
    mod.send_confirmation("A", "ASSESSMENT", 1, deadline="2026-04-01")

    mod2 = load_mod(monkeypatch)
    posts2 = []
    get_db2 = Mock(side_effect=AssertionError("DB should not run"))
    monkeypatch.setattr(mod2.requests, "post", post_stub(posts2, exc=mod2.requests.exceptions.Timeout("timeout")))
    monkeypatch.setattr(mod2, "get_db_connection", get_db2)
    mod2.send_confirmation("B", "INTERVIEW", 2, event_date="2026-04-02")

    mod3 = load_mod(monkeypatch)
    posts3 = []
    cur3 = Cur()
    conn3 = Conn(cur3)
    monkeypatch.setattr(mod3.requests, "post", post_stub(posts3, {"result": {}}))
    monkeypatch.setattr(mod3, "get_db_connection", lambda: conn3)
    try:
        mod3.send_confirmation("C", "INTERVIEW", 3, event_date="2026-04-03")
        actual = {
            "missing_env_posts": len(posts),
            "missing_env_db_calls": get_db.call_count,
            "timeout_posts": len(posts2),
            "timeout_db_calls": get_db2.call_count,
            "missing_message_id_insert": cur3.queries[0][1],
        }
        assert len(posts) == 0 and get_db.call_count == 0
        assert len(posts2) == 1 and get_db2.call_count == 0
        assert cur3.queries[0][1] == (3, None)
        ok = True
    finally:
        pend(actual, ok)


def test_send_next_question_first_only_and_empty(monkeypatch):
    name = "test_send_next_question_first_only_and_empty"
    pstart(name, "Queue has data, then becomes empty.", {"queue": 2}, "First call sends only first item; empty queue ends session.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    snd = pmock("SEND_CONFIRMATION")
    monkeypatch.setattr(mod, "send_confirmation", snd)
    mod.pending_questions[:] = [{"id": 1, "company": "A", "stage": "ASSESSMENT", "deadline": "2026-04-01", "event_date": None}, {"id": 2, "company": "B", "stage": "INTERVIEW", "deadline": None, "event_date": "2026-04-02"}]
    mod.send_next_question()
    mod.pending_questions.clear()
    mod.ACTIVE_SESSION = True
    mod.send_next_question()
    try:
        actual = {"first_args": snd.call_args.args, "calls": snd.call_count, "active_after_empty": mod.ACTIVE_SESSION}
        assert snd.call_args.args == ("A", "ASSESSMENT", 1, "2026-04-01", None)
        assert snd.call_count == 1
        assert mod.ACTIVE_SESSION is False
        ok = True
    finally:
        pend(actual, ok)


def test_update_message_after_click_yes_and_missing_message_id(monkeypatch):
    name = "test_update_message_after_click_yes_and_missing_message_id"
    pstart(name, "UI update works for YES and safely ignores missing message_id.", {"choice": "YES"}, "Chosen option changes visually, callback_data becomes done, and missing message_id makes no API call.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    posts = []
    monkeypatch.setattr(mod.requests, "post", post_stub(posts, {"ok": True}))
    mod.update_message_after_click(cb(), "YES")
    mod.update_message_after_click(cb(message_id=None), "NO")
    try:
        row = posts[0][1]["reply_markup"]["inline_keyboard"][0]
        actual = {"texts": [x["text"] for x in row], "callbacks": [x["callback_data"] for x in row], "post_calls": len(posts)}
        assert row[0]["text"] != "YES" and "YES" in row[0]["text"]
        assert row[1]["text"] == "NO"
        assert row[2]["text"] == "IRRELEVANT"
        assert [x["callback_data"] for x in row] == ["done", "done", "done"]
        assert len(posts) == 1
        ok = True
    finally:
        pend(actual, ok)


@pytest.mark.parametrize(
    ("name", "callback_data", "choice", "expected_sql"),
    [
        ("test_handle_response_yes", "confirm_55", "YES", "SET action_required = FALSE"),
        ("test_handle_response_no", "pending_56", "NO", "SET last_notified_at = CURRENT_TIMESTAMP"),
        ("test_handle_response_irrelevant", "remove_57", "IRRELEVANT", "DELETE FROM opportunities WHERE id = %s"),
    ],
)
def test_handle_response_main_paths(monkeypatch, name, callback_data, choice, expected_sql):
    pstart(name, f"{choice} is clicked first.", {"callback_data": callback_data}, "Lock is acquired, branch SQL runs, notification is deleted, and next question is triggered.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    mod.pending_questions[:] = [{"id": 99, "company": "A", "stage": "ASSESSMENT", "deadline": "2026-04-01", "event_date": None}]
    cur = Cur(rowcounts=[1])
    conn = Conn(cur)
    ack = pmock("ANSWER_CALLBACK")
    ui = pmock("UPDATE_MESSAGE")
    nxt = pmock("SEND_NEXT")
    monkeypatch.setattr(mod, "get_db_connection", lambda: conn)
    monkeypatch.setattr(mod, "answer_callback", ack)
    monkeypatch.setattr(mod, "update_message_after_click", ui)
    monkeypatch.setattr(mod, "send_next_question", nxt)
    query = cb(qid="cb-x")
    try:
        mod.handle_response(callback_data, query)
        queries = [" ".join(q.split()) for q, _ in cur.queries]
        actual = {"queries": queries, "commits": conn.commits, "rollbacks": conn.rollbacks, "ui": ui.call_args.args if ui.call_count else None, "send_next": nxt.call_count}
        assert ack.call_args.args == ("cb-x",)
        assert any("SET response_locked = TRUE" in q for q in queries)
        assert any(expected_sql in q for q in queries)
        assert any("DELETE FROM notifications WHERE opportunity_id = %s" in q for q in queries)
        assert ui.call_args.args == (query, choice)
        assert conn.commits == 1 and conn.rollbacks == 0
        assert nxt.call_count == 1
        ok = True
    finally:
        pend(actual, ok)


@pytest.mark.parametrize(
    ("name", "callback_data"),
    [
        ("test_duplicate_same_click_ignored", "confirm_58"),
        ("test_duplicate_different_click_ignored", "remove_58"),
    ],
)
def test_handle_response_duplicate_clicks_ignored(monkeypatch, name, callback_data):
    pstart(name, "Response is already locked before this click.", {"callback_data": callback_data, "rowcount": 0}, "Only ACK happens; no branch update, no commit, no next send.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    mod.pending_questions[:] = [{"id": 1, "company": "A", "stage": "ASSESSMENT", "deadline": "2026-04-01", "event_date": None}]
    cur = Cur(rowcounts=[0])
    conn = Conn(cur)
    ack = pmock("ANSWER_CALLBACK")
    ui = pmock("UPDATE_MESSAGE")
    nxt = pmock("SEND_NEXT")
    monkeypatch.setattr(mod, "get_db_connection", lambda: conn)
    monkeypatch.setattr(mod, "answer_callback", ack)
    monkeypatch.setattr(mod, "update_message_after_click", ui)
    monkeypatch.setattr(mod, "send_next_question", nxt)
    try:
        mod.handle_response(callback_data, cb())
        actual = {"queries": [" ".join(q.split()) for q, _ in cur.queries], "commits": conn.commits, "ui_calls": ui.call_count, "send_next": nxt.call_count}
        assert ack.call_count == 1
        assert len(cur.queries) == 1
        assert conn.commits == 0
        assert ui.call_count == 0
        assert nxt.call_count == 0
        ok = True
    finally:
        pend(actual, ok)


def test_handle_response_invalid_and_malformed_callbacks(monkeypatch):
    name = "test_handle_response_invalid_and_malformed_callbacks"
    pstart(name, "Empty callback_data and malformed callback_data are received.", {"callbacks": ["", "confirm_bad"]}, "Empty callback avoids DB; malformed callback rolls back and still triggers next question.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    mod.pending_questions[:] = [{"id": 1, "company": "A", "stage": "ASSESSMENT", "deadline": "2026-04-01", "event_date": None}]
    ack1 = pmock("ANSWER_CALLBACK_1")
    get_db1 = Mock(side_effect=AssertionError("DB should not run"))
    nxt1 = pmock("SEND_NEXT_1")
    monkeypatch.setattr(mod, "answer_callback", ack1)
    monkeypatch.setattr(mod, "get_db_connection", get_db1)
    monkeypatch.setattr(mod, "send_next_question", nxt1)
    mod.handle_response("", cb("cb-empty"))

    mod2 = load_mod(monkeypatch)
    mod2.pending_questions[:] = [{"id": 1, "company": "A", "stage": "ASSESSMENT", "deadline": "2026-04-01", "event_date": None}]
    cur2 = Cur()
    conn2 = Conn(cur2)
    ack2 = pmock("ANSWER_CALLBACK_2")
    ui2 = pmock("UPDATE_MESSAGE_2")
    nxt2 = pmock("SEND_NEXT_2")
    monkeypatch.setattr(mod2, "get_db_connection", lambda: conn2)
    monkeypatch.setattr(mod2, "answer_callback", ack2)
    monkeypatch.setattr(mod2, "update_message_after_click", ui2)
    monkeypatch.setattr(mod2, "send_next_question", nxt2)
    try:
        mod2.handle_response("confirm_bad", cb("cb-bad"))
        actual = {
            "empty_ack": ack1.call_count,
            "empty_db_calls": get_db1.call_count,
            "empty_send_next": nxt1.call_count,
            "malformed_rollbacks": conn2.rollbacks,
            "malformed_commits": conn2.commits,
            "malformed_ui": ui2.call_count,
            "malformed_send_next": nxt2.call_count,
        }
        assert ack1.call_count == 1 and get_db1.call_count == 0 and nxt1.call_count == 0
        assert conn2.rollbacks == 1 and conn2.commits == 0
        assert ui2.call_count == 0 and nxt2.call_count == 1
        ok = True
    finally:
        pend(actual, ok)


def test_listen_for_responses_valid_and_timeout(monkeypatch):
    name = "test_listen_for_responses_valid_and_timeout"
    pstart(name, "One valid polling cycle and one timeout cycle are simulated.", {"cycles": 2}, "Valid callback is dispatched with updated offset; timeout sleeps and exits cleanly.")
    ok = False
    actual = {}
    mod = load_mod(monkeypatch)
    mod.ACTIVE_SESSION = True
    gets = []
    handled = []

    def handle(data, query):
        print("HANDLE_RESPONSE:", data, query)
        handled.append((data, query))
        mod.ACTIVE_SESSION = False

    monkeypatch.setattr(mod.requests, "get", get_stub(gets, {"result": [{"update_id": 901, "callback_query": {"id": "l1", "data": "confirm_77", "message": {"chat": {"id": 7}, "message_id": 70}}}]}))
    monkeypatch.setattr(mod, "handle_response", handle)
    monkeypatch.setattr(mod.time, "sleep", lambda s: print("sleep", s))
    times = iter([0, 0, 1, 2, 3])
    monkeypatch.setattr(mod.time, "time", lambda: next(times))
    mod.listen_for_responses()

    mod2 = load_mod(monkeypatch)
    mod2.ACTIVE_SESSION = True
    gets2 = []
    sleeps2 = []
    monkeypatch.setattr(mod2.requests, "get", get_stub(gets2, exc=mod2.requests.exceptions.Timeout("poll timeout")))

    def sleep2(sec):
        print("sleep", sec)
        sleeps2.append(sec)
        mod2.ACTIVE_SESSION = False

    monkeypatch.setattr(mod2.time, "sleep", sleep2)
    times2 = iter([0, 0, 1, 2, 3])
    monkeypatch.setattr(mod2.time, "time", lambda: next(times2))
    try:
        mod2.listen_for_responses()
        actual = {"valid_gets": len(gets), "handled": handled, "last_update_id": mod.last_update_id, "timeout_gets": len(gets2), "timeout_sleeps": sleeps2}
        assert len(gets) == 1
        assert handled[0][0] == "confirm_77"
        assert mod.last_update_id == 901
        assert len(gets2) == 1
        assert sleeps2 == [2]
        ok = True
    finally:
        pend(actual, ok)
