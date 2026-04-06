class RetryConfig:
    BACKGROUND = {
        "max_attempts": 2,
        "base_delay": 2,
        "max_delay": 10
    }

    FOREGROUND = {
        "max_attempts": 1,   # 🔥 fail fast
        "base_delay": 0,
        "max_delay": 0
    }


# =========================================================
# BASE ERROR
# =========================================================

import socket

class BaseAppError(Exception):
    retryable = False
    user_message = "Something went wrong"
    show_to_user = False

    def __init__(self, message=None):
        super().__init__(message or self.user_message)


# =========================================================
# RETRY DECORATOR (UPDATED ONLY THIS)
# =========================================================

import time
import random

def retry(config=None, max_attempts=2, base_delay=2, max_delay=10):
    def wrapper(func):
        def inner(*args, **kwargs):

            # 🔥 Resolve config
            if config:
                max_attempts_local = config.get("max_attempts", 1)
                base_delay_local = config.get("base_delay", 0)
                max_delay_local = config.get("max_delay", 0)
            else:
                max_attempts_local = max_attempts
                base_delay_local = base_delay
                max_delay_local = max_delay

            for attempt in range(max_attempts_local):
                try:
                    return func(*args, **kwargs)

                except BaseAppError as e:

                    # ❌ Non-retryable → fail immediately
                    if not e.retryable:
                        print(f"❌ Non-retryable error in {func.__name__} → {type(e).__name__}: {e}")
                        raise e

                    # ⚡ Fail-fast (foreground)
                    if max_attempts_local == 1:
                        print(f"⚡ Fail-fast → {func.__name__} → {type(e).__name__}: {e}")
                        raise e

                    # 🔁 Retry with backoff
                    if attempt < max_attempts_local - 1:

                        delay = min(base_delay_local * (2 ** attempt), max_delay_local)
                        jitter = random.uniform(0, 1)

                        sleep_time = delay + jitter

                        print(
                            f"🔁 Retry {attempt + 1}/{max_attempts_local} | "
                            f"{func.__name__} | "
                            f"{type(e).__name__} | "
                            f"sleep={sleep_time:.2f}s"
                        )

                        time.sleep(sleep_time)
                        continue

                    # ❌ Final failure
                    print(f"❌ Failed after {max_attempts_local} attempts → {type(e).__name__}: {e}")
                    raise e

        return inner
    return wrapper


def is_internet_available():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except:
        return False


# =========================================================
# CONNECTION ERRORS (GMAIL SETUP)
# =========================================================

class NetworkError(BaseAppError):
    retryable = True
    user_message = "Temporary network issue. Please try again later."
    show_to_user = True


class NetworkDownError(BaseAppError):
    retryable = False
    user_message = "Please Connect to the internet"
    show_to_user = True


class TokenRefreshError(BaseAppError):
    retryable = True
    user_message = "Session expired. Retrying authentication..."
    show_to_user = False   # internal retry handled


class TokenLoadError(BaseAppError):
    retryable = False
    user_message = "Gmail configuration missing or invalid. Please reconnect your account."
    show_to_user = True


class OAuthLoginError(BaseAppError):
    retryable = False
    user_message = "Gmail login failed. Please try reconnecting your account."
    show_to_user = True


class GmailServiceBuildError(BaseAppError):
    retryable = True
    user_message = "Unable to connect to Gmail service. Please try again later."
    show_to_user = True


# =========================================================
# INBOX ERRORS (EMAIL FETCHING)
# =========================================================

class GmailFetchError(BaseAppError):
    retryable = True
    user_message = "Unable to fetch emails at the moment. Retrying..."
    show_to_user = False   # handled silently


class MessageNotFoundError(BaseAppError):
    retryable = False
    user_message = "Email not found or may have been deleted."
    show_to_user = False   # user doesn't need to see per-email issues


class Base64DecodeError(BaseAppError):
    retryable = False
    user_message = "Failed to process email content."
    show_to_user = False   # internal parsing issue


# =========================================================
# LLM ERRORS (EMAIL ANALYSIS)
# =========================================================

class RateLimitError(BaseAppError):
    retryable = True
    user_message = "System is busy. Please try again shortly."
    show_to_user = True


class ServiceUnavailableError(BaseAppError):
    retryable = False
    user_message = "AI service is temporarily unavailable. Please try again later."
    show_to_user = True


class AuthenticationError(BaseAppError):
    retryable = False
    user_message = "AI service authentication failed. Please contact support."
    show_to_user = True


class LLMAPIError(BaseAppError):
    retryable = True
    user_message = "Error communicating with AI service. Retrying..."
    show_to_user = False


class LLMValidationError(BaseAppError):
    retryable = True
    user_message = "Processing issue occurred. Retrying..."
    show_to_user = False


class LLMOutputFormatError(BaseAppError):
    retryable = True
    user_message = "Temporary processing issue. Retrying..."
    show_to_user = False


# =========================================================
# DB ERRORS
# =========================================================

class DBConnectionError(BaseAppError):
    retryable = True
    user_message = "Database temporarily unavailable. Please try again later."
    show_to_user = False