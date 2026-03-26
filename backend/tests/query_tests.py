import sys
import json
import os
from dotenv import load_dotenv

from backend.query_engine.intent_to_sql import resolve_user_question
from backend.query_engine.sql_validator import validate_sql
from backend.query_engine.query_runner import execute_query

from backend.email_analyser.llm_gemini import call_llm
from backend.email_analyser.prompts import SQL_EXPLANATION_PROMPT


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv()

MODEL_SQL_EXPLANATION = os.getenv("EXPLANATION_MODEL")


# ---------------------------------------------------------
# Pretty JSON printer
# ---------------------------------------------------------

def print_json(data):

    if not data:
        print("No records found.")
        return

    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------
# Load questions from data.json
# ---------------------------------------------------------

def load_questions():

    with open("data/data.json", "r") as f:
        data = json.load(f)

    return data


# ---------------------------------------------------------
# Send results to Gemini for explanation
# ---------------------------------------------------------

def explain_with_llm(question, count_sql, list_sql, records):

    sql_section = ""

    if count_sql:
        sql_section += "COUNT SQL:\n" + count_sql + "\n\n"

    if list_sql:
        sql_section += "LIST SQL:\n" + list_sql + "\n\n"

    prompt = (
        SQL_EXPLANATION_PROMPT
        + "\n\nUSER QUESTION:\n"
        + question
        + "\n\nSQL QUERIES Constructed:\n"
        + sql_section
        + "\nRETRIEVED DATA:\n"
        + json.dumps(records, indent=2, default=str)
    )

    try:
        response=call_llm(prompt, MODEL_SQL_EXPLANATION,0)
    except Exception as e:
        response="LLM Call failed"+str(e)
        
    print("\nLLM RESPONSE\n")
    print(response)
    print()


# ---------------------------------------------------------
# Main runner
# ---------------------------------------------------------

def main():

    print("\n===================================================")
    print("AI Job Tracker Query Pipeline Test Console")
    print("===================================================\n")

    questions = load_questions()

    for item in questions:

        question = item["question"]

        print("\n===================================================")
        print("QUESTION:")
        print(question)
        print("===================================================\n")

        # -------------------------------------------------
        # STEP 1: Generate SQL
        # -------------------------------------------------

        result = resolve_user_question(question)

        if not result:
            print("❌ No SQL generated\n")
            continue

        if "route" in result:

            print("\n⚠ Routing Decision\n")
            print(result["route"])

            print("\nSQL must be generated through the LLM\n")
            continue

        count_sql = result.get("count_sql")
        list_sql = result.get("list_sql")

        print("\nGenerated SQL\n")

        if count_sql:
            print("COUNT SQL:")
            print(count_sql)
            print()

        if list_sql:
            print("LIST SQL:")
            print(list_sql)
            print()

        # -------------------------------------------------
        # STEP 2: Validate SQL
        # -------------------------------------------------

        validation = validate_sql(
            question,
            count_sql,
            list_sql
        )

        decision = validation["decision"]
        reason = validation["reason"]

        print("Validation Result\n")
        print(json.dumps(validation, indent=2))
        print()

        if decision != "YES":

            print("⚠ SQL rejected by validator")
            print("Reason:", reason)
            print("\nSQL must be generated through the LLM\n")

            continue

        # -------------------------------------------------
        # Ask if user wants to execute queries
        # -------------------------------------------------

        execute = input("Do you want to execute the query? (y/n): ").strip().lower()

        if execute != "y":
            print("Skipping query execution.\n")
            continue

        # -------------------------------------------------
        # STEP 3: Execute COUNT SQL
        # -------------------------------------------------

        count_records = None
        list_records = None

        if count_sql:

            print("\nExecuting COUNT SQL\n")
            print(count_sql)
            print()

            count_records = execute_query(count_sql)

            print("COUNT RESULT\n")
            print_json(count_records)
            print()

        # -------------------------------------------------
        # STEP 4: Execute LIST SQL
        # -------------------------------------------------

        if list_sql:

            print("\nExecuting LIST SQL\n")
            print(list_sql)
            print()

            list_records = execute_query(list_sql)

            print("LIST RESULT\n")
            print_json(list_records)
            print()

        # -------------------------------------------------
        # Ask if user wants LLM explanation
        # -------------------------------------------------

        use_llm = input("Do you want to send results to LLM for explanation? (y/n): ").strip().lower()

        if use_llm == "y":

            records={"Count_Result":count_records,"List_Result":list_records}

            explain_with_llm(
                question,
                count_sql,
                list_sql,
                records
            )

        else:
            print("Skipping LLM explanation.\n")

        # -------------------------------------------------
        # Ask to continue
        # -------------------------------------------------

        cont = input("Continue to next question? (y/n): ").strip().lower()

        if cont=='n':
            continue

        if cont not in["y",'n']:
            print("\nExiting program.")
            sys.exit()

    print("\nAll questions processed.")


# ---------------------------------------------------------

if __name__ == "__main__":
    main()