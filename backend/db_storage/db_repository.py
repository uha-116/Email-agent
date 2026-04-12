# db_repository.py

import json
from datetime import date, datetime
from difflib import SequenceMatcher



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

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_intern(role: str | None) -> bool:
    if not role:
        return False
    return "intern" in role.lower()


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

    # --------------------------------------------------
    # 🔹 STEP 1: FETCH ALL COMPANY RECORDS
    # --------------------------------------------------
    cur.execute(
        """
        SELECT id, role, pipeline_stage, last_updated_at
        FROM opportunities
        WHERE LOWER(company) = LOWER(%s)
        """,
        (company,)
    )

    rows = cur.fetchall()

    # --------------------------------------------------
    # 🔹 STEP 2: NO RECORDS → INSERT
    # --------------------------------------------------
    if not rows:
        return "INSERT", None

    # Convert to structured list
    candidates = []
    for r in rows:
        candidates.append({
            "id": r[0],
            "role": r[1],
            "stage": r[2],
            "last_updated_at": r[3]
        })

    new_stage_priority = get_stage_priority(new_stage)

    # --------------------------------------------------
    # 🔹 STEP 3: ONLY ONE RECORD
    # --------------------------------------------------
    if len(candidates) == 1:
        record = candidates[0]

        if role and record["role"]:
            sim = similarity(role, record["role"])

            if sim >= 0.6 and is_intern(role) == is_intern(record["role"]):
                return "UPDATE", record["id"]
            else:
                return "INSERT", None

        return "UPDATE", record["id"]

    # --------------------------------------------------
    # 🔹 STEP 4: ROLE-BASED MATCHING
    # --------------------------------------------------
    role_matches = []

    if role:
        for rec in candidates:
            if not rec["role"]:
                continue

            sim = similarity(role, rec["role"])

            # 🔴 Strong mismatch → skip
            if sim < 0.5:
                continue

            # 🔴 Intern mismatch → skip
            if is_intern(role) != is_intern(rec["role"]):
                continue

            existing_stage_priority = get_stage_priority(rec["stage"])

            # 🔴 Prevent downgrade
            if existing_stage_priority > new_stage_priority:
                continue

            stage_diff = abs(new_stage_priority - existing_stage_priority)

            role_matches.append({
                "id": rec["id"],
                "similarity": sim,
                "stage_diff": stage_diff,
                "last_updated_at": rec["last_updated_at"]
            })

    # --------------------------------------------------
    # 🔹 STEP 5: IF ROLE MATCHES FOUND
    # --------------------------------------------------
    if role_matches:
        role_matches.sort(
            key=lambda x: (
                -x["similarity"],             # highest similarity first
                x["stage_diff"],              # closest stage
                -x["last_updated_at"].timestamp() 
            )
        )

        return "UPDATE", role_matches[0]["id"]

    # --------------------------------------------------
    # 🔹 STEP 6: STAGE FALLBACK
    # --------------------------------------------------
    stage_matches = []

    for rec in candidates:
        existing_stage_priority = get_stage_priority(rec["stage"])

        # Only lower or equal stages
        if existing_stage_priority > new_stage_priority:
            continue

        stage_diff = abs(new_stage_priority - existing_stage_priority)

        stage_matches.append({
            "id": rec["id"],
            "stage_diff": stage_diff,
            "last_updated_at": rec["last_updated_at"]
        })

    if stage_matches:
        stage_matches.sort(
            key=lambda x: (
                x["stage_diff"],
                -x["last_updated_at"].timestamp() if x["last_updated_at"] else 0
            )
        )

        return "UPDATE", stage_matches[0]["id"]

    # --------------------------------------------------
    # 🔹 STEP 7: FINAL FALLBACK → INSERT
    # --------------------------------------------------
    return "INSERT", None


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

                email_id = %s,

                -- 🔒 ROLE (only if NULL)
                role = COALESCE(role, %s),

                -- 📍 LOCATION
                location =
                    CASE
                        WHEN %s IS NOT NULL THEN %s
                        ELSE location
                    END,

                -- 💰 SALARY
                salary_amount =
                    CASE
                        WHEN %s IS NOT NULL THEN %s
                        ELSE salary_amount
                    END,

                salary_period =
                    CASE
                        WHEN %s IS NOT NULL THEN %s
                        ELSE salary_period
                    END,

                -- 📊 EXPERIENCE
                min_experience_years =
                    CASE
                        WHEN %s IS NOT NULL THEN %s
                        ELSE min_experience_years
                    END,

                max_experience_years =
                    CASE
                        WHEN %s IS NOT NULL THEN %s
                        ELSE max_experience_years
                    END,

                -- 🚀 PIPELINE
                pipeline_stage = %s,

                -- 🔥 FIXED lifecycle
                action_required = %s,

                -- 🔥 IMPORTANT: ALWAYS OVERWRITE
                deadline = %s,
                event_date = %s,

                -- 🕒 LAST UPDATED
                last_updated_at = %s,
                response_locked = FALSE


            WHERE id = %s;
            """,
            (
                 email_id, 
                 
                # role
                role,

                # location
                location, location,

                # salary
                salary_amount, salary_amount,
                salary_period, salary_period,

                # experience
                min_experience_years, min_experience_years,
                max_experience_years, max_experience_years,

                # pipeline
                pipeline_stage,

                # action_required
                action_required,

                # 🔥 ALWAYS overwrite
                deadline,
                event_date,

                # last updated
                received_at,

                # id
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