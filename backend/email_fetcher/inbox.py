import base64
import re
import requests
import pytesseract
import html
import numpy as np
import email.utils

from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from datetime import datetime

from googleapiclient.errors import HttpError

from backend.error_handling import (
    retry,
    NetworkError,
    GmailFetchError,
    MessageNotFoundError,
    Base64DecodeError,
    NetworkDownError
)

# =========================================================
# HELPERS
# =========================================================

def decode_base64(data):
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    except Exception as e:
        raise Base64DecodeError(f"Base64 decode failed: {e}")


def get_header(headers, name):
    return next(
        (h["value"] for h in headers if h["name"].lower() == name.lower()),
        ""
    )

# =========================================================
# TEXT EXTRACTION
# =========================================================

def extract_plain_text(payload):
    text = ""

    def walk(part):
        nonlocal text
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                try:
                    text += decode_base64(data)
                except Base64DecodeError:
                    return

        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    return text


def extract_visible_html_text(payload):
    html_content = ""

    def walk(part):
        nonlocal html_content
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data")
            if data:
                try:
                    html_content += decode_base64(data)
                except Base64DecodeError:
                    return

        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)

    if not html_content:
        return "", ""

    soup = BeautifulSoup(html_content, "html.parser")
    visible_text = soup.get_text(separator="\n", strip=True)

    return html_content, visible_text


# =========================================================
# CORE FUNCTION (WITH RETRY)
# =========================================================

@retry(max_attempts=2)
def get_clean_email_text(service, message_id: str) -> dict:

    # --------------------------------------------------
    # STEP 1: FETCH EMAIL FROM GMAIL
    # --------------------------------------------------
    try:
        msg = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

    except HttpError as e:

        status = e.resp.status
        error_msg = str(e).lower()

        # ❌ Permanent error
        if status == 404:
            raise MessageNotFoundError(f"Message not found: {message_id}")

        # ✅ Retryable
        elif status == 429:
            raise NetworkError("Rate limit exceeded")

        elif status in (500, 503):
            raise NetworkError("Gmail server error")

        # ⚠️ Conditional
        elif status == 403:
            if "rate limit" in error_msg:
                raise NetworkError("Rate limit exceeded")
            else:
                raise GmailFetchError("Permission or access issue")

        # ❌ Unknown Gmail error
        else:
            raise GmailFetchError(f"Gmail API error: {e}")

    except Exception as e:

        error_str = str(e).lower()

        # 🔥 HARD NETWORK FAILURE (NO INTERNET)
        if (
            "getaddrinfo failed" in error_str
            or "name or service not known" in error_str
            or "temporary failure in name resolution" in error_str
        ):
            raise NetworkDownError(f"Gmail DNS/network failure: {e}")

        # ✅ Retryable network issues
        if "timed out" in error_str or "connection" in error_str:
            raise NetworkError(f"Gmail fetch network error: {e}")

        # ❌ Other failures
        raise GmailFetchError(f"Failed to fetch message {message_id}: {e}")
        
    # --------------------------------------------------
    # STEP 2: VALIDATE PAYLOAD
    # --------------------------------------------------
    payload = msg.get("payload", {})
    if not payload:
        raise GmailFetchError("Empty payload received from Gmail")

    headers = payload.get("headers", [])

    subject = get_header(headers, "Subject")
    date_str = get_header(headers, "Date")

    # --------------------------------------------------
    # STEP 3: SAFE DATE PARSING
    # --------------------------------------------------
    received_at = None
    if date_str:
        try:
            received_at = datetime.fromtimestamp(
                email.utils.mktime_tz(email.utils.parsedate_tz(date_str))
            )
        except Exception:
            received_at = None

    # --------------------------------------------------
    # STEP 4: EXTRACT TEXT
    # --------------------------------------------------
    plain_text = extract_plain_text(payload)
    html_content, visible_text = extract_visible_html_text(payload)

    parts = []

    if plain_text:
        parts.append(plain_text)

    if visible_text:
        parts.append(visible_text)

    body_text = "\n".join(parts).strip()

    # --------------------------------------------------
    # STEP 5: FINAL RESPONSE
    # --------------------------------------------------
    return {
        "gmail_message_id": msg["id"],
        "subject": subject,
        "received_at": received_at,
        "raw_text": body_text
    }

# =========================================================
# JOB CONFIDENCE SCORING
# =========================================================

STRONG_JOB_KEYWORDS = [
    "application", "applied", "shortlisted", "shortlist",
    "assessment", "test", "coding", "interview", "offer",
    "offer letter", "selected", "selection", "onboarding",
    "joining", "hiring", "recruitment", "candidate portal",
    "ctc", "messaged", "accepted", "connect", "messages",
    "opportunity", "intern", "confirmation", "submit",
    "stipend", "opportunities", "technical assessment",
    "moving forward", "proceeding","awaits","await","Linkedin"
]

MEDIUM_JOB_KEYWORDS = [
    "schedule", "complete", "interest", "congratulations",
    "eligible", "duration","messaged","response"
]

NEGATION = [
    "reddit", "hireready", "session", "challenge",
    "webinar", "newsletter", "event", "survey",
    "r/btechtards", "comments", "upvotes", "prizes",
    "competition", "certificates", "news", "courses",
    "post", "suhas", "register", "like","competitions"
]


def compute_job_confidence(text: str) -> float:
    """
    Returns confidence score between 0.0 and 1.0
    """
    if not text:
        return 0.0

    text = text.lower()
    score = 0.0

    STRONG_WEIGHT = 0.25
    MEDIUM_WEIGHT = 0.10
    NEG_WEIGHT = 0.10

    for kw in STRONG_JOB_KEYWORDS:
        if kw in text:
            score += STRONG_WEIGHT

    for kw in MEDIUM_JOB_KEYWORDS:
        if kw in text:
            score += MEDIUM_WEIGHT

    for kw in NEGATION:
        if kw in text:
            score -= NEG_WEIGHT

    return min(score, 1.0)