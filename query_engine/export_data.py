import os
import json
from psycopg2.extras import RealDictCursor
from db_Connection_test import get_db_connection

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
OUTPUT_DIR = "data"
SAMPLE_LIMIT = 300  # change to None to export ALL rows

TABLES = [
    "emails",
    "opportunities",
    "opportunity_details",
    "linkedin_events"
]

# --------------------------------------------------
# Ensure data folder exists
# --------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --------------------------------------------------
# Export logic
# --------------------------------------------------
def export_table(cursor, table_name):
    print(f"📤 Exporting table: {table_name}")

    query = f"SELECT * FROM {table_name}"
    if SAMPLE_LIMIT:
        query += f" LIMIT {SAMPLE_LIMIT}"

    cursor.execute(query)
    rows = cursor.fetchall()

    file_path = os.path.join(OUTPUT_DIR, f"{table_name}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)

    print(f"✅ Saved {len(rows)} records → {file_path}")


def main():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        for table in TABLES:
            export_table(cursor, table)

        cursor.close()

    except Exception as e:
        print("❌ Error while exporting data:", e)

    finally:
        if conn:
            conn.close()
            print("🔒 Database connection closed")


# --------------------------------------------------
# Entry point
# --------------------------------------------------
if __name__ == "__main__":
    main()
