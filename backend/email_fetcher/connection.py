import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import requests
import socket

from backend.error_handling import (
    retry,
    NetworkError,
    NetworkDownError,   # 🔥 NEW
    TokenLoadError,
    GmailServiceBuildError,
    is_internet_available   # 🔥 NEW
)

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOKEN_PATH = os.path.join(BASE_DIR, "config", "token.json")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "config", "credentials.json")


# =========================================================
# INTERNAL LOGIN HELPER (RETRYABLE LOGIN FLOW)
# =========================================================

def perform_login():

    if not os.path.exists(CREDENTIALS_PATH):
        raise TokenLoadError("credentials.json not found")

    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_PATH,
        SCOPES
    )

    print("\n🔐 Gmail authentication required")
    print("👉 Opening browser for login...\n")

    try:
        creds = flow.run_local_server(
            port=8080,
            access_type='offline',
            prompt='consent'
        )
        return creds

    except OSError:
        print("\n⚠️ Browser failed → switching to console login\n")
        creds = flow.run_console(
            access_type='offline',
            prompt='consent'
        )
        return creds


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
    # STEP 1: LOAD TOKEN
    # --------------------------------------------------
    if os.path.exists(TOKEN_PATH):
        try:
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

            # 🔥 HARD NETWORK FAILURE
            if (
                "getaddrinfo failed" in msg
                or "name or service not known" in msg
            ):
                raise NetworkDownError()

            raise NetworkError(f"Network error during refresh: {e}")

        except Exception as e:
            print(f"⚠️ Refresh failed → removing token: {e}")
            try:
                os.remove(TOKEN_PATH)
            except Exception:
                pass
            creds = None

    else:
        creds = None

    # --------------------------------------------------
    # STEP 3: LOGIN (WITH INTERNAL RETRY)
    # --------------------------------------------------
    if not creds:

        for attempt in range(2):
            try:
                creds = perform_login()
                break

            except (requests.exceptions.RequestException, socket.timeout) as e:

                msg = str(e).lower()

                # 🔥 HARD NETWORK FAILURE
                if (
                    "getaddrinfo failed" in msg
                    or "name or service not known" in msg
                ):
                    raise NetworkDownError()

                raise NetworkError(f"Network error during OAuth login: {e}")

            except Exception as e:
                print(f"⚠️ Login attempt {attempt+1} failed: {e}")

                try:
                    os.remove(TOKEN_PATH)
                except Exception:
                    pass

                if attempt == 1:
                    raise TokenLoadError("OAuth login failed after retries")

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

        # 🔥 HARD NETWORK FAILURE
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