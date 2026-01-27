from datetime import date
from Connection import get_gmail_service
from inbox import get_clean_email_text
from email_analyser import analyze_email
from db_Persistor import persist_email_payload

START_DATE = "2025/01/01"
MAX_EMAILS = 100  # safe batch

def main():
    service = get_gmail_service()
    print("✅ Gmail service created")

    query = f"after:{START_DATE}"

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=MAX_EMAILS
    ).execute()

    messages = results.get("messages", [])
    print(f"📩 Found {len(messages)} emails")

    for idx, msg in enumerate(messages, start=1):
        message_id = msg["id"]

        try:
            email_data = get_clean_email_text(message_id)

            payload = analyze_email(email_data["raw_text"])

            # 🛑 LLM quota exhausted
            if payload.get("email_type") == "LLM_QUOTA_EXHAUSTED":
                print("\n🛑 LLM quota exhausted. Stopping safely.")
                break

            if payload.get("email_type") == "ERROR":
                print(f"⚠️ [{idx}] Gemini error → skipped")
                continue

            result = persist_email_payload(
                payload=payload,
                gmail_message_id=email_data["gmail_message_id"],
                received_at=email_data["received_at"],
                raw_body_text=email_data["raw_text"]
            )

            if result["email_id"]:
                print(f"✅ [{idx}] Stored email_id={result['email_id']}")
            else:
                print(f"⏭️ [{idx}] Already processed")

        except Exception as e:
            print(f"❌ [{idx}] Failed → {e}")

if __name__ == "__main__":
    main()
