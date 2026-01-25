# db_repository.py
from datetime import datetime
from psycopg2.errors import UniqueViolation
from db_Connection import get_db_connection


def insert_email(
    gmail_message_id: str,
    sender: str,
    subject: str,
    email_type: str,
    received_at: datetime,
    raw_body_text: str
) -> int:
    """
    Inserts a record into the emails table.

    Returns:
        email_id (int)

    Raises:
        Exception if insert fails (except duplicate gmail_message_id)
    """

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

    conn = get_db_connection()
    cur = conn.cursor()

    try:
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
        email_id = cur.fetchone()[0]
        conn.commit()
        return email_id

    except UniqueViolation:
        conn.rollback()
        raise Exception(
            f"Email with gmail_message_id={gmail_message_id} already exists"
        )

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()

from datetime import date, datetime


def insert_opportunity(
    email_id: int,
    company: str,
    role: str,
    location: str | None,
    salary_amount: float | None,
    salary_period: str | None,
    min_experience_years: int | None,
    max_experience_years: int | None,
    pipeline_stage: str,
    action_required: bool,
    deadline: date | None,
    event_date: datetime | None
) -> int:
    """
    Inserts a record into the opportunities table.

    Returns:
        opportunity_id (int)
    """

    query = """
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
            event_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            query,
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
        opportunity_id = cur.fetchone()[0]
        conn.commit()
        return opportunity_id

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()

import json


def insert_opportunity_details(
    opportunity_id: int,
    other_important_details: dict
) -> None:
    """
    Inserts extra/unstructured details for an opportunity into JSONB table.
    """

    if not other_important_details:
        # Nothing to insert
        return

    query = """
        INSERT INTO opportunity_details (
            opportunity_id,
            details
        )
        VALUES (%s, %s);
    """

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            query,
            (
                opportunity_id,
                json.dumps(other_important_details)
            )
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()

def insert_linkedin_event(
    email_id: int,
    person_name: str | None,
    person_title: str | None,
    person_company: str | None,
    interaction_type: str,
    requires_follow_up: bool
) -> int:
    """
    Inserts a LinkedIn networking event.
    Returns linkedin_event_id.
    """

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

    conn = get_db_connection()
    cur = conn.cursor()

    try:
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
        linkedin_event_id = cur.fetchone()[0]
        conn.commit()
        return linkedin_event_id

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()


