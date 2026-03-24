import json
import re
import os
from dotenv import load_dotenv

from email_analyser.llm_gemini import call_llm
from email_analyser.prompts import FINAL_ANALYSIS_PROMPT

from error_handling import (
    retry,
    LLMOutputFormatError,
    LLMValidationError
)

from email_analyser.schema_validation import validate_schema

# --------------------------------------------------
# LOAD ENV
# --------------------------------------------------
load_dotenv()
EMAIL_EXTRACTION_MODEL = os.getenv("EMAIL_EXTRACTION_MODEL")


# =========================================================
# JSON EXTRACTION
# =========================================================

def extract_json(text: str):

    if not text:
        raise LLMOutputFormatError("Empty LLM response")

    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    array_match = re.search(r"\[\s*{.*}\s*\]", text, re.DOTALL)
    if array_match:
        json_text = array_match.group(0)
        try:
            return json.loads(json_text)
        except Exception:
            raise LLMOutputFormatError("Invalid JSON array structure")

    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        json_text = obj_match.group(0)
        try:
            return json.loads(json_text)
        except Exception:
            raise LLMOutputFormatError("Invalid JSON object structure")

    raise LLMOutputFormatError("No valid JSON found in LLM output")


# =========================================================
# MAIN ANALYSIS (WITH RETRY + VALIDATION)
# =========================================================

@retry(max_attempts=2)
def analyze_email_batch(gemini_input: list) -> list:

    # --------------------------------------------------
    # STEP 1: BUILD PROMPT
    # --------------------------------------------------
    prompt = (
        FINAL_ANALYSIS_PROMPT
        + "\n\nEMAILS:\n"
        + json.dumps(gemini_input, indent=2)
    )

    # --------------------------------------------------
    # STEP 2: CALL LLM
    # --------------------------------------------------
    raw_response = call_llm(prompt, EMAIL_EXTRACTION_MODEL, 0)

    # --------------------------------------------------
    # STEP 3: JSON EXTRACTION
    # --------------------------------------------------
    payload = extract_json(raw_response)

    # --------------------------------------------------
    # STEP 4: SCHEMA VALIDATION (PARTIAL SAFE)
    # --------------------------------------------------
    try:
        valid_items, invalid_items = validate_schema(payload)
        print("Valid_items",valid_items)
        print("Invalid items",invalid_items)

    except LLMValidationError as e:
        # This means FULL STRUCTURE is broken (not per-item)
        raise LLMValidationError(f"Batch validation failed: {e}")

    # --------------------------------------------------
    # STEP 5: LOG INVALID ITEMS
    # --------------------------------------------------
    for bad in invalid_items:
        item = bad.get("item", {})
        idx = item.get("index", "unknown")

        print(f"⚠️ Skipping LLM output at index {idx} → {bad['error']}")

    # --------------------------------------------------
    # STEP 6: RETURN ONLY VALID ITEMS
    # --------------------------------------------------
    if not valid_items:
        raise LLMValidationError("All items failed validation")

    return valid_items