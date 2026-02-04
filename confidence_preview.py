from Connection import get_gmail_service
from inbox import compute_job_confidence


# =========================================================
# 📅 DATE RANGE
# =========================================================

START_DATE = "2026/01/31"
END_DATE   = "2026/02/04"
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


# =========================================================
# 🔍 HEADER HELPER
# =========================================================

def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


# =========================================================
# 📊 CONFIDENCE PREVIEW (LLM-WORTHY ONLY)
# =========================================================

def main():
    service = get_gmail_service()
    print("✅ Gmail service created\n")

    query = f"in:inbox after:{START_DATE} before:{END_DATE}"

    # --------------------------------------------------
    # 📩 PAGINATED FETCH
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

    print(f"📩 Total fetched: {len(messages)} emails\n")

    llm_count = 0

    # --------------------------------------------------
    # 🔁 PROCESS EACH EMAIL
    # --------------------------------------------------
    for msg in messages:
        message_id = msg["id"]

        # -------------------------------
        # Fetch METADATA only
        # -------------------------------
        full = service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject"]
        ).execute()

        headers = full.get("payload", {}).get("headers", [])
        subject = get_header(headers, "Subject")
        snippet = full.get("snippet", "")
        label_ids = full.get("labelIds", [])

        # -------------------------------
        # LLM-WORTHY FILTER
        # -------------------------------
        if not is_llm_worthy(label_ids):
            continue

        llm_count += 1

        # -------------------------------
        # Compute confidence
        # -------------------------------
        text = f"{subject} {snippet}"
        confidence = compute_job_confidence(text)

        # -------------------------------
        # PRINT RESULT
        # -------------------------------
        print("\n" + "=" * 100)
        print(f"📧 LLM-WORTHY EMAIL #{llm_count}")
        print(f"Message ID : {message_id}")
        print(f"Subject    : {subject}")
        print(f"Snippet    : {snippet}")
        print(f"Labels     : {label_ids}")
        print(f"🎯 Job Confidence : {confidence:.2f}")
        print("=" * 100)

    print(f"\n🎯 TOTAL LLM-WORTHY EMAILS SHOWN: {llm_count}")
    print("✅ Confidence preview completed.")


if __name__ == "__main__":
    main()
