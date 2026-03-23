from error_handling import LLMValidationError

# =========================================================
# CONSTANTS
# =========================================================

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
    "RECRUITER_MESSAGE",
    "MESSAGE_RECEIVED",
    "CONNECTION_REQUEST"
}

VALID_SALARY_PERIOD = {"year", "month", "hour"}


# =========================================================
# FIELD DEFINITIONS
# =========================================================

JOB_PAYLOAD_FIELDS = ["email_type", "sender", "subject", "opportunities"]

OPPORTUNITY_FIELDS = [
    "company",
    "role",
    "location",
    "salary_amount",
    "salary_period",
    "min_experience_years",
    "max_experience_years",
    "pipeline_stage",
    "action_required",
    "deadline",
    "event_date",
    "other_important_details"
]

LINKEDIN_PAYLOAD_FIELDS = ["email_type", "sender", "subject", "events"]

LINKEDIN_EVENT_FIELDS = [
    "person_name",
    "person_title",
    "person_company",
    "interaction_type",
    "requires_follow_up"
]


# =========================================================
# NORMALIZE
# =========================================================

def normalize_output(data):
    if isinstance(data, dict):
        return [data]
    return data


# =========================================================
# TYPE CHECK HELPERS
# =========================================================

def is_number(x):
    return isinstance(x, (int, float))


def is_int(x):
    return isinstance(x, int)


def is_bool(x):
    return isinstance(x, bool)


def is_str(x):
    return isinstance(x, str)


# =========================================================
# MAIN VALIDATION
# =========================================================

def validate_schema(data):

    data = normalize_output(data)

    if not isinstance(data, list):
        raise LLMValidationError("Output must be list or dict")

    for item in data:

        if not isinstance(item, dict):
            raise LLMValidationError("Each item must be object")

        payload = item.get("payload", item)

        email_type = payload.get("email_type")

        if not email_type:
            raise LLMValidationError("Missing email_type")

        # =========================================================
        # IGNORE → PASS
        # =========================================================
        if email_type == "IGNORE":
            return True

        # =========================================================
        # JOB PIPELINE
        # =========================================================
        elif email_type == "JOB_PIPELINE":

            # -------------------------
            # FIELD EXISTENCE
            # -------------------------
            for field in JOB_PAYLOAD_FIELDS:
                if field not in payload:
                    raise LLMValidationError(f"Missing field: {field}")

            opportunities = payload["opportunities"]

            if not isinstance(opportunities, list):
                raise LLMValidationError("opportunities must be list")

            for opp in opportunities:

                if not isinstance(opp, dict):
                    raise LLMValidationError("Invalid opportunity object")

                # -------------------------
                # FIELD EXISTENCE
                # -------------------------
                for field in OPPORTUNITY_FIELDS:
                    if field not in opp:
                        raise LLMValidationError(f"Missing field: {field}")

                # -------------------------
                # TYPE CHECKS
                # -------------------------
                if opp["company"] is not None and not is_str(opp["company"]):
                    raise LLMValidationError("company must be string")

                if opp["role"] is not None and not is_str(opp["role"]):
                    raise LLMValidationError("role must be string")

                if opp["location"] is not None and not is_str(opp["location"]):
                    raise LLMValidationError("location must be string")

                if opp["salary_amount"] is not None and not is_number(opp["salary_amount"]):
                    raise LLMValidationError("salary_amount must be numeric")

                if opp["salary_period"] is not None:
                    if not is_str(opp["salary_period"]) or opp["salary_period"] not in VALID_SALARY_PERIOD:
                        raise LLMValidationError("Invalid salary_period")

                if opp["min_experience_years"] is not None and not is_int(opp["min_experience_years"]):
                    raise LLMValidationError("min_experience_years must be int")

                if opp["max_experience_years"] is not None and not is_int(opp["max_experience_years"]):
                    raise LLMValidationError("max_experience_years must be int")

                if opp["action_required"] is not None and not is_bool(opp["action_required"]):
                    raise LLMValidationError("action_required must be boolean")

                if opp["deadline"] is not None and not is_str(opp["deadline"]):
                    raise LLMValidationError("deadline must be string (YYYY-MM-DD)")

                if opp["event_date"] is not None and not is_str(opp["event_date"]):
                    raise LLMValidationError("event_date must be string timestamp")

                # -------------------------
                # ENUM VALIDATION
                # -------------------------
                if opp["pipeline_stage"] is not None:
                    if not is_str(opp["pipeline_stage"]) or opp["pipeline_stage"] not in VALID_PIPELINE_STAGES:
                        raise LLMValidationError("Invalid pipeline_stage")

        # =========================================================
        # LINKEDIN NETWORKING
        # =========================================================
        elif email_type == "LINKEDIN_NETWORKING":

            for field in LINKEDIN_PAYLOAD_FIELDS:
                if field not in payload:
                    raise LLMValidationError(f"Missing field: {field}")

            events = payload["events"]

            if not isinstance(events, list):
                raise LLMValidationError("events must be list")

            for ev in events:

                if not isinstance(ev, dict):
                    raise LLMValidationError("Invalid event object")

                # -------------------------
                # FIELD EXISTENCE
                # -------------------------
                for field in LINKEDIN_EVENT_FIELDS:
                    if field not in ev:
                        raise LLMValidationError(f"Missing field: {field}")

                # -------------------------
                # TYPE CHECKS
                # -------------------------
                if ev["person_name"] is not None and not is_str(ev["person_name"]):
                    raise LLMValidationError("person_name must be string")

                if ev["person_title"] is not None and not is_str(ev["person_title"]):
                    raise LLMValidationError("person_title must be string")

                if ev["person_company"] is not None and not is_str(ev["person_company"]):
                    raise LLMValidationError("person_company must be string")

                if ev["requires_follow_up"] is not None and not is_bool(ev["requires_follow_up"]):
                    raise LLMValidationError("requires_follow_up must be boolean")

                # -------------------------
                # ENUM VALIDATION
                # -------------------------
                if ev["interaction_type"] is not None:
                    if not is_str(ev["interaction_type"]) or ev["interaction_type"] not in VALID_INTERACTIONS:
                        raise LLMValidationError("Invalid interaction_type")

        # =========================================================
        # UNKNOWN TYPE
        # =========================================================
        else:
            raise LLMValidationError(f"Unknown email_type: {email_type}")

    return True