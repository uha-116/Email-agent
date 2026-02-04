# db_Repository.py

import json
from datetime import date, datetime


# =========================================================
# 🔢 PIPELINE STAGE PRIORITY
# =========================================================

STAGE_PRIORITY = {
    "OPPORTUNITY_FOUND": 1,
    "APPLIED": 2,
    "SHORTLISTED": 3,
    "ASSESSMENT": 4,
    "INTERVIEW": 5,
    "SELECTED": 6,
    "REJECTED": 7
}


def get_stage_priority(stage: str) -> int:
    return STAGE_PRIORITY.get(stage, 0)


# =========================================================
# 🧠 INSERT vs UPDATE DECISION
# =========================================================

def decide_insert_or_update(
    cur,
    *,
    company: str,
    role: str | None,
    new_stage: str
):
    """
    Returns:
        ("INSERT", None)
        ("UPDATE", opportunity_id)
        ("IGNORE", None)
        ("AMBIGUOUS", None)
    """

    if role:
        cur.execute(
            """
            SELECT id, pipeline_stage
            FROM opportunities
            WHERE company = %s AND role = %s;
            """,
            (company, role)
        )
    else:
        cur.execute(
            """
            SELECT id, pipeline_stage
            FROM opportunities
            WHERE company = %s;
            """,
            (company,)
        )

    rows = cur.fetchall()

    if not rows:
        return "INSERT", None

    if not role and len(rows) > 1:
        return "AMBIGUOUS", None

    new_priority = get_stage_priority(new_stage)

    best_match = None
    best_priority = -1

    for opp_id, current_stage in rows:
        curr_priority = get_stage_priority(current_stage)

        if curr_priority <= new_priority and curr_priority > best_priority:
            best_match = opp_id
            best_priority = curr_priority

    if best_match is None:
        return "IGNORE", None

    return "UPDATE", best_match


# =========================================================
# 📩 EMAIL INSERT
# =========================================================

def insert_email(
    cur,
    gmail_message_id: str,
    sender: str,
    subject: str,
    email_type: str,
    received_at: datetime,
    raw_body_text: str
) -> int:
    query = """
        INSERT INTO emails (
            gmail_message_id,
            sender,
            subject,
            email_type,
            received_at,
            raw_body_text
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
    """

    cur.execute(
        query,
        (
            gmail_message_id,
            sender,
            subject,
            email_type,
            received_at,
            raw_body_text
        )
    )
    return cur.fetchone()[0]


# =========================================================
# 💼 OPPORTUNITY INSERT / UPDATE
# =========================================================

def insert_or_update_opportunity(
    cur,
    *,
    email_id: int,
    company: str,
    role: str | None,
    location: str | None,
    salary_amount: float | None,
    salary_period: str | None,
    min_experience_years: int | None,
    max_experience_years: int | None,
    pipeline_stage: str,
    action_required: bool,
    deadline: date | None,
    event_date: datetime | None
) -> int | None:

    decision, record_id = decide_insert_or_update(
        cur,
        company=company,
        role=role,
        new_stage=pipeline_stage
    )

    if decision == "INSERT":
        cur.execute(
            """
            INSERT INTO opportunities (
                email_id,
                company,
                role,
                location,
                salary_amount,
                salary_period,
                min_experience_years,
                max_experience_years,
                pipeline_stage,
                action_required,
                deadline,
                event_date,
                last_updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
            """,
            (
                email_id,
                company,
                role,
                location,
                salary_amount,
                salary_period,
                min_experience_years,
                max_experience_years,
                pipeline_stage,
                action_required,
                deadline,
                event_date
            )
        )
        return cur.fetchone()[0]

    if decision == "UPDATE":
        cur.execute(
            """
            UPDATE opportunities
            SET
                pipeline_stage = %s,
                action_required = %s,
                deadline = COALESCE(%s, deadline),
                event_date = COALESCE(%s, event_date),
                last_updated_at = NOW()
            WHERE id = %s;
            """,
            (
                pipeline_stage,
                action_required,
                deadline,
                event_date,
                record_id
            )
        )
        print("Updating the record", record_id)
        return record_id

    return None


# =========================================================
# 🧾 OPPORTUNITY DETAILS (ALWAYS REPLACE ✅)
# =========================================================

def insert_opportunity_details(
    cur,
    opportunity_id: int,
    other_important_details: dict | None
) -> None:
    """
    Always replace opportunity_details with the CURRENT mail's details.
    Old details must NEVER persist.
    """

    details = other_important_details or {}

    query = """
        INSERT INTO opportunity_details (opportunity_id, details)
        VALUES (%s, %s)
        ON CONFLICT (opportunity_id)
        DO UPDATE SET
            details = EXCLUDED.details;
    """

    cur.execute(
        query,
        (
            opportunity_id,
            json.dumps(details)
        )
    )


# =========================================================
# 🤝 LINKEDIN EVENTS
# =========================================================

def insert_linkedin_event(
    cur,
    email_id: int,
    person_name: str | None,
    person_title: str | None,
    person_company: str | None,
    interaction_type: str,
    requires_follow_up: bool
) -> int:
    query = """
        INSERT INTO linkedin_events (
            email_id,
            person_name,
            person_title,
            person_company,
            interaction_type,
            requires_follow_up
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
    """

    cur.execute(
        query,
        (
            email_id,
            person_name,
            person_title,
            person_company,
            interaction_type,
            requires_follow_up
        )
    )
    return cur.fetchone()[0]
