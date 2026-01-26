import base64
import re
import requests
import pytesseract
import html
import numpy as np

from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

from Connection import get_gmail_service


# =========================================================
# HELPERS
# =========================================================

def decode_base64(data):
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def get_header(headers, name):
    return next(
        (h["value"] for h in headers if h["name"].lower() == name.lower()),
        ""
    )


# =========================================================
# NORMALIZATION
# =========================================================

JUNK_CHARS_REGEX = re.compile(r"[\ufeff\u2007\u200b\u200c\u200d\xa0͏]")

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = JUNK_CHARS_REGEX.sub(" ", text)
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    cleaned_lines = []
    prev = None
    for line in text.split("\n"):
        line = line.strip()
        if line and line != prev:
            cleaned_lines.append(line)
            prev = line

    return "\n".join(cleaned_lines).strip()


def normalize_ocr_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = JUNK_CHARS_REGEX.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


# =========================================================
# EXTRACTION
# =========================================================

def extract_plain_text(payload):
    text = ""

    def walk(part):
        nonlocal text
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                text += decode_base64(data)

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
                html_content += decode_base64(data)

        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)

    if not html_content:
        return "", ""

    soup = BeautifulSoup(html_content, "html.parser")
    visible_text = soup.get_text(separator="\n", strip=True)

    return html_content, visible_text


def extract_image_urls(html_content):
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    return [img.get("src") for img in soup.find_all("img") if img.get("src")]


def ocr_image_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("L")
        text = pytesseract.image_to_string(np.array(img))
        return normalize_ocr_text(text)
    except Exception:
        return ""

def looks_like_html(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r"<(html|body|div|table|style|head|meta)[\s>]", text, re.I))


# =========================================================
# CORE FUNCTION — FINAL OUTPUT
# =========================================================

def get_clean_email_text(message_id: str) -> dict:
    service = get_gmail_service()

    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    subject = get_header(headers, "Subject")
    date_str = get_header(headers, "Date")

    # -------- RECEIVED DATE --------
    received_at = None
    if date_str:
        received_at = datetime.fromtimestamp(
            email.utils.mktime_tz(email.utils.parsedate_tz(date_str))
        )

    # -------- BODY TEXT --------
    plain_text = extract_plain_text(payload)
    html_content, visible_text = extract_visible_html_text(payload)

    parts = []

    if plain_text and not looks_like_html(plain_text):
        parts.append(plain_text)

    if visible_text:
        parts.append(visible_text)

    body_text = normalize_text("\n".join(parts))

    # -------- OCR TEXT --------
    image_urls = extract_image_urls(html_content)
    ocr_texts = []

    for url in image_urls:
        text = ocr_image_from_url(url)
        if text:
            ocr_texts.append(text)

    ocr_texts = list(dict.fromkeys(ocr_texts))  # dedupe
    combined_ocr_text = "\n".join(ocr_texts).strip()

    # -------- FINAL RAW TEXT --------
    final_parts = []

    if combined_ocr_text:
        final_parts.append(
            "--- IMAGE OCR TEXT ---\n\n" + combined_ocr_text
        )

    header_block = "\n".join(
        line for line in [
            f"Subject: {subject}" if subject else "",
            f"Date: {date_str}" if date_str else ""
        ] if line
    )

    if header_block:
        final_parts.append(header_block)

    if body_text:
        final_parts.append("--- EMAIL BODY ---\n\n" + body_text)

    raw_text = "\n\n".join(final_parts).strip()

    # ✅ RETURN AS JSON (as requested)
    return {
        "gmail_message_id": msg["id"],
        "subject": subject,
        "received_at": received_at,
        "raw_text": raw_text
    }
