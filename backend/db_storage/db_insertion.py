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
    NetworkDownError,
    LLMAPIError
)

import os

metrics = {
    "emails_seen": 0,
    "emails_filtered": 0,
    "emails_processed": 0,
    "emails_stored": 0,
    "emails_failed": 0,
    "llm_calls": 0,
    "llm_failures": 0
}


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
    metrics["emails_seen"] = len(messages)
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
            metrics["emails_filtered"] += 1
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
                metrics["emails_filtered"] += 1
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
            metrics["emails_failed"] += 1
            print(f"⚠️ Skipping {message_id} → {e}")
            continue

        except GmailFetchError as e:
            metrics["emails_failed"] += 1
            print(f"⚠️ Skipping {message_id} after retries → {e}")
            continue
        
        # 🔴 HARD NETWORK FAILURE → STOP
        except NetworkDownError as e:
            metrics["emails_failed"] += 1
            print(f"🛑 NETWORK DOWN: {e.user_message}")
            return

        except BaseAppError as e:
            metrics["emails_failed"] += 1
            print(f"⚠️ Skipping {message_id} → {e}")
            continue

        except Exception as e:
            metrics["emails_failed"] += 1
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
            metrics["emails_filtered"] += 1
            continue

        metrics["emails_processed"] += 1

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

        metrics["llm_calls"] += 1
        llm_success = False
        llm_failed = False

        try:
            valid_items, invalid_items = analyze_email_batch(build_batch(batch))
            llm_success = True

        # 🔴 FULL FAIL → fallback
        except (LLMValidationError, LLMOutputFormatError, LLMAPIError) as e:

            print(f"⚠️ Batch failed → fallback to single: {e}")

            responses = []

            for i, item in enumerate(batch):
                try:
                    single_input = [{"index": 0, "text": item["email_data"]["raw_text"]}]
                    metrics["llm_calls"] += 1
                    single_valid, _ = analyze_email_batch(single_input)

                    if single_valid:
                        llm_success = True 
                        single_valid[0]["index"] = i
                        responses.extend(single_valid)

                except Exception as inner_e:
                    print(f"⚠️ Skipping {item['message_id']} → {inner_e}")

            if not responses:
                batch.clear()
                continue

        # 🔴 HARD NETWORK FAILURE → STOP
        except NetworkDownError as e:
            
            print(f"🛑 NETWORK DOWN: {e.user_message}")
            return

        # 🔴 RATE LIMIT
        except RateLimitError as e:
           
            if "DAILY_QUOTA_EXHAUSTED" in str(e):
                print("🛑 STOPPING PIPELINE → DAILY QUOTA HIT")
                return

            print(f"⚠️ TEMP RATE LIMIT → skipping batch: {e}")
            batch.clear()
            continue

        # 🟡 NETWORK ERROR → SKIP
        except NetworkError as e:


            print(f"⚠️ LLM TEMP ERROR → skipping batch: {e}")
            batch.clear()
            continue

        # 🔴 SERVICE DOWN
        except ServiceUnavailableError as e:
            
            print(f"🛑 LLM SERVICE DOWN → stopping pipeline: {e}")
            return

        # 🔴 AUTH ERROR
        except AuthenticationError as e:
           
            print(f"🛑 LLM AUTH ERROR: {e.user_message}")
            return

        # 🔥 OTHER APP ERRORS
        except BaseAppError as e:
            print(f"⚠️ Unexpected LLM error → skipping batch: {e}")
            batch.clear()
            continue

        except Exception as e:
            
            print(f"⚠️ LLM failure → skipping batch: {e}")
            batch.clear()
            continue

        # 🟢 SUCCESS / PARTIAL CASE
        else:
            # 👇 IMPORTANT
            if not llm_failed:
                responses = valid_items

                # 🔁 retry invalid only
                for bad in invalid_items:
                    idx = bad["item"].get("index")

                    if idx is None:
                        continue

                    item = batch[idx]

                    try:
                        single_input = [{"index": 0, "text": item["email_data"]["raw_text"]}]
                        metrics["llm_calls"] += 1
                        single_valid, _ = analyze_email_batch(single_input)

                        if single_valid:
                            llm_success = True 
                            single_valid[0]["index"] = idx
                            responses.append(single_valid[0])

                    except Exception as inner_e:
                        print(f"⚠️ Retry failed for {item['message_id']} → {inner_e}")

        # --------------------------------------------------
        # FINAL LLM FAILURE CHECK
        # --------------------------------------------------
        if not llm_success:
            metrics["llm_failures"] += 1
        # --------------------------------------------------
        # STORE RESULTS
        # --------------------------------------------------
        for r in responses:

            try:
                index = r["index"]
                payload = r["payload"]

            except Exception:
                metrics["emails_failed"] += 1
                print("⚠️ Invalid LLM response structure → skipping")
                continue

            email_item = batch[index]
            message_id = email_item["message_id"]
            email_data = email_item["email_data"]

            if payload.get("email_type") == "ERROR":
                metrics["emails_failed"] += 1
                continue

            try:

                result=persist_email_payload(
                    payload=payload,
                    gmail_message_id=message_id,
                    received_at=email_data["received_at"],
                    raw_body_text=email_data["raw_text"]
                )

                print(f"✅ Stored {message_id}")
                metrics["emails_stored"] += 1

            # 🔥 Trigger notification

                try:
                    notification_handle(result)
                except Exception as e:
                    print(f"⚠️ Notification failed: {e}")


            except DBConnectionError as e:
                metrics["emails_failed"] += 1
                print(f"🛑 DB ERROR during insert: {e.user_message}")
                return

            except NetworkDownError as e:
                metrics["emails_failed"] += 1
                print(f"🛑 NETWORK DOWN: {e.user_message}")
                return

            except Exception as e:
                metrics["emails_failed"] += 1
                print(f"⚠️ Skipping {message_id} → DB insert failed: {e}")
                continue


        batch.clear()


    print("\n📊 METRICS SUMMARY")

    processed = metrics["emails_processed"]
    stored = metrics["emails_stored"]
    llm_calls = metrics["llm_calls"]
    llm_failures = metrics["llm_failures"]

    success_rate = (stored / processed * 100) if processed else 0
    llm_failure_rate = (llm_failures / llm_calls * 100) if llm_calls else 0

    print(f"Emails Seen: {metrics['emails_seen']}")
    print(f"Processed: {processed}")
    print(f"Stored: {stored}")
    print(f"Failed: {metrics['emails_failed']}")

    print(f"Success Rate: {success_rate:.2f}%")
    print(f"LLM Failure Rate: {llm_failure_rate:.2f}%")

    print("\n\n🎯 Pipeline completed successfully")




if __name__ == "__main__":

    try:
        main()
    except Exception as e:
        print(f"🛑 CRON FATAL ERROR → {e}")