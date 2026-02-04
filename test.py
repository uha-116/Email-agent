import json
from datetime import datetime

from Connection import get_gmail_service
from inbox import get_clean_email_text
from db_Persistor import persist_email_payload, email_already_processed
from db_Connection import get_db_connection


# =========================================================
# 📅 DATE RANGE (IMPORTANT)
# before date must be NEXT DAY to be inclusive
# =========================================================

START_DATE = "2026/01/31"
END_DATE   = "2026/02/04"   # includes Feb completely
MAX_EMAILS = 500


# =========================================================
# 🔍 LLM-WORTHY FILTER (PRIMARY / IMPORTANT)
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


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# =========================================================
# 🚀 MANUAL LLM-ASSISTED PIPELINE (PAGINATED & SAFE)
# =========================================================

def main():
    service = get_gmail_service()
    print("✅ Gmail service created\n")

    query = f"in:inbox after:{START_DATE} before:{END_DATE}"

    # --------------------------------------------------
    # 📩 PAGINATED GMAIL FETCH (CRITICAL FIX)
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
        full = service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject"]
        ).execute()

        label_ids = full.get("labelIds", [])
        headers = full.get("payload", {}).get("headers", [])
        subject = get_header(headers, "Subject")
        snippet = full.get("snippet", "")

        # --------------------------------------------------
        # 2️⃣ FILTER LLM-WORTHY
        # --------------------------------------------------
        if not is_llm_worthy(label_ids):
            continue

        llm_count += 1

        print("\n" + "=" * 100)
        print(f"✅ LLM-WORTHY EMAIL #{llm_count}")
        print(f"Message ID : {message_id}")
        print(f"Subject    : {subject}")
        print(f"Snippet    : {snippet}")
        print(f"Labels     : {label_ids}")
        print("=" * 100)

        # --------------------------------------------------
        # 3️⃣ CHECK IF ALREADY PROCESSED (SAFE DB USAGE)
        # --------------------------------------------------
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            if email_already_processed(cur, message_id):
                print("⏭️ Already processed → skipped\n")
                continue
        finally:
            cur.close()
            conn.close()

        # --------------------------------------------------
        # 4️⃣ FULL EMAIL EXTRACTION
        # --------------------------------------------------
        email_data = get_clean_email_text(message_id)

        print("\n📨 CLEANED EMAIL TEXT (COPY THIS TO GEMINI)")
        print("-" * 100)
        print(email_data["raw_text"])
        print("-" * 100)

        # --------------------------------------------------
        # 5️⃣ MULTI-LINE JSON INPUT (Ctrl+Z + Enter)
        # --------------------------------------------------
        print("\n👉 Paste JSON from Gemini.")
        print("👉 When done, press Ctrl+Z and then Enter (Windows).\n")

        raw_json = ""
        try:
            while True:
                raw_json += input() + "\n"
        except EOFError:
            pass

        raw_json = raw_json.strip()

        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON → skipped ({e})\n")
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

        print("✅ Stored successfully\n")

    print(f"\n🎯 TOTAL LLM-WORTHY EMAILS: {llm_count}")


if __name__ == "__main__":
    main()
