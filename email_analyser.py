import json
import re
from LLM_Gemini import call_llm, LLMQuotaExhausted
from prompts import FINAL_ANALYSIS_PROMPT


def extract_json(text: str) -> dict:
    if not text:
        raise ValueError("Empty LLM response")

    text = text.strip()

    # Remove markdown fences if any
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    first = text.find("{")
    last = text.rfind("}")

    if first == -1 or last == -1:
        raise ValueError("No JSON object found")

    return json.loads(text[first:last + 1])


def analyze_email(clean_email_text: str) -> dict:
    prompt = FINAL_ANALYSIS_PROMPT + "\n\nEMAIL CONTENT:\n" + clean_email_text

    try:
        raw_response = call_llm(prompt)

    except LLMQuotaExhausted as e:
        return {
            "email_type": "LLM_QUOTA_EXHAUSTED",
            "error": str(e)
        }

    except Exception as e:
        return {
            "email_type": "ERROR",
            "error": str(e)
        }

    try:
        payload = extract_json(raw_response)
        return payload

    except Exception as e:
        return {
            "email_type": "ERROR",
            "error": f"JSON extraction failed: {e}",
            "raw_response": raw_response[:500]
        }
