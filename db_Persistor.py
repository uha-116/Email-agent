# db_Persistor.py

from datetime import datetime
from db_Connection import get_db_connection
from db_Repository import (
    insert_email,
    insert_or_update_opportunity,
    insert_opportunity_details,
    insert_linkedin_event
)


def email_already_processed(cur, gmail_message_id: str) -> bool:
    """
    Checks if an email with this Gmail message ID
    has already been processed.
    """
    cur.execute(
        "SELECT 1 FROM emails WHERE gmail_message_id = %s;",
        (gmail_message_id,)
    )
    return cur.fetchone() is not None


def persist_email_payload(
    payload: dict,
    gmail_message_id: str,
    received_at: datetime,
    raw_body_text: str
) -> dict:
    """
    Persists a parsed email payload into the database.

    RULES:
    - ALL emails are stored in emails table (including IGNORE)
    - JOB_PIPELINE → opportunities + details
    - LINKEDIN_NETWORKING → linkedin_events
    - IGNORE → emails table ONLY
    """

    result = {
        "email_id": None,
        "opportunity_ids": [],
        "linkedin_event_id": None
    }

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # --------------------------------------------------
        # 1️⃣ ALWAYS INSERT EMAIL (INCLUDING IGNORE)
        # --------------------------------------------------
        email_id = insert_email(
            cur=cur,
            gmail_message_id=gmail_message_id,
            sender=payload.get("sender"),
            subject=payload.get("subject"),
            email_type=payload.get("email_type"),
            received_at=received_at,
            raw_body_text=raw_body_text
        )

        result["email_id"] = email_id
        email_type = payload.get("email_type")

        # --------------------------------------------------
        # 2️⃣ IGNORE → STOP AFTER EMAIL INSERT
        # --------------------------------------------------
        if email_type == "IGNORE":
            conn.commit()
            return result

        # --------------------------------------------------
        # 3️⃣ JOB PIPELINE
        # --------------------------------------------------
        if email_type == "JOB_PIPELINE":
            for opp in payload.get("opportunities", []):

                opportunity_id = insert_or_update_opportunity(
                    cur=cur,
                    email_id=email_id,
                    company=opp.get("company"),
                    role=opp.get("role"),
                    location=opp.get("location"),
                    salary_amount=opp.get("salary_amount"),
                    salary_period=opp.get("salary_period"),
                    min_experience_years=opp.get("min_experience_years"),
                    max_experience_years=opp.get("max_experience_years"),
                    pipeline_stage=opp.get("pipeline_stage"),
                    action_required=opp.get("action_required", False),
                    deadline=opp.get("deadline"),
                    event_date=opp.get("event_date")
                )

                if opportunity_id:
                    result["opportunity_ids"].append(opportunity_id)

                    insert_opportunity_details(
                        cur=cur,
                        opportunity_id=opportunity_id,
                        other_important_details=opp.get(
                            "other_important_details", {}
                        )
                    )

        # --------------------------------------------------
        # 4️⃣ LINKEDIN NETWORKING
        # --------------------------------------------------
        elif email_type == "LINKEDIN_NETWORKING":
            linkedin = payload.get("linkedin_event")
            if linkedin:
                linkedin_event_id = insert_linkedin_event(
                    cur=cur,
                    email_id=email_id,
                    person_name=linkedin.get("person_name"),
                    person_title=linkedin.get("person_title"),
                    person_company=linkedin.get("person_company"),
                    interaction_type=linkedin.get("interaction_type"),
                    requires_follow_up=linkedin.get(
                        "requires_follow_up", False
                    )
                )
                result["linkedin_event_id"] = linkedin_event_id

        conn.commit()
        return result

    except Exception as e:
        conn.rollback()
        raise e

    finally:
        cur.close()
        conn.close()
