# cli.py

from intent_detector import detect_intent, detect_filters
from sql_builder import build_sql
from db_Connection import get_db_connection
from datetime import datetime

INTENT_FAILURE_LOG = "intent_failures.log"
EMPTY_RESULT_LOG = "empty_results.log"


def log_intent_failure(question: str):
    with open(INTENT_FAILURE_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now()}]\n")
        f.write(f"QUESTION: {question}\n")


def log_empty_result(question: str, intent: str, filters: list, sql: str):
    with open(EMPTY_RESULT_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now()}]\n")
        f.write(f"QUESTION: {question}\n")
        f.write(f"INTENT: {intent}\n")
        f.write(f"FILTERS: {filters}\n")
        f.write("SQL:\n")
        f.write(sql.strip() + "\n")


def main():
    print("🧠 Job Assistant CLI (Ctrl+C to exit)\n")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        while True:
            question = input("❓ Ask: ").strip()
            if not question:
                continue

            intent = detect_intent(question)
            if not intent:
                print("⚠️ Could not detect intent\n")
                log_intent_failure(question)
                continue

            filters = detect_filters(question)
            sql = build_sql(intent, filters)

            print("\n🧩 Detected intent:", intent)
            print("🧩 Detected filters:", filters)
            print("\n🧾 Final SQL:")
            print(sql)

            cur.execute(sql)
            rows = cur.fetchall()

            print("\n📊 SQL Result:")
            if not rows:
                print("(no rows)")
                log_empty_result(question, intent, filters, sql)
            else:
                for r in rows:
                    print(r)

            print("\n" + "-" * 50 + "\n")

    except KeyboardInterrupt:
        print("\n👋 Exiting")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
