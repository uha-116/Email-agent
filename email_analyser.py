import json
import re
from gemini_client import call_gemini
from prompts import FINAL_ANALYSIS_PROMPT


def extract_json(text: str) -> dict:
    """
    Extracts valid JSON from LLM output.
    Handles ```json ... ``` and plain JSON.
    """
    if not text:
        raise ValueError("Empty response")

    # Remove markdown code fences if present
    text = text.strip()

    # Case 1: ```json ... ```
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    # Case 2: extra text before/after JSON
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
    "ASSESSMENT",
    "INTERVIEW",
    "SELECTED",
    "REJECTED"
}


def validate_payload(payload: dict) -> tuple[bool, str]:
    # -------- Top-level --------
    if payload.get("email_type") not in ALLOWED_EMAIL_TYPES:
        return False, "Invalid email_type"

    if not isinstance(payload.get("sender"), str):
        return False, "Invalid sender"

    if not isinstance(payload.get("subject"), str):
        return False, "Invalid subject"

    # -------- JOB PIPELINE --------
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

            if salary is not None:
                if not isinstance(salary, (int, float)):
                    return False, "Invalid salary_amount"

                if period == "year" and salary < 10000:
                    # downgrade, do NOT reject
                    opp["other_important_details"]["invalid_salary"] = salary
                    opp["salary_amount"] = None

    return True, "OK"



def analyze_email(clean_email_text: str) -> dict:
    prompt = FINAL_ANALYSIS_PROMPT + "\n\nEMAIL CONTENT:\n" + clean_email_text
    raw_response = call_gemini(prompt)

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
    # STEP 2: Validate + Normalize
    # ---------------------------
    is_valid, reason = validate_payload(payload)

    if not is_valid:
        return {
            "email_type": "ERROR",
            "error": f"Payload validation failed: {reason}",
            "raw_response": raw_response
        }

    # ---------------------------
    # STEP 3: SAFE payload
    # ---------------------------
    return payload


text = """ 
--- IMAGE OCR TEXT ---

#CareerKiAzadi

frezdow feat

Opportunities with CTC upto 2OLPA
& Prize pool upto 3Cr+ ~

Bonus: Apply to any 5 opportunities & win
prizes upto INR 50,000

COMPANY

From: Team Unstop <noreply@dare2compete.news>
Subject: This Republic Day, win INR 50K Giveaway
Date: Sun, 25 Jan 2026 12:24:50 +0000

--- EMAIL BODY ---

Freedom Fest | Career Ki Azadi
Claim Now!
Hi Burjukindi 🇮🇳
This Republic Day, celebrate
#CareerKiAzadi
with
Freedom Fest by Unstop
.
Explore
jobs up to INR 12 LPA
, paid internships, and live competitions with a
I
NR 3 Cr+ prize pool.
Republic Day Bonus 🎁
Apply to any 5 opportunities and unlock surprise giveaways worth ₹50,000 for 50 lucky winners.
Explore Freedom Fest
How to participate:
Step 1:
Apply to any 5 opportunities & unlock giveaways worth 50000 (50 lucky winners)
Step 2:
Post about Unstop Freedom Fest on your social media along with the fest link.
We will select
50 lucky winners
based on participation and announce the results on our social media platforms.
Freedom to choose your career. Only on Unstop.
Regards
This email was sent to uharikajob@gmail.com because you subscribed to updates from Unstop.
To stop receiving these emails,
unsubscribe here
.

"""

store=analyze_email(text)
print(store)