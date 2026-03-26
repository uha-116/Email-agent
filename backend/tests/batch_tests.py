import json
from backend.email_fetcher.connection import get_gmail_service
from backend.email_fetcher.inbox import get_clean_email_text, compute_job_confidence

from backend.db_storage.db_persistor import email_already_processed
from backend.db_storage.db_connection import get_db_connection


START_DATE = "2026/03/09"
END_DATE   = "2026/03/16"

MAX_EMAILS = 500
BATCH_SIZE = 2


def is_llm_worthy(label_ids: list[str]):

    if "INBOX" not in label_ids:
        return False

    if "CATEGORY_UPDATES" not in label_ids:
        return False

    if "IMPORTANT" not in label_ids:
        return False

    if "CATEGORY_PROMOTIONS" in label_ids:
        return False

    if "CATEGORY_SOCIAL" in label_ids:
        return False

    return True


def main():

    service = get_gmail_service()

    print("✅ Gmail service created\n")

    query = f"in:inbox after:{START_DATE} before:{END_DATE}"

    messages = []
    page_token = None

    while True:

        resp = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=MAX_EMAILS,
            pageToken=page_token
        ).execute()

        messages.extend(resp.get("messages", []))

        page_token = resp.get("nextPageToken")

        if not page_token:
            break

    messages = list(reversed(messages))

    print(f"📩 Total fetched: {len(messages)} emails\n")

    batch = []

    for msg in messages:

        message_id = msg["id"]

        metadata = service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata"
        ).execute()

        label_ids = metadata.get("labelIds", [])

        if not is_llm_worthy(label_ids):
            continue

        # ---------------------------------------
        # Already processed check
        # ---------------------------------------

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            if email_already_processed(cur, message_id):
                print(f"Skipping processed email: {message_id}")
                continue
        finally:
            cur.close()
            conn.close()

        try:

            email_data = get_clean_email_text(message_id)

            job_conf = compute_job_confidence(email_data["raw_text"])

            if job_conf <= 0.5:

                subject = email_data.get("subject", "")
                snippet = metadata.get("snippet", "")

                print(f"\n⚠️ Low confidence email skipped")
                print(f"Subject: {subject}")
                print(f"Snippet: {snippet}\n")

                continue

            print(f"\n📨 Adding email to batch: {message_id}")

            batch.append({
                "message_id": message_id,
                "email_data": email_data
            })
            # ---------------------------------------
            # Wait until batch fills
            # ---------------------------------------

            if len(batch) < BATCH_SIZE:
                continue

            print("\n🚀 Batch Full — Preparing Gemini Input\n")
            print("\nPrepared Batch")
            print(batch)

            gemini_input = []

            for idx, item in enumerate(batch):

                gemini_input.append({
                    "index": idx,
                    "text": item["email_data"]["raw_text"]
                })

            print("Gemini Input Payload:\n")

            print(json.dumps(gemini_input, indent=2))

            print("\n-----------------------------\n")

            # Clear batch
            batch = []

        except Exception as e:

            print(f"❌ Failed processing {message_id}: {e}")


if __name__ == "__main__":
    main()