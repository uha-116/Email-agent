import time
from datetime import datetime

from Connection import get_gmail_service
from inbox import get_clean_email_text,compute_job_confidence
from email_analyser import analyze_email
from db_Persistor import persist_email_payload, email_already_processed
from db_Connection import get_db_connection


# =========================================================
# 📅 DATE RANGE (INCREMENTAL RUN)
# before date must be NEXT DAY to be inclusive
# =========================================================

START_DATE = "2026/02/02"
END_DATE   = "2026/02/05"   # includes entire February
MAX_EMAILS = 500


# =========================================================
# 🔍 LLM-WORTHY FILTER (PRIMARY / IMPORTANT ONLY)
# =========================================================

def is_llm_worthy(label_ids: list[str]) -> bool:
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
# 🚀 AUTOMATED PIPELINE (GEMINI ENABLED)
# =========================================================

def main():
    service = get_gmail_service()
    print("✅ Gmail service created\n")

    query = f"in:inbox after:{START_DATE} before:{END_DATE}"

    # --------------------------------------------------
    # 📩 PAGINATED GMAIL FETCH (CRITICAL)
    # --------------------------------------------------
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

    # --------------------------------------------------
    # 🔁 PROCESS EMAILS
    # --------------------------------------------------
    for idx, msg in enumerate(messages, start=1):
        message_id = msg["id"]

        # --------------------------------------------------
        # 1️⃣ METADATA FETCH (cheap)
        # --------------------------------------------------
        metadata = service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata"
        ).execute()

        label_ids = metadata.get("labelIds", [])
 

        # --------------------------------------------------
        # 2️⃣ FILTER NON-LLM EMAILS EARLY
        # --------------------------------------------------
        if not is_llm_worthy(label_ids):
            continue

        
        # --------------------------------------------------
        # 3️⃣ CHECK IF ALREADY PROCESSED (NEON-SAFE)
        # --------------------------------------------------
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            if email_already_processed(cur, message_id):
                continue
        finally:
            cur.close()
            conn.close()

        try:
            # --------------------------------------------------
            # 4️⃣ FULL EMAIL EXTRACTION
            # --------------------------------------------------
            email_data = get_clean_email_text(message_id)
            snippet = metadata.get("snippet", "")
            job_conf = compute_job_confidence(email_data["raw_text"])
            print(f"⭐ Confidence={job_conf}% | snippet={snippet}")

            if job_conf <= 0.5:
                print("Skipping the mail due to low confidence")
                continue
            
            llm_count += 1
            print(f"\n🧠 Processing LLM email #{llm_count} | {message_id}")
            # --------------------------------------------------
            # 5️⃣ LLM ANALYSIS (STRICT PROMPT)
            # --------------------------------------------------
            payload = analyze_email(email_data["raw_text"])
            print(payload)

            time.sleep(2)  # throttle Gemini safely

            # 🛑 LLM quota exhausted → STOP CLEANLY
            if payload.get("email_type") == "LLM_QUOTA_EXHAUSTED":
                print("\n🛑 Gemini quota exhausted. Stopping run safely.")
                break

            # ⚠️ Skip bad LLM output
            if payload.get("email_type") in ("ERROR", "IGNORE"):
                continue

            # --------------------------------------------------
            # 6️⃣ INSERT / UPDATE DATABASE
            # --------------------------------------------------
            persist_email_payload(
                payload=payload,
                gmail_message_id=email_data["gmail_message_id"],
                received_at=email_data["received_at"],
                raw_body_text=email_data["raw_text"]
            )

            print("✅ Stored successfully")

        except Exception as e:
            print(f"❌ Failed for {message_id} → {e}")

    print(f"\n🎯 TOTAL LLM-WORTHY EMAILS PROCESSED: {llm_count}")


if __name__ == "__main__":
    main()
