# direct_db_insertion.py

from Connection import get_gmail_service
from inbox import get_clean_email_text
from db_Repository import insert_email

START_DATE = "2025/10/01"
END_DATE = "2025/10/11"   # 10-day test
MAX_EMAILS = 50


def main():
    service = get_gmail_service()
    print("✅ Gmail service created")

    query = f"after:{START_DATE} before:{END_DATE}"

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

            email_id = insert_email(
                gmail_message_id=email_data["gmail_message_id"],
                sender=None,              # Gemini later
                subject=email_data["subject"],
                email_type="RAW",
                received_at=email_data["received_at"],
                raw_body_text=email_data["raw_text"]
            )

            print(f"✅ [{idx}] Inserted email_id={email_id}")

        except Exception as e:
            print(f"⚠️ [{idx}] Skipped → {e}")


if __name__ == "__main__":
    main()
