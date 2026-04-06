# task_update.py
import os
import time
import requests
from dotenv import load_dotenv
from backend.db_storage.db_connection import get_db_connection
from backend.error_handling import DBConnectionError, NetworkError, NetworkDownError
from datetime import datetime

load_dotenv()



BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("BOT_CHAT_ID")

pending_questions = []
last_update_id = None
ACTIVE_SESSION = False



def build_gmail_link(gmail_message_id):
    if not gmail_message_id:
        return None
    return f"https://mail.google.com/mail/u/0/#all/{gmail_message_id}"

def build_reminder_text(company, stage, deadline=None, event_date=None):

    now = datetime.now()
    label = "assessment" if stage == "ASSESSMENT" else "interview"

    # --------------------------------------------------
    # ASSESSMENT
    # --------------------------------------------------
    if stage == "ASSESSMENT":

        if deadline:
            try:
                days = (deadline.date() - now.date()).days
            except:
                days = None  # ✅ FIX

            if days is None:
                return f"⚠️ Please check {company} {label} details"

            if days > 1:
                return f"⏳ {days} days left for {company} {label}"

            elif days == 1:
                return f"⚠️ Tomorrow is deadline for {company} {label}"

            elif days == 0:
                return f"🔥 Today is deadline for {company} {label}"

            else:  # days < 0
                return f"🚨 You missed {company} {label} deadline!"

        else:
            return f"⚠️ Please complete {company} {label} as soon as possible"

    # --------------------------------------------------
    # INTERVIEW
    # --------------------------------------------------
    elif stage == "INTERVIEW":

        if event_date:
            try:
                if isinstance(event_date, datetime):
                    parsed_date = event_date
                else:
                    parsed_date = datetime.fromisoformat(str(event_date))

                date_str = parsed_date.strftime('%Y-%m-%d')
                days = (parsed_date.date() - now.date()).days

            except:
                days = None  # ✅ FIX
                date_str = str(event_date)

            if days is None:
                return f"⚠️ Interview scheduled with {company} (check details)"

            if days > 1:
                return f"📅 Interview with {company} on {date_str}"

            elif days == 1:
                return f"⚠️ Interview tomorrow with {company} on {date_str}"

            elif days == 0:
                return f"🔥 Interview TODAY with {company} on {date_str}"

            else:  # days < 0
                return f"🚨 You missed interview with {company} on {date_str}"

        else:
            return f"⚠️ Interview scheduled with {company} (date not available)"

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------
    return f"⚠️ Please check update for {company}"

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
       SELECT DISTINCT ON (o.company, o.pipeline_stage)
            o.id,
            o.company,
            o.pipeline_stage,
            o.deadline,
            o.event_date,
            e.gmail_message_id   -- ✅ FROM emails table

        FROM opportunities o

        -- ✅ JOIN emails table
        LEFT JOIN emails e
        ON o.email_id = e.id

        WHERE o.action_required = TRUE

        -- ❌ REMOVED response_locked condition

        -- ✅ Prevent duplicate active questions
        AND NOT EXISTS (
            SELECT 1
            FROM notifications n
            WHERE n.opportunity_id = o.id
        )

        -- ✅ Cooldown logic (4 hours)
        AND (
            o.last_notified_at IS NULL
            OR o.last_notified_at < NOW() - INTERVAL '4 hours'
        )

        -- ✅ Only relevant stages
        AND o.pipeline_stage IN ('ASSESSMENT','INTERVIEW')

        -- ✅ Date filtering
        AND (
            -- Case 1: deadline exists
            (o.deadline IS NOT NULL AND o.deadline >= CURRENT_DATE)

            OR

            -- Case 2: event date exists
            (o.event_date IS NOT NULL AND o.event_date::date >= CURRENT_DATE)

            OR

            -- Case 3: NO deadline → use last_updated_at window
            (
                o.deadline IS NULL
                AND o.event_date IS NULL
                AND o.last_updated_at >= NOW() - INTERVAL '3 days'
            )

            or 
            --Case 4: Missed deadline/event_date within last 1 day 
            (
                (
                    o.deadline IS NOT NULL AND o.deadline < CURRENT_DATE AND o.deadline >= CURRENT_DATE - INTERVAL '1 day'
                )
                OR
                (
                    o.event_date IS NOT NULL AND o.event_date::date < CURRENT_DATE AND o.event_date::date >= CURRENT_DATE - INTERVAL '1 day'
                )
            )
        )

        ORDER BY
            o.company,
            o.pipeline_stage,
            o.deadline ASC NULLS LAST,
            o.event_date ASC NULLS LAST;
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
    pending_questions.clear() 

    print("\nLoaded pending confirmations\n")

    for opp_id, company, stage, deadline, event_date,gmail_id in rows:

        pending_questions.append({
            "id": opp_id,
            "company": company,
            "stage": stage,
            "deadline": deadline,
            "event_date": event_date,
            "gmail_id": gmail_id
        })

    send_next_question()


