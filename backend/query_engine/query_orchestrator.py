import json
import os
from dotenv import load_dotenv

from backend.query_engine.intent_to_sql import resolve_user_question
from backend.query_engine.sql_validator import validate_sql
from backend.query_engine.query_runner import execute_query
from backend.query_engine.entry_guard import check_entry_guard

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
MODEL_SQL = os.getenv("SQL_MODEL")


# =========================================================
# 🚀 MAIN ORCHESTRATOR
# =========================================================

def handle_query(question: str):

    print("\n" + "="*80)
    print("🧠 USER QUESTION:")
    print(question)
    print("="*80)

    try:

        # =================================================
        # STEP 1: INTENT → SQL
        # =================================================
        print("\n🔍 STEP 1: INTENT TO SQL")

        result = resolve_user_question(question)
        score = result.get("similarity", 0.0)

        print(f"SBERT Score: {score}")

        if score < 0.4:
            print("❌ Out of domain query")
            return "Hi! I'm Job Application Tracking Assitant. I can only help you with Job related queries.Please ask questions related to your job openings and application status."

        guard = check_entry_guard(question)

        if guard["block"]:
            print("⚠️ Blocked by entry guard")
            return guard["message"]


        # fallback route
        if "route" in result:
            print("⚠️ Routed to LLM SQL generation")
            print("👉 This question requires LLM-based SQL generation (currently disabled)\n")
            return "This query requires advanced processing which is currently unavailable."

        count_sql = result.get("count_sql")
        list_sql = result.get("list_sql")

        print("\n🧾 Generated SQL:")
        if count_sql:
            print("COUNT SQL:\n", count_sql)
        if list_sql:
            print("LIST SQL:\n", list_sql)

        # =================================================
        # STEP 2: VALIDATION
        # =================================================
        print("\n✅ STEP 2: VALIDATION")

        validation = validate_sql(question, count_sql, list_sql)
        print(validation)

        if validation["decision"] != "YES":
            print("⚠️ Validation failed → switching to LLM SQL")
            return "Query needs advanced processing"

        # =================================================
        # STEP 3: EXECUTION
        # =================================================
        print("\n⚡ STEP 3: EXECUTION")

        count_result = None
        list_result = None

        if count_sql:
            print("\nRunning COUNT query...")
            count_result = execute_query(count_sql)
            print("COUNT RESULT:", count_result)

        if list_sql:
            print("\nRunning LIST query...")
            list_result = execute_query(list_sql)
            print("LIST RESULT:", list_result)

        # =================================================
        # STEP 4: LLM EXPLANATION
        # =================================================
        print("\n🤖 STEP 4: LLM EXPLANATION")

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

        print("\n🎯 FINAL ANSWER:\n")
        print(explanation)

        # 🔥 ONLY RETURN FINAL EXPLANATION (UI NEED)
        return explanation

    except BaseAppError as e:
        print(f"❌ ERROR: {e.user_message}")
        return e.user_message

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return "Something went wrong while processing your request."


# =========================================================
# 🔥 LLM SQL FALLBACK
# =========================================================

def _handle_llm_sql(question):

    print("\n🧠 FALLBACK: LLM SQL GENERATION")

    try:
        prompt = SQL_GENERATION_PROMPT + "\n\nUSER QUESTION:\n" + question

        sql = call_llm(prompt, MODEL_SQL, 1000,0)

        print("\nGenerated SQL (LLM):\n", sql)

        print("\n⚡ Executing LLM SQL...")
        result = execute_query(sql)

        print("\nRESULT:\n", result)

        explanation = _generate_explanation(
            question,
            None,
            sql,
            result
        )

        print("\n🎯 FINAL ANSWER:\n")
        print(explanation)

        # 🔥 RETURN ONLY FINAL EXPLANATION
        return explanation

    except Exception as e:
        print("❌ LLM SQL failed:", e)
        return "Failed to process query using AI."


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
    except Exception as e:
        return "LLM explanation failed: " + str(e)


# =========================================================
# 🧪 TEST LOOP
# =========================================================

def main():

    print("\n🚀 QUERY ENGINE STARTED\n")

    while True:
        q = input("Ask: ")

        if q.lower() in ["exit", "quit"]:
            break

        result = handle_query(q)

        # optional debug
        print("\n📦 RETURNED (for UI):\n", result)


if __name__ == "__main__":
    main()