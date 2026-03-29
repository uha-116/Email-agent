# task_update.py
import os
import time
import requests
from dotenv import load_dotenv
from backend.db_storage.db_connection import get_db_connection
from backend.error_handling import DBConnectionError, NetworkError, NetworkDownError

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("BOT_CHAT_ID")

pending_questions = []
last_update_id = None
ACTIVE_SESSION = False


# --------------------------------------------------
# 🔥 ACK TELEGRAM CALLBACK
# --------------------------------------------------

def answer_callback(callback_query_id):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_query_id}, timeout=5)
    except Exception as e:
        print(f"⚠️ Failed to ACK callback: {e}")


# --------------------------------------------------
# Fetch pending confirmations from DB
# --------------------------------------------------

def fetch_pending_confirmations():

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
        SELECT DISTINCT ON (company, pipeline_stage)
            id,
            company,
            pipeline_stage,
            deadline,
            event_date
        FROM opportunities
        WHERE action_required = TRUE
        AND pipeline_stage IN ('ASSESSMENT','INTERVIEW')
        AND (
            (deadline IS NOT NULL AND deadline >= CURRENT_DATE)
            OR (event_date IS NOT NULL AND event_date::date >= CURRENT_DATE)
        )
        ORDER BY company,pipeline_stage, deadline DESC NULLS LAST, event_date DESC NULLS LAST;
        """

        cur.execute(query)
        rows = cur.fetchall()

    except (DBConnectionError, NetworkError, NetworkDownError) as e:
        print(f"❌ DB error in fetch_pending_confirmations: {e}")
        return

    except Exception as e:
        print(f"❌ Unexpected DB error: {e}")
        return

    finally:
        try:
            if cur:
                cur.close()
        except:
            pass
        try:
            if conn:
                conn.close()
        except:
            pass

    global ACTIVE_SESSION

    if not rows:
        print("No pending confirmations.")
        ACTIVE_SESSION = False
        return

    ACTIVE_SESSION = True

    print("\nLoaded pending confirmations\n")

    for opp_id, company, stage, deadline, event_date in rows:

        pending_questions.append({
            "id": opp_id,
            "company": company,
            "stage": stage,
            "deadline": deadline,
            "event_date": event_date
        })

    send_next_question()


# --------------------------------------------------
# Send next question from queue
# --------------------------------------------------

def send_next_question():

    global ACTIVE_SESSION

    if not pending_questions:
        print("All confirmations completed.")
        ACTIVE_SESSION = False   # 🔥 STOP SESSION
        return

    question = pending_questions[0]

    send_confirmation(
        question["company"],
        question["stage"],
        question["id"],
        question["deadline"],
        question["event_date"]
    )


# --------------------------------------------------
# Send Telegram confirmation message
# --------------------------------------------------

def send_confirmation(company, stage, opportunity_id, deadline=None, event_date=None):

    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing BOT_TOKEN or CHAT_ID")
        return

    if stage == "ASSESSMENT":
        text = f"Did you complete {company} assessment?\nDeadline: {deadline}"

    elif stage == "INTERVIEW":
        text = f"Did you attend {company} interview?\nDate: {event_date}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "YES", "callback_data": f"confirm_{opportunity_id}"},
                {"text": "NO", "callback_data": f"pending_{opportunity_id}"},
                {"text": "IRRELEVANT", "callback_data": f"remove_{opportunity_id}"}
            ]
        ]
    }

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "reply_markup": keyboard
    }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, json=payload, timeout=5)
        print(f"Question sent for opportunity {opportunity_id}")

    except requests.exceptions.Timeout:
        print("⚠️ Telegram timeout")

    except requests.exceptions.ConnectionError:
        print("⚠️ Telegram connection failed")

    except Exception as e:
        print(f"❌ Telegram error: {e}")


# --------------------------------------------------
# Update Telegram message after click
# --------------------------------------------------

def update_message_after_click(callback_query, choice):

    try:
        chat_id = callback_query["message"]["chat"]["id"]
        message_id = callback_query["message"]["message_id"]

        options = ["YES", "NO", "IRRELEVANT"]
        keyboard_row = []

        for opt in options:
            if opt == choice:
                text = f"✔ {opt}"
            else:
                text = opt

            keyboard_row.append({
                "text": text,
                "callback_data": "done"
            })

        keyboard = {
            "inline_keyboard": [keyboard_row]
        }

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup"

        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": keyboard
        }

        requests.post(url, json=payload, timeout=5)

    except Exception as e:
        print(f"⚠️ Failed to update message UI: {e}")


# --------------------------------------------------
# Handle user response
# --------------------------------------------------

def handle_response(callback_data, callback_query):

    if not pending_questions:
        return

    # 🔥 ACK telegram immediately
    answer_callback(callback_query["id"])

    # 🔥 Safety for invalid callback
    if "_" not in callback_data:
        print("⚠️ Invalid callback data")
        return

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 🔥 Extract ID
        opportunity_id = int(callback_data.split("_")[-1])

        # 🔥 Fetch correct record
        cur.execute(
            """
            SELECT company, pipeline_stage
            FROM opportunities
            WHERE id = %s
            """,
            (opportunity_id,)
        )

        row = cur.fetchone()

        if not row:
            print("⚠️ Opportunity not found or already handled")
            return

        company, stage = row

        # 🔥 Remove from queue safely
        pending_questions[:] = [
            q for q in pending_questions if q["id"] != opportunity_id
        ]

        print("\nUser clicked:", callback_data)
        print("Company:", company)
        print("Stage:", stage)

        # ---------------------------
        # YES
        # ---------------------------
        if callback_data.startswith("confirm_"):

            update_message_after_click(callback_query, "YES")

            cur.execute(
                """
                UPDATE opportunities
                SET action_required = FALSE,
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE company = %s
                AND pipeline_stage = %s
                AND action_required = TRUE
                """,
                (company, stage)
            )

            if cur.rowcount == 0:
                print("⚠️ Duplicate click ignored — already processed")
                return

            print("✔ Marked all matching opportunities as completed")

        # ---------------------------
        # IRRELEVANT
        # ---------------------------
        elif callback_data.startswith("remove_"):

            update_message_after_click(callback_query, "IRRELEVANT")

            cur.execute(
                """
                DELETE FROM opportunities
                WHERE company = %s
                AND pipeline_stage = %s
                AND action_required = TRUE
                """,
                (company, stage)
            )

            if cur.rowcount == 0:
                print("⚠️ Already removed / duplicate click")
                return

            print("✖ Removed incorrect opportunity records")

        # ---------------------------
        # NO (your logic preserved)
        # ---------------------------
        elif callback_data.startswith("pending_"):

            update_message_after_click(callback_query, "NO")

            cur.execute(
                """
                UPDATE opportunities
                SET last_updated_at = CURRENT_TIMESTAMP
                WHERE company = %s
                AND pipeline_stage = %s
                AND action_required = TRUE
                """,
                (company, stage)
            )

            if cur.rowcount == 0:
                print("⚠️ Duplicate NO click ignored")
                return

            print("⏳ Still pending — timestamp refreshed")

        conn.commit()

    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except:
            pass
        print("Database error:", e)

    finally:
        try:
            if cur:
                cur.close()
        except:
            pass
        try:
            if conn:
                conn.close()
        except:
            pass

    send_next_question()


# --------------------------------------------------
# Listen for Telegram button clicks
# --------------------------------------------------

def listen_for_responses():

    global last_update_id

    print("\nListening for Telegram responses...\n")

    while ACTIVE_SESSION:

        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

            if last_update_id:
                url += f"?offset={last_update_id + 1}"

            response = requests.get(url, timeout=5)
            data = response.json()

        except requests.exceptions.Timeout:
            print("⚠️ Telegram polling timeout")
            time.sleep(2)
            continue

        except requests.exceptions.ConnectionError:
            print("⚠️ Telegram polling connection error")
            time.sleep(2)
            continue

        except Exception as e:
            print(f"❌ Polling error: {e}")
            time.sleep(2)
            continue

        for update in data.get("result", []):

            last_update_id = update.get("update_id")

            if "callback_query" in update:
                try:
                    cb_data = update["callback_query"]["data"]
                    handle_response(cb_data, update["callback_query"])
                except Exception as e:
                    print(f"❌ Callback handling error: {e}")

        time.sleep(1)


# --------------------------------------------------
# Run system
# --------------------------------------------------

if __name__ == "__main__":

    fetch_pending_confirmations()
    listen_for_responses()