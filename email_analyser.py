import json
import re

from LLM_Groq import call_llm, LLMQuotaExhausted
from prompts import FINAL_ANALYSIS_PROMPT


def extract_json(text: str) -> dict:
    if not text:
        raise ValueError("Empty LLM response")

    text = text.strip()

    # Remove ```json fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    first = text.find("{")
    last = text.rfind("}")

    if first == -1 or last == -1:
        raise ValueError("No JSON object found")

    return json.loads(text[first:last + 1])


ALLOWED_EMAIL_TYPES = {"JOB_PIPELINE", "LINKEDIN_NETWORKING", "IGNORE"}
ALLOWED_PIPELINE_STAGES = {
    "OPPORTUNITY_FOUND",
    "APPLIED",
    "SHORTLISTED",
    "ASSESSMENT",
    "INTERVIEW",
    "SELECTED",
    "REJECTED",
}


def validate_payload(payload: dict) -> tuple[bool, str]:
    if payload.get("email_type") not in ALLOWED_EMAIL_TYPES:
        return False, "Invalid email_type"

    if not isinstance(payload.get("sender"), str):
        return False, "Invalid sender"

    if not isinstance(payload.get("subject"), str):
        return False, "Invalid subject"

    if payload["email_type"] == "JOB_PIPELINE":
        opps = payload.get("opportunities")

        if not isinstance(opps, list) or not opps:
            return False, "Opportunities must be a non-empty list"

        for opp in opps:
            if not isinstance(opp.get("company"), str):
                return False, "Invalid company"

            if opp.get("role") is not None and not isinstance(opp.get("role"), str):
                return False, "Invalid role"

            if opp.get("pipeline_stage") not in ALLOWED_PIPELINE_STAGES:
                return False, "Invalid pipeline_stage"

    return True, "OK"


def analyze_email(clean_email_text: str) -> dict:
    prompt = FINAL_ANALYSIS_PROMPT + "\n\nEMAIL CONTENT:\n" + clean_email_text

    try:
        raw_response = call_llm(prompt)
    except LLMQuotaExhausted as e:
        return {
            "email_type": "LLM_QUOTA_EXHAUSTED",
            "error": str(e),
        }
    except Exception as e:
        return {
            "email_type": "ERROR",
            "error": f"LLM call failed: {e}",
        }

    # 1️⃣ Extract JSON
    try:
        payload = extract_json(raw_response)
    except Exception as e:
        return {
            "email_type": "ERROR",
            "error": f"JSON extraction failed: {e}",
            "raw_response": raw_response,
        }

    # 2️⃣ Validate
    is_valid, reason = validate_payload(payload)
    if not is_valid:
        return {
            "email_type": "ERROR",
            "error": f"Payload validation failed: {reason}",
            "raw_response": raw_response,
        }

    return payload