# --------------------------------------------------
# Send next question from queue
# --------------------------------------------------

def send_next_question():

    global ACTIVE_SESSION

    if not pending_questions:
        print("All confirmations completed.")
        ACTIVE_SESSION = False
        return

    question = pending_questions[0]

    send_confirmation(
        question["company"],
        question["stage"],
        question["id"],
        question["deadline"],
        question["event_date"],
        question["gmail_id"]
    )


# --------------------------------------------------
# Send Telegram confirmation message
# --------------------------------------------------

def send_confirmation(company, stage, opportunity_id, deadline=None, event_date=None, gmail_id=None):

    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing BOT_TOKEN or CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # -----------------------------
    # 🔥 1. SEND REMINDER MESSAGE
    # -----------------------------
    reminder_text = build_reminder_text(company, stage, deadline, event_date)

    gmail_link = build_gmail_link(gmail_id)

    if gmail_link:
        reminder_text += f"\n\n🔗 View Email: {gmail_link}"

    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": reminder_text
        }, timeout=5)
    except Exception as e:
        print(f"❌ Reminder send failed: {e}")

    # -----------------------------
    # 🔥 2. ORIGINAL ACTION MESSAGE (UNCHANGED LOGIC)
    # -----------------------------
    if stage == "ASSESSMENT":
        text = f"Did you complete {company} assessment?"
    elif stage == "INTERVIEW":
        text = f"Did you attend {company} interview?"
    else:
        text = f"Did you complete the process for {company}?"

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

    time.sleep(0.5) # Small delay to ensure reminder is sent first

    try:
        response = requests.post(url, json=payload, timeout=5)
        res_json = response.json()

        message_id = res_json.get("result", {}).get("message_id")

        print(f"Question sent for opportunity {opportunity_id}, message_id={message_id}")

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO notifications(opportunity_id, message_id)
            VALUES (%s, %s)
            ON CONFLICT (opportunity_id) DO NOTHING
            """,
            (opportunity_id, message_id)
        )

        cur.execute(
            """
            UPDATE opportunities
            SET last_notified_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (opportunity_id,)
        )

        conn.commit()
        cur.close()
        conn.close()

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

        keyboard = {"inline_keyboard": [keyboard_row]}

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

    answer_callback(callback_query["id"])

    if "_" not in callback_data:
        print("⚠️ Invalid callback data")
        return

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        opportunity_id = int(callback_data.split("_")[-1])

        # 🔥 Lock check (FIRST CLICK ONLY)
        cur.execute(
            """
            UPDATE opportunities
            SET response_locked = TRUE
            WHERE id = %s
            AND response_locked = FALSE
            """,
            (opportunity_id,)
        )

        if cur.rowcount == 0:
            print("⚠️ Already answered — ignoring click")
            return

        print("\nUser clicked:", callback_data)

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
                WHERE id = %s
                """,
                (opportunity_id,)
            )

            print("✔ Marked completed")

        # ---------------------------
        # IRRELEVANT
        # ---------------------------
        elif callback_data.startswith("remove_"):

            update_message_after_click(callback_query, "IRRELEVANT")

            cur.execute(
                "DELETE FROM opportunities WHERE id = %s",
                (opportunity_id,)
            )

            print("✖ Removed opportunity")

        # ---------------------------
        # NO
        # ---------------------------
        elif callback_data.startswith("pending_"):

            update_message_after_click(callback_query, "NO")

            cur.execute(
                """
                UPDATE opportunities
                SET last_notified_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (opportunity_id,)
            )

            print("⏳ Marked for reminder")

        # 🔥 Remove notification always after response
        cur.execute(
            "DELETE FROM notifications WHERE opportunity_id = %s",
            (opportunity_id,)
        )

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        print("Database error:", e)

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

    # ✅ REMOVE CURRENT QUESTION FROM QUEUE
    if pending_questions:
        pending_questions.pop(0)

    send_next_question()


# --------------------------------------------------
# Listen for Telegram button clicks
# --------------------------------------------------

def listen_for_responses():

    global last_update_id

    print("\nListening for Telegram responses...\n")

    start_time = time.time()

    while ACTIVE_SESSION:
        if time.time() - start_time > 900:  # 10 minutes max
            print("⏳ Cron timeout reached, exiting...")
            break

    # existing polling logic

        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

            if last_update_id:
                url += f"?offset={last_update_id + 1}"

            response = requests.get(url, timeout=5)
            data = response.json()

        except Exception as e:
            print(f"❌ Polling error: {e}")
            time.sleep(2)
            continue

        for update in data.get("result", []):
            last_update_id = update.get("update_id")

            if "callback_query" in update:
                handle_response(
                    update["callback_query"]["data"],
                    update["callback_query"]
                )

        time.sleep(1)


# --------------------------------------------------
# Run system
# --------------------------------------------------

if __name__ == "__main__":

    try:
        fetch_pending_confirmations()
        listen_for_responses()
    except Exception as e:
        print(f"❌ Task scheduler fatal error: {e}")