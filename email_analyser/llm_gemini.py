import os
import concurrent.futures
from dotenv import load_dotenv
from google import genai

from error_handling import (
    retry,
    NetworkError,
    RateLimitError,
    ServiceUnavailableError,
    AuthenticationError,
    LLMAPIError,
    NetworkDownError
)

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    raise AuthenticationError("GOOGLE_API_KEY not found in environment")


# --------------------------------------------------
# 🔥 INTERNAL: RUN INSIDE PROCESS (VERY IMPORTANT)
# --------------------------------------------------
def _generate_content(prompt: str, model: str, temp: float, api_key: str):
    print("   [Child] Starting Gemini call")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "temperature": temp,
            "max_output_tokens": 10000
        }
    )

    print("   [Child] Gemini call finished")

    return response


# --------------------------------------------------
# 🔥 GENERIC LLM CALLER WITH TIMEOUT + RETRY
# --------------------------------------------------
@retry(max_attempts=2)
def call_llm(prompt: str, model: str, temp: float = 0) -> str:

    TIMEOUT_SECONDS = 15

    print("\n➡️ Entered call_llm")

    executor = None

    try:
        print("➡️ Creating process pool")

        executor = concurrent.futures.ProcessPoolExecutor(max_workers=1)

        print("➡️ Submitting LLM task")

        future = executor.submit(
            _generate_content,
            prompt,
            model,
            temp,
            API_KEY
        )

        try:
            print("⏳ Waiting for result...")
            response = future.result(timeout=TIMEOUT_SECONDS)
            print("✅ Got response from LLM")

        except concurrent.futures.TimeoutError:
            print("⏱ TIMEOUT → force killing process")

            # 🔥 CRITICAL FIX
            executor.shutdown(wait=False, cancel_futures=True)

            raise NetworkError("LLM request timed out")

        # --------------------------------------------------
        # EMPTY RESPONSE CHECK
        # --------------------------------------------------
        if not response or not getattr(response, "text", None):
            print("❌ Empty response detected")
            raise LLMAPIError("Empty response from LLM")

        print("✅ Returning response text")

        return response.text

    except Exception as e:

        print(f"❌ Exception caught: {e}")

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
        # NETWORK ERROR (IMPORTANT FIX)
        # -----------------------------
        if (
            "getaddrinfo failed" in msg   # 🔥 DNS failure (NO INTERNET)
            or "name or service not known" in msg
            or "temporary failure in name resolution" in msg
        ):
            raise NetworkDownError(f"DNS/network failure: {e}")

        if (
            "timeout" in msg
            or "connection" in msg
            or "timed out" in msg
        ):
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

    finally:
        # 🔥 CRITICAL: ensure no blocking cleanup
        if executor:
            executor.shutdown(wait=False)