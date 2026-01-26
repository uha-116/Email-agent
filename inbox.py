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

