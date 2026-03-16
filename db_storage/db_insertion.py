import time
from datetime import datetime

from email_fetcher.connection import get_gmail_service
from email_fetcher.inbox import get_clean_email_text, compute_job_confidence

from email_analyser.email_analyser import analyze_email_batch

from db_storage.db_persistor import persist_email_payload, email_already_processed
from db_storage.db_connection import get_db_connection
# from agent_services.notification_engine import notification_handle
from datetime import timedelta


def compute_start_date():

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            SELECT MAX(last_updated_at)
            FROM opportunities;
        """)

        result = cur.fetchone()[0]

        if not result:
            # First run fallback
            return "2026/01/01"

        start_dt = result - timedelta(days=1)

        return start_dt.strftime("%Y/%m/%d")

    finally:
        cur.close()
        conn.close()

MAX_EMAILS = 500


# =========================================================
# FILTER
# =========================================================

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


# =========================================================
# BUILD BATCH FOR GEMINI
# =========================================================

def build_batch(batch):

    gemini_input = []

    for idx, item in enumerate(batch):

        gemini_input.append({
            "index": idx,
            "text": item["email_data"]["raw_text"]
        })

    return gemini_input


# =========================================================
# MAIN PIPELINE
# =========================================================

def main():

    service = get_gmail_service()

    print("✅ Gmail service created\n")

    batch = []
    BATCH_SIZE = 2

    START_DATE = compute_start_date()

    print(f"Auto START_DATE: {START_DATE}")

    query = f"in:inbox after:{START_DATE}"

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

    llm_count = 0

    for idx, msg in enumerate(messages, start=1):

        message_id = msg["id"]

        metadata = service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata"
        ).execute()

        label_ids = metadata.get("labelIds", [])

        if not is_llm_worthy(label_ids):
            continue

        # -----------------------------------------
        # already processed check
        # -----------------------------------------

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            if email_already_processed(cur, message_id):
                continue
        finally:
            cur.close()
            conn.close()

        try:

            email_data = get_clean_email_text(message_id)

            snippet = metadata.get("snippet", "")

            job_conf = compute_job_confidence(email_data["raw_text"])

            print(f"⭐ Confidence={job_conf}% | snippet={snippet}")

            if job_conf < 0.5:
                print("Skipping the mail due to low confidence")
                continue

            llm_count += 1

            print(f"\n🧠 Processing LLM email #{llm_count} | {message_id}")

            # -----------------------------------------
            # ADD TO BATCH
            # -----------------------------------------

            batch.append({
                "message_id": message_id,
                "email_data": email_data
            })

            if len(batch) < BATCH_SIZE:
                continue

            print("\n🚀 Batch full — sending to Gemini\n")

            gemini_input = build_batch(batch)

            responses = analyze_email_batch(gemini_input)

            print(type(responses))
            print(responses)

            time.sleep(2)

            # -----------------------------------------
            # PROCESS GEMINI OUTPUT
            # -----------------------------------------

            for r in responses:

                index = r["index"]

                payload = r["payload"]

                email_item = batch[index]

                email_data = email_item["email_data"]

                message_id = email_item["message_id"]

                print("Processing Date",email_data["received_at"])

                if payload.get("email_type") == "LLM_QUOTA_EXHAUSTED":

                    print("\n🛑 Gemini quota exhausted. Stopping run safely.")

                    return

                if payload.get("email_type") in ("ERROR", "IGNORE"):
                    continue

                # ✅ FIX — per record failure isolation
                try:

                    result = persist_email_payload(
                        payload=payload,
                        gmail_message_id=message_id,
                        received_at=email_data["received_at"],
                        raw_body_text=email_data["raw_text"]
                    )

                    print("✅ Stored successfully")
                    print("DB Changes:", result)

                    # notification_handle(result)

                except Exception as e:

                    print(f"⚠️ Skipping record index={index} | message_id={message_id}")
                    print(f"Reason → {e}")

                    continue

            # -----------------------------------------
            # CLEAR BATCH
            # -----------------------------------------

            batch.clear()

        except Exception as e:

            print(f"❌ Failed for {message_id} → {e}")

    print(f"\n🎯 TOTAL LLM-WORTHY EMAILS PROCESSED: {llm_count}")


if __name__ == "__main__":
    main()