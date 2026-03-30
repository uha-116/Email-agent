import time
from datetime import datetime, timedelta

from backend.email_fetcher.connection import get_gmail_service
from backend.email_fetcher.inbox import get_clean_email_text, compute_job_confidence
from backend.email_analyser.email_analyser import analyze_email_batch

from backend.db_storage.db_persistor import persist_email_payload, email_already_processed
from backend.db_storage.db_connection import get_db_connection
from backend.agent_services.notification_engine import notification_handle

from backend.error_handling import (
    BaseAppError,
    DBConnectionError,
    MessageNotFoundError,
    Base64DecodeError,
    GmailFetchError,
    LLMValidationError,
    LLMOutputFormatError,
    NetworkError,
    RateLimitError,
    ServiceUnavailableError,
    AuthenticationError,
    NetworkDownError
)

import os

LOCK_FILE = "pipeline.lock"

def acquire_lock():
    if os.path.exists(LOCK_FILE):
        print("⚠️ Another instance running. Exiting...")
        return False

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    return True


def release_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

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

    if "IMPORTANT" not in label_ids:
        return False

    

    return True


# =========================================================
# BUILD BATCH
# =========================================================

def build_batch(batch):

    return [
        {"index": idx, "text": item["email_data"]["raw_text"]}
        for idx, item in enumerate(batch)
    ]


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
        print(f"🛑 CRITICAL: {e.user_message}")
        return

    except Exception as e:
        print(f"🛑 Gmail connection failed → {e}")
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
        print(f"🛑 ERROR: {e.user_message}")
        return

    except Exception as e:
        print(f"🛑 Failed to fetch email list → {e}")
        return

    messages = list(reversed(messages))
    print(f"📩 Total fetched: {len(messages)} emails\n")

    for idx, msg in enumerate(messages, start=1):

        message_id = msg["id"]

        print("\n" + "="*80)
        print(f"📨 Email #{idx} | ID: {message_id}")

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
            print(f"⚠️ Skipping {message_id} → metadata fetch failed: {e}")
            continue

        label_ids = metadata.get("labelIds", [])
        snippet = metadata.get("snippet", "")

        internal_ts = metadata.get("internalDate")

        received_at = None
        if internal_ts:
            try:
                received_at = datetime.fromtimestamp(int(internal_ts) / 1000)
            except Exception:
                received_at = None

        print(f"📅 Date: {received_at}")

        print(f"🏷 Labels: {label_ids}")
        print(f"📝 Snippet: {snippet}")

        if not is_llm_worthy(label_ids):
            print("❌ Skipped (label filter)")
            continue

        # --------------------------------------------------
        # DB CHECK
        # --------------------------------------------------
        conn = None
        cur = None
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            if email_already_processed(cur, message_id):
                print("❌ Already processed")
                continue

        except DBConnectionError as e:
            print(f"🛑 DB ERROR: {e.user_message}")
            return

        except Exception as e:
            print(f"⚠️ Skipping {message_id} → DB check failed: {e}")
            continue

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

        # --------------------------------------------------
        # FETCH EMAIL CONTENT
        # --------------------------------------------------
        try:
            email_data = get_clean_email_text(service, message_id)
            print(email_data["raw_text"][:100])

        except (MessageNotFoundError, Base64DecodeError) as e:
            print(f"⚠️ Skipping {message_id} → {e}")
            continue

        except GmailFetchError as e:
            print(f"⚠️ Skipping {message_id} after retries → {e}")
            continue
        
        # 🔴 HARD NETWORK FAILURE → STOP
        except NetworkDownError as e:
            print(f"🛑 NETWORK DOWN: {e.user_message}")
            return

        except BaseAppError as e:
            print(f"⚠️ Skipping {message_id} → {e}")
            continue

        except Exception as e:
            print(f"⚠️ Skipping {message_id} → unexpected error: {e}")
            continue

        # --------------------------------------------------
        # CONFIDENCE
        # --------------------------------------------------
        try:
            job_conf = compute_job_confidence(email_data["raw_text"])

        except Exception as e:
            print(f"⚠️ Skipping {message_id} → confidence failed: {e} with {job_conf}")
            continue

        if job_conf < 0.5:
            print(f"❌ Skipped (low confidence) with {job_conf}")
            continue

        batch.append({
            "message_id": message_id,
            "email_data": email_data
        })

        if len(batch) < BATCH_SIZE:
            continue

        # --------------------------------------------------
        # LLM CALL
        # --------------------------------------------------
        print("\n🚀 Sending batch to Gemini\n")

        try:
            responses = analyze_email_batch(build_batch(batch))

            if not isinstance(responses, list):
                raise ValueError("Invalid response format")

        except (LLMValidationError, LLMOutputFormatError) as e:
            print(f"⚠️ LLM output issue → skipping batch: {e}")
            batch.clear()
            continue
        
        # 🔴 HARD NETWORK FAILURE → STOP
        except NetworkDownError as e:
            print(f"🛑 NETWORK DOWN: {e.user_message}")
            return
        

        # 🔴 HANDLE RATE LIMIT SEPARATELY
        except RateLimitError as e:

            if "DAILY_QUOTA_EXHAUSTED" in str(e):
                print("🛑 STOPPING PIPELINE → DAILY QUOTA HIT")
                return   # 🔥 STOP ENTIRE PIPELINE

            print(f"⚠️ TEMP RATE LIMIT → skipping batch: {e}")
            batch.clear()
            continue


        # -----------------------------
        # 🟡 NETWORK ERROR → SKIP
        # -----------------------------
        except NetworkError as e:
            print(f"⚠️ LLM TEMP ERROR → skipping batch: {e}")
            batch.clear()
            continue

        # -----------------------------
        # 🔴 SERVICE DOWN → STOP
        # -----------------------------
        except ServiceUnavailableError as e:
            print(f"🛑 LLM SERVICE DOWN → stopping pipeline: {e}")
            return

        # 🔥 FATAL AUTH ERROR → STOP
        except AuthenticationError as e:
            print(f"🛑 LLM AUTH ERROR: {e.user_message}")
            return

        # 🔥 OTHER APP ERRORS → SKIP
        except BaseAppError as e:
            print(f"⚠️ Unexpected LLM error → skipping batch: {e}")
            batch.clear()
            continue

        except Exception as e:
            print(f"⚠️ LLM failure → skipping batch: {e}")
            batch.clear()
            continue

        time.sleep(1)

        # --------------------------------------------------
        # STORE RESULTS
        # --------------------------------------------------
        for r in responses:

            try:
                index = r["index"]
                payload = r["payload"]

            except Exception:
                print("⚠️ Invalid LLM response structure → skipping")
                continue

            email_item = batch[index]
            message_id = email_item["message_id"]
            email_data = email_item["email_data"]

            if payload.get("email_type") in ("ERROR", "IGNORE"):
                print(f"⚠️ Skipping {message_id} (LLM ignored)")
                continue

            try:

                result=persist_email_payload(
                    payload=payload,
                    gmail_message_id=message_id,
                    received_at=email_data["received_at"],
                    raw_body_text=email_data["raw_text"]
                )

                print(f"✅ Stored {message_id}")

            # 🔥 Trigger notification

                try:
                    notification_handle(result)
                except Exception as e:
                    print(f"⚠️ Notification failed: {e}")


            except DBConnectionError as e:
                print(f"🛑 DB ERROR during insert: {e.user_message}")
                return

            except NetworkDownError as e:
                print(f"🛑 NETWORK DOWN: {e.user_message}")
                return

            except Exception as e:
                print(f"⚠️ Skipping {message_id} → DB insert failed: {e}")
                continue


        batch.clear()

    print("\n🎯 Pipeline completed successfully")


if __name__ == "__main__":
    if not acquire_lock():
        exit()

    try:
        main()
    except Exception as e:
        print(f"🛑 CRON FATAL ERROR → {e}")
    finally:
        release_lock()