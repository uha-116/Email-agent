import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import requests
import socket

# --------------------------------------------------
# IMPORT CUSTOM EXCEPTIONS + RETRY
# --------------------------------------------------

from error_handling import (
    BaseAppError,
    retry,
    NetworkError,
    TokenRefreshError,
    TokenLoadError,
    OAuthLoginError,
    GmailServiceBuildError
)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOKEN_PATH = os.path.join(BASE_DIR, "config", "token.json")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "config", "credentials.json")


# --------------------------------------------------
# CORE FUNCTION (WITH RETRY)
# --------------------------------------------------

@retry(max_attempts=2)
def get_gmail_service():

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
            raise TokenLoadError(f"Failed to load token.json: {e}")

    # --------------------------------------------------
    # STEP 2: VALIDITY CHECK
    # --------------------------------------------------
    if not creds or not creds.valid:

        # --------------------------------------------------
        # STEP 3: REFRESH TOKEN
        # --------------------------------------------------
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())

            except (requests.exceptions.RequestException, socket.timeout) as e:
                raise NetworkError(f"Network error during token refresh: {e}")

            except Exception as e:
                raise TokenRefreshError(f"Token refresh failed: {e}")

        else:
            creds = None

        # --------------------------------------------------
        # STEP 4: LOGIN (ONLY if NO CREDS)
        # --------------------------------------------------
        if not creds:

            # 🔴 credentials.json missing → NON-RETRYABLE
            if not os.path.exists(CREDENTIALS_PATH):
                raise TokenLoadError("credentials.json not found")

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_PATH,
                    SCOPES
                )

            except Exception as e:
                raise TokenLoadError(f"Invalid credentials.json: {e}")

            try:
                creds = flow.run_local_server(port=8080)

            except OSError as e:
                raise OAuthLoginError(f"Port issue during OAuth login: {e}")

            except (requests.exceptions.RequestException, socket.timeout) as e:
                raise NetworkError(f"Network error during OAuth login: {e}")

            except Exception as e:
                raise OAuthLoginError(f"OAuth login failed: {e}")

        # --------------------------------------------------
        # STEP 5: SAVE TOKEN (NON-CRITICAL)
        # --------------------------------------------------
        try:
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())

        except Exception:
            # Non-critical — ignore
            pass

    # --------------------------------------------------
    # STEP 6: BUILD SERVICE
    # --------------------------------------------------
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service

    except (requests.exceptions.RequestException, socket.timeout) as e:
        raise NetworkError(f"Network error while building Gmail service: {e}")

    except Exception as e:
        raise GmailServiceBuildError(
            f"Failed to build Gmail service: {e}"
        )