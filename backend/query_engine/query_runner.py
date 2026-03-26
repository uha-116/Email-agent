import sys
import json

from backend.query_engine.intent_to_sql import resolve_user_question
from backend.db_storage.db_connection import get_db_connection


# ---------------------------------------------------------
# Convert SQL rows → JSON objects
# Remove null values
# ---------------------------------------------------------

def rows_to_json(cursor, rows):

    if not rows:
        return []

    columns = [col[0] for col in cursor.description]

    results = []

    for row in rows:

        record = {}

        for col, val in zip(columns, row):

            if val is not None:
                record[col] = val

        if record:
            results.append(record)

    return results


# ---------------------------------------------------------
# Execute SQL and return JSON records
# ---------------------------------------------------------

def execute_query(sql):

    if not sql:
        return None

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute(sql)

        rows = cur.fetchall()

        results = rows_to_json(cur, rows)

        # ✅ Gmail link logic INSIDE try
        for record in results:
            gmail_id = record.get("gmail_message_id")

            if gmail_id:
                record["email_link"] = f"https://mail.google.com/mail/u/0/#all/{gmail_id}"

            record.pop("gmail_message_id", None)

        return results

    finally:
        cur.close()
        conn.close()

# ---------------------------------------------------------
# Pretty print JSON
# ---------------------------------------------------------

def print_json(data):

    if not data:
        print("No records found.")
        return

    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------

def main():

    print("\n===============================================")
    print("AI Job Tracker Query Console")
    print("Ask questions about your job pipeline")
    print("Press Ctrl+C to exit")
    print("===============================================\n")

    while True:

        try:

            question = input("Ask: ").strip()

            if not question:
                continue

            # -------------------------------------------------
            # Resolve user question → SQL
            # -------------------------------------------------

            result = resolve_user_question(question)

            if not result:
                print("❌ Could not generate SQL.\n")
                continue

            count_sql = result.get("count_sql")
            list_sql = result.get("list_sql")

            print("\n" + "=" * 80)

            # -------------------------------------------------
            # COUNT QUERY
            # -------------------------------------------------

            if count_sql:

                print("\nCOUNT SQL:")
                print(count_sql)

                records = execute_query(count_sql)

                print("\nCOUNT RESULT:")
                print_json(records)

            # -------------------------------------------------
            # LIST QUERY
            # -------------------------------------------------

            if list_sql:

                print("\nLIST SQL:")
                print(list_sql)

                records = execute_query(list_sql)

                print("\nLIST RESULT:")
                print_json(records)

            print("\n" + "=" * 80 + "\n")

        except KeyboardInterrupt:

            print("\n\nExiting Query Console.")
            sys.exit()


# ---------------------------------------------------------

if __name__ == "__main__":
    main()