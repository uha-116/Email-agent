import requests
import os
from dotenv import load_dotenv

from backend.error_handling import NetworkError, RateLimitError

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("BOT_CHAT_ID")


def send_telegram(message):

    # --------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing BOT_TOKEN or CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    # --------------------------------------------------
    # TRY REQUEST
    # --------------------------------------------------
    try:
        response = requests.post(
            url,
            json=payload,
            timeout=5   # 🔥 VERY IMPORTANT
        )

    # --------------------------------------------------
    # NETWORK ERRORS
    # --------------------------------------------------
    except requests.exceptions.Timeout:
        raise NetworkError("Telegram timeout")

    except requests.exceptions.ConnectionError:
        raise NetworkError("Telegram connection failed")

    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Telegram request failed: {e}")

    # --------------------------------------------------
    # RESPONSE STATUS HANDLING
    # --------------------------------------------------

    # ❌ RATE LIMIT
    if response.status_code == 429:
        raise RateLimitError("Telegram rate limit")

    # ❌ SERVER ERROR
    if response.status_code >= 500:
        raise NetworkError("Telegram server error")

    # ❌ BAD REQUEST (TOKEN / CHAT_ID / PAYLOAD)
    if response.status_code != 200:
        print(f"❌ Telegram API error: {response.status_code} | {response.text}")
        return

    # --------------------------------------------------
    # SAFE JSON PARSE
    # --------------------------------------------------
    try:
        data = response.json()
        print("✅ Telegram sent:", data.get("ok"))
    except Exception:
        print("⚠️ Telegram response not JSON")