# db_repository.py

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
    """

    # Look for existing record for same company + stage
    cur.execute(
        """
        SELECT id
        FROM opportunities
        WHERE LOWER(company) = LOWER(%s)
        AND pipeline_stage = %s;
        """,
        (company, new_stage)
    )

    row = cur.fetchone()

    if not row:
        return "INSERT", None

    # Existing record found → update it
    return "UPDATE", row[0]


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
    event_date: datetime | None,
    received_at: datetime,
) -> tuple[int, str] | None:

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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                event_date,
                received_at
            )
        )
        opp_id = cur.fetchone()[0]     # ✅ FIX 2
        return opp_id, "INSERT"        # ✅ FIX 3

    if decision == "UPDATE":

        cur.execute(
            """
            UPDATE opportunities
            SET
                role =
                    CASE
                        WHEN LENGTH(COALESCE(%s,'')) > LENGTH(COALESCE(role,''))
                        THEN %s
                        ELSE role
                    END,

                location = COALESCE(location, %s),

                salary_amount = COALESCE(salary_amount, %s),
                salary_period = COALESCE(salary_period, %s),

                min_experience_years = COALESCE(min_experience_years, %s),
                max_experience_years = COALESCE(max_experience_years, %s),

                pipeline_stage = %s,

                action_required = opportunities.action_required OR %s,

                deadline = COALESCE(%s, deadline),

                event_date = COALESCE(%s, event_date),

                last_updated_at = GREATEST(last_updated_at, %s)

            WHERE id = %s;
            """,
            (
                role,
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
                received_at,
                record_id
            )
        )

        print("Updating the record", record_id)
        return record_id,"UPDATE"

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

    # 🔎 Check if recruiter already exists
    cur.execute(
        """
        SELECT id
        FROM linkedin_events
        WHERE person_name ILIKE %s
        AND person_company ILIKE %s;
        """,
        (person_name, person_company)
    )

    row = cur.fetchone()

    # 🔁 UPDATE existing event
    if row:
        event_id = row[0]

        cur.execute(
            """
            UPDATE linkedin_events
            SET
                email_id = %s,
                person_title = %s,
                interaction_type = %s,
                requires_follow_up = %s
            WHERE id = %s;
            """,
            (
                email_id,
                person_title,
                interaction_type,
                requires_follow_up,
                event_id
            )
        )
        print("Updating linkedin event")

        return event_id

    # ➕ INSERT new event
    cur.execute(
        """
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
    """,
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