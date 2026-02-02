from Connection import get_gmail_service

START_DATE = "2026/01/01"
END_DATE   = "2026/01/10"
MAX_EMAILS = 200


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def is_llm_worthy(label_ids):
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

    results = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=MAX_EMAILS
    ).execute()

    messages = results.get("messages", [])
    print(f"📩 Total fetched: {len(messages)}\n")

    llm_count = 0

    for msg in messages:
        full = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["From", "Subject"]
        ).execute()

        labels = full.get("labelIds", [])
        snippet = full.get("snippet", "")
        headers = full.get("payload", {}).get("headers", [])

        subject = get_header(headers, "Subject")

        if is_llm_worthy(labels):
            llm_count += 1
            print("✅ LLM EMAIL")
            print("Subject :", subject)
            print("Snippet :", snippet)
            print("Labels  :", labels)
            print("-" * 80)

    print(f"\n🎯 TOTAL LLM-WORTHY EMAILS: {llm_count}")


if __name__ == "__main__":
    main()
