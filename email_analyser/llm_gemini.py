import os
from google import genai
from dotenv import load_dotenv

from error_handling import (
    retry,
    NetworkError,
    RateLimitError,
    ServiceUnavailableError,
    AuthenticationError,
    LLMAPIError
)

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# Validate API KEY (fail fast)
# --------------------------------------------------
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    raise AuthenticationError("GOOGLE_API_KEY not found in environment")

# --------------------------------------------------
# Initialize Gemini Client
# --------------------------------------------------
client = genai.Client(api_key=API_KEY)


# --------------------------------------------------
# Generic LLM Caller (WITH RETRY)
# --------------------------------------------------
@retry(max_attempts=2)
def call_llm(prompt: str, model: str, temp: float = 0) -> str:
    """
    Generic Gemini LLM caller with retry support.
    """

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "temperature": temp,
                "max_output_tokens": 10000
            }
        )

        # -----------------------------
        # EMPTY RESPONSE CHECK
        # -----------------------------
        if not response or not getattr(response, "text", None):
            raise LLMAPIError("Empty response from LLM")

        return response.text

    except Exception as e:

        msg = str(e).lower()

        # -----------------------------
        # RATE LIMIT / QUOTA
        # -----------------------------
        if "quota" in msg or "limit" in msg:
            raise RateLimitError("LLM quota or rate limit exceeded")

        # -----------------------------
        # AUTHENTICATION ERROR
        # -----------------------------
        if "api key" in msg or "permission" in msg or "unauthorized" in msg:
            raise AuthenticationError("Invalid or missing API key")

        # -----------------------------
        # NETWORK ERROR
        # -----------------------------
        if "timeout" in msg or "connection" in msg:
            raise NetworkError(f"LLM network error: {e}")

        # -----------------------------
        # SERVICE DOWN / SERVER ERROR
        # -----------------------------
        if "500" in msg or "503" in msg or "unavailable" in msg:
            raise ServiceUnavailableError("LLM service unavailable")

        # -----------------------------
        # UNKNOWN ERROR
        # -----------------------------
        raise LLMAPIError(f"LLM API failed: {e}")