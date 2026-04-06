from backend.db_storage.db_connection import get_db_connection
from backend.agent_services.telegram_notifier import send_telegram
from backend.error_handling import DBConnectionError, NetworkError, NetworkDownError


def notification_handle(result):

    insert_ids = result["opportunity_changes"]["INSERT"]
    update_ids = result["opportunity_changes"]["UPDATE"]

    linkedin_ids = result.get("linkedin_event_id", [])

    all_ids = insert_ids + update_ids

    if not all_ids and not linkedin_ids:
        return

    conn = None
    cur = None

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --------------------------------------------------
        # JOB PIPELINE QUERY
        # --------------------------------------------------
        rows = []
        if all_ids:
            query = """
            SELECT
                o.id,
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
        # LINKEDIN EVENTS QUERY (🔥 FIXED)
        # --------------------------------------------------
        linkedin_rows = []
        if linkedin_ids:
            linkedin_query = """
            SELECT
                id,
                person_name,
                person_company,
                interaction_type
            FROM linkedin_events
            WHERE id = ANY(%s);
            """
            cur.execute(linkedin_query, (linkedin_ids,))
            linkedin_rows = cur.fetchall()

    except (DBConnectionError, NetworkError, NetworkDownError) as e:
        print(f"❌ DB error in notification_engine: {e}")
        return

    except Exception as e:
        print(f"❌ Unexpected DB error: {e}")
        return

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

    if not rows and not linkedin_rows:
        return

    # --------------------------------------------------
    # Group records by pipeline stage
    # --------------------------------------------------

    pipeline_records = {}
    ids_to_update = []  # 🔥 FIX

    for opp_id, company, role, stage, deadline, event_date, gmail_id in rows:

        ids_to_update.append(opp_id)

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

        elif stage == "ASSESSMENT":

            for record in pipeline_records["ASSESSMENT"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"⚠ Assessment from {record['company']}\n"
                    f"Deadline: {record['deadline']}\n"
                    f"For more details: {link}"
                )

        elif stage == "INTERVIEW":

            for record in pipeline_records["INTERVIEW"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"📅 Interview with {record['company']}\n"
                    f"Date: {record['event_date']}\n"
                    f"For more details: {link}"
                )

        elif stage == "SELECTED":

            for record in pipeline_records["SELECTED"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"🎉 Congratulations! Selected by {record['company']}\n"
                    f"For more details: {link}"
                )

        elif stage == "REJECTED":

            for record in pipeline_records["REJECTED"]:

                link = f"https://mail.google.com/mail/u/0/#all/{record['gmail_id']}"

                messages.append(
                    f"Update from {record['company']} Application rejected\n"
                    f"For more details: {link}"
                )

    # --------------------------------------------------
    # 🔥 LINKEDIN NOTIFICATIONS (UPDATED AS PER YOUR DESIGN)
    # --------------------------------------------------

    for _, person_name, person_company, interaction_type in linkedin_rows:

        # Prefer company over person (your design)
        if person_company:
            base = f"{person_company} member"
        else:
            base = person_name or "LinkedIn user"

        if interaction_type == "MESSAGE_RECEIVED":
            msg = f"💬 Message from {base}"

        elif interaction_type == "CONNECTION_REQUEST":
            msg = f"🤝 Connection request from {base}"

        elif interaction_type == "CONNECTION_ACCEPTED":
            msg = f"✅ Connection accepted by {base}"

        else:
            msg = f"🔔 LinkedIn update from {base}"

        messages.append(msg)

    # --------------------------------------------------
    # Final Notification
    # --------------------------------------------------

    if messages:

        final_message = "\n\n".join(messages)

        if len(final_message) > 4000:
            final_message = final_message[:4000] + "\n...truncated"

        try:
            send_telegram(final_message)

            # 🔥 UPDATE last_notified_at (ONLY for opportunities)
            if ids_to_update:
                conn = get_db_connection()
                cur = conn.cursor()

                cur.execute(
                    """
                    UPDATE opportunities
                    SET last_notified_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                    """,
                    (ids_to_update,)
                )

                conn.commit()
                cur.close()
                conn.close()

        except NetworkError as e:
            print(f"⚠️ Telegram failed (1st try): {e}")

            try:
                send_telegram(final_message)
                print("✅ Telegram retry success")

            except Exception as retry_error:
                print(f"❌ Telegram retry failed: {retry_error}")

        except Exception as e:
            print(f"❌ Unexpected Telegram error: {e}")