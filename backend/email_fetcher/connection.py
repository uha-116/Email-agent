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
    is_internet_available,
    RetryConfig
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

    raise TokenLoadError(
        "Invalid GMAIL_TOKEN format in environment. Please update the GitHub secret."
    )
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

@retry(config=RetryConfig.BACKGROUND)
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

    # --------------------------------------------------
    # 🔥 FAIL FAST IF NO VALID TOKEN (IMPORTANT)
    # --------------------------------------------------
    if not creds:
        raise TokenLoadError(
            "No valid Gmail token found. Configure GMAIL_TOKEN or run locally to authenticate."
        )

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

            # 🔥 HANDLE invalid_grant → FORCE RE-AUTH
            if "invalid_grant" in str(e).lower():
                print("⚠️ Token expired/revoked → Re-authentication required")

                # --------------------------------------------------
                # STEP A: DELETE OLD TOKEN
                # --------------------------------------------------
                try:
                    if os.path.exists(TOKEN_PATH):
                        os.remove(TOKEN_PATH)
                        print("🗑️ Old token deleted")
                except Exception as del_err:
                    print(f"⚠️ Failed to delete old token: {del_err}")

                # --------------------------------------------------
                # STEP B: TRIGGER LOGIN FLOW
                # --------------------------------------------------
                try:
                    from google_auth_oauthlib.flow import InstalledAppFlow

                    print("🌐 Opening browser for Gmail login...")

                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_PATH,
                        SCOPES
                    )

                    creds = flow.run_local_server(port=8080,   
                                                access_type='offline',     # 🔥 IMPORTANT
                                                prompt='consent'     )      # 🔥 VERY IMPORTANT)

                    # --------------------------------------------------
                    # STEP C: SAVE NEW TOKEN
                    # --------------------------------------------------
                    try:
                        with open(TOKEN_PATH, 'w') as token:
                            token.write(creds.to_json())
                        print("✅ New token saved after re-auth")
                    except Exception as save_err:
                        print(f"⚠️ Failed to save new token: {save_err}")

                except Exception as auth_err:
                    raise TokenLoadError(
                        f"Re-authentication failed: {auth_err}"
                    )

            else:
                # Existing behavior for other errors
                raise TokenLoadError(
                    f"Refresh failed — manual login required: {e}"
                )
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