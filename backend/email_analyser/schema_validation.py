from datetime import datetime
from backend.error_handling import LLMValidationError, retry

VALID_PIPELINE_STAGES = {
    "OPPORTUNITY_FOUND",
    "APPLIED",
    "ASSESSMENT",
    "INTERVIEW",
    "SELECTED",
    "SHORTLISTED",
    "REJECTED"
}

VALID_INTERACTIONS = {
    "CONNECTION_ACCEPTED",
    "MESSAGE_RECEIVED",
    "CONNECTION_REQUEST"  # 🔥 added (your sample uses this)
}

VALID_SALARY_PERIOD = {"year", "month", "hour"}


def normalize_output(data):
    return [data] if isinstance(data, dict) else data


def is_number(x): return isinstance(x, (int, float))
def is_int(x): return isinstance(x, int)
def is_bool(x): return isinstance(x, bool)
def is_str(x): return isinstance(x, str)


def validate_date(date_str):
    datetime.strptime(date_str, "%Y-%m-%d")


def validate_datetime(dt_str):
    datetime.fromisoformat(dt_str)


# =========================================================
# SINGLE ITEM VALIDATION
# =========================================================

def validate_single_item(item):

    if not isinstance(item, dict):
        raise LLMValidationError("Item must be object")

    payload = item.get("payload", item)

    if not isinstance(payload, dict):
        raise LLMValidationError("payload must be object")

    email_type = payload.get("email_type")

    if not email_type:
        raise LLMValidationError("Missing email_type")

    # =====================================================
    # IGNORE
    # =====================================================
    if email_type == "IGNORE":
        return True

    # =====================================================
    # JOB PIPELINE
    # =====================================================
    if email_type == "JOB_PIPELINE":

        if "opportunities" not in payload:
            raise LLMValidationError("Missing opportunities")

        opportunities = payload["opportunities"]

        if not isinstance(opportunities, list) or not opportunities:
            raise LLMValidationError("opportunities must be non-empty list")

        for opp in opportunities:

            if not isinstance(opp, dict):
                raise LLMValidationError("Each opportunity must be object")

            # -------------------------
            # REQUIRED FIELDS
            # -------------------------
            company = opp.get("company")
            pipeline_stage = opp.get("pipeline_stage")

            if not company or not is_str(company) or not company.strip():
                raise LLMValidationError("company must be non-empty string")

            if not pipeline_stage or pipeline_stage not in VALID_PIPELINE_STAGES:
                raise LLMValidationError("Invalid or missing pipeline_stage")

            # -------------------------
            # OPTIONAL STRING FIELDS
            # -------------------------
            for field in ["role", "location"]:
                if opp.get(field) is not None and not is_str(opp[field]):
                    raise LLMValidationError(f"{field} must be string")

            # -------------------------
            # SALARY LOGIC
            # -------------------------
            salary_amount = opp.get("salary_amount")
            salary_period = opp.get("salary_period")

            if salary_amount is not None and not is_number(salary_amount):
                raise LLMValidationError("salary_amount must be numeric")

            if salary_period is not None:
                if not is_str(salary_period) or salary_period not in VALID_SALARY_PERIOD:
                    raise LLMValidationError("Invalid salary_period")

            if (salary_amount is None) != (salary_period is None):
                raise LLMValidationError("salary_amount and salary_period must both exist or both be null")

            # -------------------------
            # EXPERIENCE
            # -------------------------
            min_exp = opp.get("min_experience_years")
            max_exp = opp.get("max_experience_years")

            if min_exp is not None and not is_int(min_exp):
                raise LLMValidationError("min_experience_years must be int")

            if max_exp is not None and not is_int(max_exp):
                raise LLMValidationError("max_experience_years must be int")

            if min_exp is not None and max_exp is not None and min_exp > max_exp:
                raise LLMValidationError("min_exp > max_exp")

            # -------------------------
            # BOOLEAN
            # -------------------------
            if opp.get("action_required") is not None and not is_bool(opp["action_required"]):
                raise LLMValidationError("action_required must be boolean")

            # -------------------------
            # DATE
            # -------------------------
            if opp.get("deadline") is not None:
                if not is_str(opp["deadline"]):
                    raise LLMValidationError("deadline must be string in YYYY-MM-DD format")
                validate_date(opp["deadline"])

            if opp.get("event_date") is not None:
                if not is_str(opp["event_date"]):
                    raise LLMValidationError("event_date must be ISO datetime string")
                validate_datetime(opp["event_date"])

            # -------------------------
            # OTHER DETAILS (optional dict)
            # -------------------------
            if opp.get("other_important_details") is not None and not isinstance(opp["other_important_details"], dict):
                raise LLMValidationError("other_important_details must be object")

    # =====================================================
    # LINKEDIN
    # =====================================================
    elif email_type == "LINKEDIN_NETWORKING":

        linkedin = payload.get("linkedin_event")

        if not isinstance(linkedin, dict):
            raise LLMValidationError("linkedin_event must be object")

        # REQUIRED
        person_name = linkedin.get("person_name")
        interaction_type = linkedin.get("interaction_type")

        if not person_name or not is_str(person_name) or not person_name.strip():
            raise LLMValidationError("person_name must be non-empty string")

        if not interaction_type or interaction_type not in VALID_INTERACTIONS:
            raise LLMValidationError("Invalid interaction_type")

        # OPTIONAL
        for field in ["person_title", "person_company"]:
            if linkedin.get(field) is not None and not is_str(linkedin[field]):
                raise LLMValidationError(f"{field} must be string")

        if linkedin.get("requires_follow_up") is not None and not is_bool(linkedin["requires_follow_up"]):
            raise LLMValidationError("requires_follow_up must be boolean")

    else:
        raise LLMValidationError("Unknown email_type")

    return True


# =========================================================
# BATCH VALIDATION
# =========================================================

@retry(max_attempts=2)
def validate_schema(data):

    data = normalize_output(data)

    if not isinstance(data, list):
        raise LLMValidationError("Output must be list")

    valid_items = []
    invalid_items = []

    for item in data:
        try:
            validate_single_item(item)
            valid_items.append(item)

        except LLMValidationError as e:
            invalid_items.append({
                "item": item,
                "error": str(e)
            })
    
    if not valid_items and invalid_items:
    # 🔥 all items failed → treat as full validation failure
        raise LLMValidationError("All items failed validation")

    return valid_items, invalid_items