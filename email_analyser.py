import json
import re
from gemini_client import GeminiPool, QuotaExhausted
from prompts import FINAL_ANALYSIS_PROMPT


llm_pool = GeminiPool()


def extract_json(text: str) -> dict:
    if not text:
        raise ValueError("Empty response")

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace == -1 or last_brace == -1:
        raise ValueError("No JSON object found")

    json_text = text[first_brace:last_brace + 1]
    return json.loads(json_text)


ALLOWED_EMAIL_TYPES = {"JOB_PIPELINE", "LINKEDIN_NETWORKING", "IGNORE"}
ALLOWED_PIPELINE_STAGES = {
    "OPPORTUNITY_FOUND",
    "APPLIED",
    "SHORTLISTED",
    "ASSESSMENT",
    "INTERVIEW",
    "SELECTED",
    "REJECTED"
}


def validate_payload(payload: dict) -> tuple[bool, str]:
    if payload.get("email_type") not in ALLOWED_EMAIL_TYPES:
        return False, "Invalid email_type"

    if not isinstance(payload.get("sender"), str):
        return False, "Invalid sender"

    if not isinstance(payload.get("subject"), str):
        return False, "Invalid subject"

    if payload["email_type"] == "JOB_PIPELINE":
        opportunities = payload.get("opportunities")

        if not isinstance(opportunities, list) or not opportunities:
            return False, "Opportunities must be a non-empty list"

        for opp in opportunities:
            if not isinstance(opp.get("company"), str):
                return False, "Invalid company"

            if not isinstance(opp.get("role"), str):
                return False, "Invalid role"

            if opp.get("pipeline_stage") not in ALLOWED_PIPELINE_STAGES:
                return False, "Invalid pipeline_stage"

            salary = opp.get("salary_amount")
            period = opp.get("salary_period")

            if salary is not None and not isinstance(salary, (int, float)):
                return False, "Invalid salary_amount"

    return True, "OK"


def analyze_email(clean_email_text: str) -> dict:
    prompt = FINAL_ANALYSIS_PROMPT + "\n\nEMAIL CONTENT:\n" + clean_email_text

    try:
        raw_response = llm_pool.call(prompt)

    except QuotaExhausted as e:
        # 🔴 SIGNAL TO PIPELINE TO STOP
        return {
            "email_type": "LLM_QUOTA_EXHAUSTED",
            "error": str(e)
        }

    # ---------------------------
    # STEP 1: Extract JSON
    # ---------------------------
    try:
        payload = extract_json(raw_response)
    except Exception as e:
        return {
            "email_type": "ERROR",
            "error": f"JSON extraction failed: {str(e)}",
            "raw_response": raw_response
        }

    # ---------------------------
    # STEP 2: Validate
    # ---------------------------
    is_valid, reason = validate_payload(payload)

    if not is_valid:
        return {
            "email_type": "ERROR",
            "error": f"Payload validation failed: {reason}",
            "raw_response": raw_response
        }

    return payload
