# notification_engine.py
from backend.db_storage.db_connection import get_db_connection
from backend.agent_services.telegram_notifier import send_telegram
from backend.error_handling import DBConnectionError, NetworkError, NetworkDownError


def notification_handle(result):

    insert_ids = result["opportunity_changes"]["INSERT"]
    update_ids = result["opportunity_changes"]["UPDATE"]

    all_ids = insert_ids + update_ids

    if not all_ids:
        return

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
        SELECT
            o.company,
            o.role,
            o.pipeline_stage,
            o.deadline,
            o.event_date,
            e.gmail_message_id
        FROM opportunities o
        JOIN emails e
            ON o.email_id = e.id
        WHERE o.id = ANY(%s);
        """

        cur.execute(query, (all_ids,))
        rows = cur.fetchall()

    # --------------------------------------------------
    # EXPECTED DB ERRORS
    # --------------------------------------------------
    except (DBConnectionError, NetworkError, NetworkDownError) as e:
        print(f"❌ DB error in notification_engine: {e}")
        return

    # --------------------------------------------------
    # UNKNOWN ERRORS
    # --------------------------------------------------
    except Exception as e:
        print(f"❌ Unexpected DB error: {e}")
        return

    # --------------------------------------------------
    # CLEANUP (ALWAYS RUNS)
    # --------------------------------------------------
    finally:
        try:
            if cur:
                cur.close()
        except Exception:
            pass

        try:
            if conn:
                conn.close()
        except Exception:
            pass

    # --------------------------------------------------
    # EMPTY RESULT SAFETY
    # --------------------------------------------------
    if not rows:
        return

    # --------------------------------------------------
    # Group records by pipeline stage
    # --------------------------------------------------

    pipeline_records = {}

    for company, role, stage, deadline, event_date, gmail_id in rows:

        if stage not in pipeline_records:
            pipeline_records[stage] = []

        pipeline_records[stage].append({
            "company": company,
            "role": role,
            "deadline": deadline,
            "event_date": event_date,
            "gmail_id": gmail_id
        })

    # --------------------------------------------------
    # Build Notification Message
    # --------------------------------------------------

    messages = []

    # Priority order
    stage_priority = [
        "SELECTED",
        "INTERVIEW",
        "ASSESSMENT",
        "OPPORTUNITY_FOUND",
        "REJECTED"
    ]

    for stage in stage_priority:

        if stage not in pipeline_records:
            continue

        # --------------------------------------------------
        # Opportunities
        # --------------------------------------------------
        if stage == "OPPORTUNITY_FOUND":

            count = len(pipeline_records["OPPORTUNITY_FOUND"])

            messages.append(
                f"You got {count} new opportunities.\n"
                f"Check your email for more details."
            )

        # --------------------------------------------------
        # Assessments
        # --------------------------------------------------
        elif stage == "ASSESSMENT":

            for record in pipeline_records["ASSESSMENT"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"⚠ Assessment from {record['company']}\n"
                    f"Deadline: {record['deadline']}\n"
                    f"For more details: {link}"
                )

        # --------------------------------------------------
        # Interviews
        # --------------------------------------------------
        elif stage == "INTERVIEW":

            for record in pipeline_records["INTERVIEW"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"📅 Interview with {record['company']}\n"
                    f"Date: {record['event_date']}\n"
                    f"For more details: {link}"
                )

        # --------------------------------------------------
        # Selected
        # --------------------------------------------------
        elif stage == "SELECTED":

            for record in pipeline_records["SELECTED"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"🎉 Congratulations! Selected by {record['company']}\n"
                    f"For more details: {link}"
                )

        # --------------------------------------------------
        # Rejected
        # --------------------------------------------------
        elif stage == "REJECTED":

            for record in pipeline_records["REJECTED"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"Update from {record['company']} Application rejected\n"
                    f"For more details: {link}"
                )

    # --------------------------------------------------
    # Final Notification
    # --------------------------------------------------

    if messages:

        final_message = "\n\n".join(messages)

        # 🔥 Telegram message limit protection
        if len(final_message) > 4000:
            final_message = final_message[:4000] + "\n...truncated"

        try:
            send_telegram(final_message)

        except NetworkError as e:
            print(f"⚠️ Telegram failed (1st try): {e}")

            # 🔁 Retry once
            try:
                send_telegram(final_message)
                print("✅ Telegram retry success")

            except Exception as retry_error:
                print(f"❌ Telegram retry failed: {retry_error}")

        except Exception as e:
            print(f"❌ Unexpected Telegram error: {e}")


# --------------------------------------------------
# Test
# --------------------------------------------------

result = {
    'email_id': 497,
    'opportunity_changes': {
        'INSERT': [796, 797, 798, 618, 747, 534],
        'UPDATE': [655, 713]
    },
    'linkedin_event_id': None
}

notification_handle(result)