import sys
import json

from backend.query_engine.intent_to_sql import resolve_user_question
from backend.query_engine.sql_validator import validate_sql


# ---------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------

def print_json(data):
    print(json.dumps(data, indent=2))


# ---------------------------------------------------------
# Test loop
# ---------------------------------------------------------

def main():

    print("\n==============================================")
    print("SQL Validation Test Console")
    print("Press Ctrl+C to exit")
    print("==============================================\n")

    while True:

        try:

            user_question = input("Ask: ").strip()

            if not user_question:
                continue

            # ---------------------------------------------
            # Generate SQL
            # ---------------------------------------------

            result = resolve_user_question(user_question)

            if not result:
                print("❌ No SQL generated\n")
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

            # ---------------------------------------------
            # Validate SQL
            # ---------------------------------------------

            validation = validate_sql(
                user_question,
                count_sql,
                list_sql
            )

            print("Validation Result\n")
            print(validation)

            print("\n" + "=" * 80 + "\n")

        except KeyboardInterrupt:

            print("\nExiting SQL validation test.")
            sys.exit()


# ---------------------------------------------------------

if __name__ == "__main__":
    main()