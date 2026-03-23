import time
from datetime import datetime, timedelta

from email_fetcher.connection import get_gmail_service
from email_fetcher.inbox import get_clean_email_text, compute_job_confidence
from email_analyser.email_analyser import analyze_email_batch

from db_storage.db_persistor import persist_email_payload, email_already_processed
from db_storage.db_connection import get_db_connection

from error_handling import BaseAppError, DBConnectionError


# =========================================================
# START DATE
# =========================================================

def compute_start_date():

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT MAX(received_at) FROM emails;")
        result = cur.fetchone()[0]

        if not result:
            return "2026/01/01"

        start_dt = result - timedelta(days=1)
        return start_dt.strftime("%Y/%m/%d")

    except BaseAppError as e:
        print(f"[ERROR] Failed to compute start date → {e}")
        return "2026/01/01"

    finally:
        if cur:
            cur.close()
        if conn:
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

    if "CATEGORY_PROMOTIONS" in label_ids:
        return False

    if "CATEGORY_SOCIAL" in label_ids:
        return False

    return True


# =========================================================
# BUILD BATCH
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

    print("Pipeline run at:", datetime.now())

    # --------------------------------------------------
    # GMAIL SERVICE
    # --------------------------------------------------
    try:
        service = get_gmail_service()
        print("[OK] Gmail service created\n")

    except BaseAppError as e:
        print(f"[CRITICAL] {e.user_message}")
        return

    except Exception as e:
        print(f"[CRITICAL] Gmail connection failed → {e}")
        return

    batch = []
    BATCH_SIZE = 2

    START_DATE = compute_start_date()
    print(f"Auto START_DATE: {START_DATE}")

    query = f"in:inbox after:{START_DATE}"

    messages = []
    page_token = None

    # --------------------------------------------------
    # FETCH EMAIL IDS
    # --------------------------------------------------
    try:
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

    except BaseAppError as e:
        print(f"[ERROR] {e.user_message}")
        return

    except Exception as e:
        print(f"[ERROR] Failed to fetch email list → {e}")
        return

    messages = list(reversed(messages))
    print(f"📩 Total fetched: {len(messages)} emails\n")

    llm_count = 0

    for idx, msg in enumerate(messages, start=1):

        message_id = msg["id"]

        # --------------------------------------------------
        # METADATA
        # --------------------------------------------------
        try:
            metadata = service.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata"
            ).execute()

        except Exception as e:
            print(f"[WARN] Failed metadata fetch | id={message_id} → {e}")
            continue

        label_ids = metadata.get("labelIds", [])
        snippet = metadata.get("snippet", "")

        print("\n" + "="*80)
        print(f"📨 Email #{idx}")
        print(f"🆔 ID: {message_id}")
        print(f"🏷 Labels: {label_ids}")
        print(f"📝 Snippet: {snippet}")

        # --------------------------------------------------
        # LABEL FILTER
        # --------------------------------------------------
        worthy = is_llm_worthy(label_ids)
        print(f"🔍 LLM Worthy: {worthy}")

        if not worthy:
            print("❌ Skipped at LABEL FILTER")
            continue

        # --------------------------------------------------
        # DB CHECK (FIXED → NEW CONNECTION PER EMAIL)
        # --------------------------------------------------
        conn = None
        cur = None

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            already_done = email_already_processed(cur, message_id)
            print(f"🗄 Already Processed: {already_done}")

            if already_done:
                print("❌ Skipped at DB CHECK")
                continue

        except DBConnectionError:
            print("❌ DB unavailable → stopping pipeline")
            return

        except Exception as e:
            print(f"[WARN] DB check failed | id={message_id} → {e}")
            continue

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        # --------------------------------------------------
        # FETCH FULL EMAIL
        # --------------------------------------------------
        try:
            email_data = get_clean_email_text(service, message_id)

        except BaseAppError as e:
            print(f"[WARN] {e}")
            continue

        except Exception as e:
            print(f"[WARN] Failed email fetch | id={message_id} → {e}")
            continue

        subject = email_data.get("subject", "")
        print(f"📌 Subject: {subject}")

        # --------------------------------------------------
        # CONFIDENCE CHECK
        # --------------------------------------------------
        try:
            job_conf = compute_job_confidence(email_data["raw_text"])

        except Exception as e:
            print(f"[WARN] Confidence calc failed | id={message_id} → {e}")
            continue

        print(f"⭐ Confidence: {job_conf}")

        if job_conf < 0.5:
            print("❌ Skipped at CONFIDENCE FILTER")
            continue

        print("✅ PASSED → Adding to batch")

        llm_count += 1

        batch.append({
            "message_id": message_id,
            "email_data": email_data
        })

        if len(batch) < BATCH_SIZE:
            continue

        # --------------------------------------------------
        # GEMINI CALL
        # --------------------------------------------------
        print("\n🚀 Batch full — sending to Gemini\n")

        gemini_input = build_batch(batch)

        try:
            responses = analyze_email_batch(gemini_input)

            if not isinstance(responses, list):
                raise ValueError("Invalid Gemini response format")

        except BaseAppError as e:

            if e.show_to_user:
                print(f"\n🛑 {e.user_message}")
                return

            print(f"\n⚠️ LLM error → {e}")
            batch.clear()
            continue

        except Exception as e:
            print(f"\n⚠️ Gemini failed → {e}")
            batch.clear()
            continue

        time.sleep(2)

        # --------------------------------------------------
        # STORE RESULTS (FIXED → NEW CONNECTION PER EMAIL)
        # --------------------------------------------------
        for r in responses:

            try:
                index = r["index"]
                payload = r["payload"]

            except Exception:
                print("[WARN] Invalid response structure — skipping")
                continue

            email_item = batch[index]
            email_data = email_item["email_data"]
            message_id = email_item["message_id"]

            print("📅 Processing Date:", email_data["received_at"])

            if payload.get("email_type") in ("ERROR", "IGNORE"):
                print("⚠️ Skipped at LLM RESPONSE STAGE")
                continue

            conn = None

            try:
                conn = get_db_connection()

                result = persist_email_payload(
                    payload=payload,
                    gmail_message_id=message_id,
                    received_at=email_data["received_at"],
                    raw_body_text=email_data["raw_text"]
                )

                conn.commit()

                print("✅ Stored successfully")
                print("DB Changes:", result)

            except DBConnectionError:
                print("❌ DB unavailable during insert → stopping pipeline")
                return

            except Exception as e:
                print(f"[WARN] DB STORE FAILED | id={message_id} → {e}")
                continue

            finally:
                if conn:
                    conn.close()

        batch.clear()

    print(f"\n🎯 TOTAL LLM-WORTHY EMAILS PROCESSED: {llm_count}")


if __name__ == "__main__":
    main()