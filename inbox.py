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

    # Decode HTML entities (&nbsp;, &zwnj;, &amp; ...)
    text = html.unescape(text)

    # Remove invisible / junk unicode characters
    text = JUNK_CHARS_REGEX.sub(" ", text)

    # Normalize line breaks
    text = re.sub(r"\r\n", "\n", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{2,}", "\n", text)

    # Collapse spaces & tabs
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
    html = ""

    def walk(part):
        nonlocal html
        if part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data")
            if data:
                html += decode_base64(data)

        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)

    if not html:
        return "", ""

    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(separator="\n", strip=True)

    return html, visible_text


def extract_image_urls_and_alt(html):
    if not html:
        return [], []

    soup = BeautifulSoup(html, "html.parser")
    urls, alts = [], []

    for img in soup.find_all("img"):
        urls.append(img.get("src") or "")
        alts.append(img.get("alt") or "")

    return urls, alts


def ocr_image_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("L")
        text = pytesseract.image_to_string(np.array(img))
        return normalize_ocr_text(text)
    except Exception:
        return ""


# =========================================================
# CORE FUNCTION — FINAL OUTPUT (STRING ONLY)
# =========================================================

def get_clean_email_text(message_id: str) -> str:
    service = get_gmail_service()

    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()

    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    sender = get_header(headers, "From")
    subject = get_header(headers, "Subject")
    date = get_header(headers, "Date")

    # -------- BODY TEXT --------
    plain_text = extract_plain_text(payload)
    html, visible_text = extract_visible_html_text(payload)

    body_text = normalize_text(
        "\n".join(t for t in [plain_text, visible_text] if t)
    )

    # -------- OCR TEXT --------
    image_urls, alt_texts = extract_image_urls_and_alt(html)
    ocr_blocks = []

    for url, alt in zip(image_urls, alt_texts):
        ocr_text = ocr_image_from_url(url) if url else ""
        if ocr_text.strip():
            ocr_blocks.append(
                f"[Image OCR Text]\n{ocr_text}\n[Image URL: {url}]"
            )

    # -------- FINAL TEXT --------
    header_block = "\n".join(
        line for line in [
            f"From: {sender}" if sender else "",
            f"Subject: {subject}" if subject else "",
            f"Date: {date}" if date else ""
        ] if line
    )

    final_text = (
        header_block
        + "\n\n--- EMAIL BODY ---\n\n"
        + body_text
    )

    if ocr_blocks:
        final_text += "\n\n--- IMAGE OCR TEXT ---\n\n" + "\n\n".join(ocr_blocks)

    return final_text.strip()


