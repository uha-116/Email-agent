import json
import os
from dotenv import load_dotenv

from backend.query_engine.intent_to_sql import resolve_user_question
from backend.query_engine.sql_validator import validate_sql
from backend.query_engine.query_runner import execute_query

from backend.email_analyser.llm_gemini import call_llm
from backend.email_analyser.prompts import (
    SQL_EXPLANATION_PROMPT,
    SQL_GENERATION_PROMPT
)

from backend.error_handling import BaseAppError


# ---------------------------------------------------------
# ENV
# ---------------------------------------------------------
load_dotenv()

MODEL_EXPLAIN = os.getenv("EXPLANATION_MODEL")
MODEL_SQL = os.getenv("SQL_GENERATION_MODEL")


# =========================================================
# 🚀 MAIN ORCHESTRATOR
# =========================================================

def handle_query_stream(question: str):

    print("\n" + "="*80)
    print("🧠 USER QUESTION:")
    print(question)
    print("="*80)

    try:

        # =================================================
        # STEP 1: INTENT → SQL
        # =================================================
        yield "Analyzing your question"

        result = resolve_user_question(question)
        score = result.get("similarity", 0.0)

        print(f"SBERT Score: {score}")

        if score < 0.4:
            yield ("FINAL", "Hi! I'm Job Application Tracking Assistant. I can only help you with job-related queries.")
            return


        # =================================================
        # ROUTING
        # =================================================
        if "route" in result:
            yield from _handle_llm_fallback(question)
            return

        # =================================================
        # SQL BUILD
        # =================================================
        yield "Building query"

        count_sql = result.get("count_sql")
        list_sql = result.get("list_sql")

        print("\n🧾 Generated SQL:")
        if count_sql:
            print("COUNT SQL:\n", count_sql)
        if list_sql:
            print("LIST SQL:\n", list_sql)

        # =================================================
        # VALIDATION
        # =================================================
        yield "Validating Query"

        validation = validate_sql(question, count_sql, list_sql)

        if validation["decision"] != "YES":
            print("⚠️ Validation failed → Routing to LLM fallback")
            yield from _handle_llm_fallback(question)
            return

        # =================================================
        # EXECUTION
        # =================================================
        yield "Fetching Results"

        count_result = None
        list_result = None

        if count_sql:
            count_result = execute_query(count_sql)

        if list_sql:
            list_result = execute_query(list_sql)

        # =================================================
        # EXPLANATION
        # =================================================
        yield "Preparing insights"

        records = {
            "count": count_result,
            "records": list_result
        }

        explanation = _generate_explanation(
            question,
            count_sql,
            list_sql,
            records
        )

        # =================================================
        # FINAL OUTPUT
        # =================================================
        yield ("FINAL", explanation)

    except BaseAppError as e:
        yield ("FINAL", e.user_message)

    except GeneratorExit:
        print("⚠️ Stream closed by client")
        return

    except Exception as e:
        yield ("FINAL", "Something went wrong while processing your request.")
        

# =========================================================
# 🔥 LLM SQL FALLBACK HANDLER (NEW)
# =========================================================

def _handle_llm_fallback(question):

    yield "Generating query using AI"

    response = _generate_llm_sql(question)

    try:
        parsed = json.loads(response)

        if parsed.get("decision") == "NO":
            yield ("FINAL", parsed.get("reason", "Sorry Uharika! This request is outside system capabilities."))
            return

        sql = parsed.get("sql")



    except:
        sql = response

    yield "Fetching Results"

    result_data = execute_query(sql)

    yield "Preparing insights"

    explanation = _generate_explanation(
        question,
        None,
        sql,
        result_data
    )

    yield ("FINAL", explanation)

# =========================================================
# 🔥 LLM SQL GENERATION
# =========================================================

def _generate_llm_sql(question):

    print("\n🧠 FALLBACK: LLM SQL GENERATION")

    prompt = SQL_GENERATION_PROMPT + "\n\nUSER QUESTION:\n" + question

    sql = call_llm(prompt, MODEL_SQL, 1000, 0)

    print("\nGenerated SQL (LLM):\n", sql)

    return sql.strip()


# =========================================================
# 🤖 EXPLANATION
# =========================================================

def _generate_explanation(question, count_sql, list_sql, records):

    sql_section = ""

    if count_sql:
        sql_section += "COUNT SQL:\n" + str(count_sql) + "\n\n"

    if list_sql:
        sql_section += "LIST SQL:\n" + str(list_sql) + "\n\n"

    prompt = (
        SQL_EXPLANATION_PROMPT
        + "\n\nUSER QUESTION:\n"
        + question
        + "\n\nSQL:\n"
        + sql_section
        + "\nDATA:\n"
        + json.dumps(records, indent=2, default=str)
    )

    try:
        return call_llm(prompt, MODEL_EXPLAIN,8000,0)

    except BaseAppError as e:
        print(f"❌ EXPLANATION ERROR: {e.user_message}")
        return e.user_message

    except Exception as e:
        print(f"❌ Unexpected explanation error: {e}")
        return "I found your results, but couldn't format them properly. Please try again."


# =========================================================
# 🧪 TEST LOOP
# =========================================================

def main():

    print("\n🚀 QUERY ENGINE STARTED\n")

    while True:
        q = input("Ask: ")

        if q.lower() in ["exit", "quit"]:
            break

        result = handle_query_stream(q)

        print("\n📦 RETURNED (for UI):\n", result)


if __name__ == "__main__":
    main()