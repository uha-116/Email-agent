import json
import sys
from sql_builder import build_sql
from db_Connection_test import get_db_connection


# ---------- Load Questions ----------
def load_questions():
    with open("data.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- Match Question ----------
def find_question(user_input, questions):
    for item in questions:
        if item["question"].lower() == user_input.lower():
            return item
    return None


# ---------- Execute SQL ----------
def execute_sql(sql):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(sql)
        rows = cursor.fetchall()

        col_names = [desc[0] for desc in cursor.description]

        cursor.close()
        conn.close()

        return col_names, rows

    except Exception as e:
        print("\n❌ Database Error:", e)
        return None, None


# ---------- Pretty Print ----------
def print_results(columns, rows):
    if not rows:
        print("\n⚠️ No records found.\n")
        return

    print("\n" + "=" * 70)
    print("Results:\n")

    for i, row in enumerate(rows, 1):
        row_dict = dict(zip(columns, row))
        print(f"{i}. {row_dict}")

    print("\nTotal Records:", len(rows))
    print("=" * 70 + "\n")


# ---------- Main ----------
def main():
    questions = load_questions()

    print("\n🚀 Query Execution Console")
    print("Type exact question from data.json\n")

    try:
        while True:
            user_input = input("Enter Question: ").strip()

            if not user_input:
                continue

            matched = find_question(user_input, questions)

            if not matched:
                print("\n❌ Question not found in data.json\n")
                continue

            # Build SQL
            sql = build_sql(matched)

            print("\nGenerated SQL:\n")
            print(sql)

            # Execute
            columns, rows = execute_sql(sql)

            if columns:
                print_results(columns, rows)

    except KeyboardInterrupt:
        print("\n\n👋 Exiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
