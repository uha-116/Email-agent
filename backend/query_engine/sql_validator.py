import json
import os
from dotenv import load_dotenv

from backend.email_analyser.llm_gemini import call_llm
from backend.email_analyser.prompts import SQL_VALIDATION_PROMPT
from backend.error_handling import BaseAppError, LLMOutputFormatError


load_dotenv()

SQL_VALIDATION_MODEL = os.getenv("SQL_VALIDATION_MODEL")


# ---------------------------------------------------------
# Validate generated SQL using LLM
# ---------------------------------------------------------

def validate_sql(user_question: str, count_sql: str, list_sql: str):

    try:
        # choose which SQL to validate
        sql = list_sql if list_sql else count_sql

        prompt = (
            SQL_VALIDATION_PROMPT
            + "\n\nUSER QUESTION:\n"
            + user_question
            + "\n\nSQL QUERY:\n"
            + sql
        )

        raw_response = call_llm(prompt, SQL_VALIDATION_MODEL, 200, 0)

        return json.loads(raw_response)

    except BaseAppError:
        # 🔥 already structured (LLM errors)
        raise

    except json.JSONDecodeError as e:
        # 🔥 invalid LLM output
        raise LLMOutputFormatError(f"Invalid JSON from SQL validation LLM: {e}")

    except Exception as e:
        # 🔥 unknown issues
        raise LLMOutputFormatError(f"SQL validation failed: {e}")