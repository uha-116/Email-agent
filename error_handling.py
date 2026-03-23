# =========================================================
# BASE ERROR
# =========================================================

class BaseAppError(Exception):
    retryable = False
    user_message = "Something went wrong"
    show_to_user = False

    def __init__(self, message=None):
        super().__init__(message or self.user_message)


# =========================================================
# RETRY DECORATOR
# =========================================================

def retry(max_attempts=2):
    def wrapper(func):
        def inner(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)

                except BaseAppError as e:

                    # 🔁 Retryable case
                    if e.retryable and attempt < max_attempts - 1:
                        print(f"🔁 Retry {attempt + 1}/{max_attempts} for {func.__name__} → {type(e).__name__}")
                        continue

                    # ❌ Final failure
                    print(f"❌ Failed in {func.__name__} → {type(e).__name__}: {e}")
                    raise e

        return inner
    return wrapper


# =========================================================
# CONNECTION ERRORS (GMAIL SETUP)
# =========================================================

class NetworkError(BaseAppError):
    retryable = True
    user_message = "Temporary network issue. Please try again later."
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
    retryable = True
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