import json
import re
from email_analyser.llm_gemini import call_llm, LLMQuotaExhausted
from email_analyser.prompts import FINAL_ANALYSIS_PROMPT
from dotenv import load_dotenv
import os

load_dotenv()
EMAIL_EXTRACTION_MODEL=os.getenv("MODEL_EMAIL_EXTRACTION")
def extract_json(text: str):
    if not text:
        raise ValueError("Empty LLM response")

    text = text.strip()

    # Remove markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    # Direct JSON parse
    return json.loads(text)


def analyze_email_batch(gemini_input: str) -> dict:
    prompt = FINAL_ANALYSIS_PROMPT + "\n\nEMAILS:\n" + json.dumps(gemini_input, indent=2)

    try:
        raw_response = call_llm(prompt,EMAIL_EXTRACTION_MODEL,0)

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
            "raw_response": raw_response
        }
