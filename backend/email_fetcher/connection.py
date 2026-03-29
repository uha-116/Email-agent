import os
import json

from dotenv import load_dotenv  # 🔥 NEW

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import requests
import socket

from backend.error_handling import (
    retry,
    NetworkError,
    NetworkDownError,
    TokenLoadError,
    GmailServiceBuildError,
    is_internet_available
)

# =========================================================
# 🔥 LOAD ENV VARIABLES ONCE (GLOBAL)
# =========================================================
load_dotenv()

TOKEN_ENV = os.getenv("GMAIL_TOKEN")
CREDENTIALS_ENV = os.getenv("GMAIL_CREDENTIALS")

# Parse JSON once (safe)
PARSED_TOKEN = None
PARSED_CREDENTIALS = None

try:
    if TOKEN_ENV:
        PARSED_TOKEN = json.loads(TOKEN_ENV)
except Exception as e:
    print(f"⚠️ Failed to parse GMAIL_TOKEN → {e}")

try:
    if CREDENTIALS_ENV:
        PARSED_CREDENTIALS = json.loads(CREDENTIALS_ENV)
except Exception as e:
    print(f"⚠️ Failed to parse GMAIL_CREDENTIALS → {e}")


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOKEN_PATH = os.path.join(BASE_DIR, "config", "token.json")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "config", "credentials.json")


# =========================================================
# MAIN FUNCTION
# =========================================================

@retry(max_attempts=2)
def get_gmail_service():

    # 🔥 FAIL FAST CHECK
    if not is_internet_available():
        raise NetworkDownError()

    creds = None

    # --------------------------------------------------
    # STEP 1: LOAD TOKEN (ENV → fallback to file)
    # --------------------------------------------------
    if PARSED_TOKEN:
        try:
            print("🔐 Loading token from ENV")
            creds = Credentials.from_authorized_user_info(
                PARSED_TOKEN,
                SCOPES
            )
        except Exception as e:
            print(f"⚠️ Invalid ENV token → {e}")
            creds = None

    elif os.path.exists(TOKEN_PATH):
        try:
            print("📂 Loading token from file")
            creds = Credentials.from_authorized_user_file(
                TOKEN_PATH,
                SCOPES
            )

        except Exception as e:
            print(f"⚠️ Corrupted token → removing: {e}")
            try:
                os.remove(TOKEN_PATH)
            except Exception:
                pass
            creds = None

    else:
        creds = None

    # --------------------------------------------------
    # STEP 2: VALIDATE / REFRESH
    # --------------------------------------------------
    if creds and creds.valid:
        pass

    elif creds and creds.expired and creds.refresh_token:
        try:
            print("🔄 Refreshing token...")
            creds.refresh(Request())

        except (requests.exceptions.RequestException, socket.timeout) as e:

            msg = str(e).lower()

            if (
                "getaddrinfo failed" in msg
                or "name or service not known" in msg
            ):
                raise NetworkDownError()

            raise NetworkError(f"Network error during refresh: {e}")

        except Exception as e:
            print(f"❌ Refresh failed: {e}")
            raise TokenLoadError(
                f"Refresh failed — manual login required: {e}"
            )

    else:
        creds = None

    # --------------------------------------------------
    # STEP 3: NO LOGIN IN PRODUCTION
    # --------------------------------------------------
    if not creds:
        print("❌ No valid credentials available")
        raise TokenLoadError(
            "No valid credentials — login required locally"
        )

    # --------------------------------------------------
    # STEP 4: SAVE TOKEN
    # --------------------------------------------------
    try:
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        print("✅ Token saved")

    except Exception:
        print("⚠️ Failed to save token (non-critical)")

    # --------------------------------------------------
    # STEP 5: BUILD SERVICE
    # --------------------------------------------------
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service

    except (requests.exceptions.RequestException, socket.timeout) as e:

        msg = str(e).lower()

        if (
            "getaddrinfo failed" in msg
            or "name or service not known" in msg
        ):
            raise NetworkDownError()

        raise NetworkError(f"Network error while building Gmail service: {e}")

    except Exception as e:
        raise GmailServiceBuildError(
            f"Failed to build Gmail service: {e}"
        )