# db_Repository.py
import json
from datetime import date, datetime



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
    """
    Inserts or updates an opportunity based on stage priority logic.
    Returns opportunity_id if inserted/updated, else None.
    """

    decision, record_id = decide_insert_or_update(
        cur,
        company=company,
        role=role,
        new_stage=pipeline_stage
    )

    # ---------------------------
    # INSERT
    # ---------------------------
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

    # ---------------------------
    # UPDATE
    # ---------------------------
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
        return record_id


    # ---------------------------
    # AMBIGUOUS or IGNORE
    # ---------------------------
    return None


def insert_opportunity_details(
    cur,
    opportunity_id: int,
    other_important_details: dict
) -> None:
    if not other_important_details:
        return

    query = """
        INSERT INTO opportunity_details (
            opportunity_id,
            details
        )
        VALUES (%s, %s);
    """

    cur.execute(
        query,
        (
            opportunity_id,
            json.dumps(other_important_details)
        )
    )


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
