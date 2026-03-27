# task_update.py
import os
import time
import requests
from dotenv import load_dotenv
from db_storage.db_connection import get_db_connection
from error_handling import DBConnectionError, NetworkError, NetworkDownError

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("BOT_CHAT_ID")

# --------------------------------------------------
# Queue to hold pending questions
# --------------------------------------------------

pending_questions = []
last_update_id = None


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
            deadline <= CURRENT_DATE
            OR event_date::date <= CURRENT_DATE
        )
        ORDER BY company, deadline DESC NULLS LAST, event_date DESC NULLS LAST;
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

    if not rows:
        print("No pending confirmations.")
        return

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

    if not pending_questions:
        print("All confirmations completed.")
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
# Handle user response
# --------------------------------------------------

def handle_response(callback_data):

    if not pending_questions:
        return

    current_question = pending_questions.pop(0)

    company = current_question["company"]
    stage = current_question["stage"]

    print("\nUser clicked:", callback_data)
    print("Company:", company)
    print("Stage:", stage)

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if callback_data.startswith("confirm_"):

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

            print("✔ Marked all matching opportunities as completed")

        elif callback_data.startswith("remove_"):

            cur.execute(
                """
                DELETE FROM opportunities
                WHERE company = %s
                AND pipeline_stage = %s
                AND action_required = TRUE
                """,
                (company, stage)
            )

            print("✖ Removed incorrect opportunity records")

        elif callback_data.startswith("pending_"):

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

    while True:

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
                    handle_response(cb_data)
                except Exception as e:
                    print(f"❌ Callback handling error: {e}")

        time.sleep(1)


# --------------------------------------------------
# Run system
# --------------------------------------------------

if __name__ == "__main__":

    fetch_pending_confirmations()

    listen_for_responses()