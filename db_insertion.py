from datetime import date
from Connection import get_gmail_service
from inbox import get_clean_email_text
from email_analyser import analyze_email
from db_Persistor import persist_email_payload, email_already_processed
from db_Connection import get_db_connection
import time

MAX_EMAILS = 50
START_DATE = "2025/01/01"
END_DATE = "2025/01/06"

def main():
    service = get_gmail_service()
    print("✅ Gmail service created")
    query = f"in:inbox category:primary after:2025/01/01 before:2025/01/06"

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=MAX_EMAILS
    ).execute()

    messages = list(reversed(results.get("messages", [])))
    print(f"📩 Found {len(messages)} emails")

    # 🔑 One DB connection for pre-checks
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        for idx, msg in enumerate(messages, start=1):
            message_id = msg["id"]

            # 🚫 SKIP EARLY (NO LLM CALL)
            if email_already_processed(cur, message_id):
                print(f"⏭️ [{idx}] Already processed → skipping")
                continue

            try:
                # 1️⃣ Extract email only if needed
                email_data = get_clean_email_text(message_id)

                # 2️⃣ LLM analysis
                payload = analyze_email(email_data["raw_text"])
                print(f"\n🧠 JSON for message_id={message_id}")
                print(payload)

                time.sleep(2)  # throttle

                # 🛑 Quota exhausted
                if payload.get("email_type") == "LLM_QUOTA_EXHAUSTED":
                    print("\n🛑 LLM quota exhausted. Stopping safely.")
                    break

                if payload.get("email_type") == "ERROR":
                    print(f"\n⚠️ [{idx}] LLM ERROR → skipped")
                    print(payload.get("error"))
                    continue

                if payload.get("email_type") == "IGNORE":
                    print(f"🗑️ [{idx}] Ignored mail")
                    continue

                # 3️⃣ Persist
                persist_email_payload(
                    payload=payload,
                    gmail_message_id=email_data["gmail_message_id"],
                    received_at=email_data["received_at"],
                    raw_body_text=email_data["raw_text"]
                )

                print(f"✅ [{idx}] Stored successfully")

            except Exception as e:
                print(f"❌ [{idx}] Failed → {e}")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
