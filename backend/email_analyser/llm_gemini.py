import os
import re
import time
import concurrent.futures
from dotenv import load_dotenv
from google import genai

from backend.error_handling import (
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
# 🔥 INTERNAL: RUN INSIDE PROCESS
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
# 🔥 GENERIC LLM CALLER (FINAL VERSION - FIXED)
# --------------------------------------------------
@retry(max_attempts=1)
def call_llm(prompt: str, model: str, temp: float = 0) -> str:

    TIMEOUT_SECONDS = 60

    print("\n➡️ Entered call_llm")

    executor = None

    try:
        time.sleep(1)  # 🔥 basic rate limiter

        executor = concurrent.futures.ProcessPoolExecutor(max_workers=1)

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
            print("⏱ TIMEOUT → DO NOT RETRY (quota may be consumed)")

            # 🔥 FIX: force shutdown properly
            executor.shutdown(wait=True, cancel_futures=True)
            executor = None

            raise LLMAPIError("LLM request timed out")

        # --------------------------------------------------
        # EMPTY RESPONSE CHECK
        # --------------------------------------------------
        if not response or not getattr(response, "text", None):
            raise LLMAPIError("Empty response from LLM")

        return response.text

    except Exception as e:

        print(f"❌ Exception caught: {e}")
        msg = str(e).lower()

        # -----------------------------
        # 🔴 RATE LIMIT / QUOTA
        # -----------------------------
        if "quota" in msg or "limit" in msg:

            if "perday" in msg or "free_tier_requests" in msg:
                print("🛑 DAILY QUOTA EXHAUSTED")
                raise RateLimitError("DAILY_QUOTA_EXHAUSTED")

            match = re.search(r"retry in (\d+)", msg)
            if match:
                delay = int(match.group(1))
                print(f"⏳ Temporary rate limit → waiting {delay}s")
                time.sleep(delay)

            raise RateLimitError("TEMP_RATE_LIMIT")

        # -----------------------------
        # AUTH ERROR
        # -----------------------------
        if "api key" in msg or "permission" in msg or "unauthorized" in msg:
            raise AuthenticationError("Invalid or missing API key")

        # -----------------------------
        # NETWORK DOWN
        # -----------------------------
        if (
            "getaddrinfo failed" in msg
            or "name or service not known" in msg
            or "temporary failure in name resolution" in msg
        ):
            raise NetworkDownError(f"DNS/network failure: {e}")

        # -----------------------------
        # NETWORK ERROR
        # -----------------------------
        if (
            "timeout" in msg
            or "connection" in msg
            or "timed out" in msg
        ):
            raise NetworkError(f"LLM network error: {e}")

        # -----------------------------
        # SERVICE DOWN
        # -----------------------------
        if "500" in msg or "503" in msg or "unavailable" in msg:
            raise ServiceUnavailableError("LLM service unavailable")

        # -----------------------------
        # UNKNOWN ERROR
        # -----------------------------
        raise LLMAPIError(f"LLM API failed: {e}")

    finally:
        # 🔥 CRITICAL FIX: ensure proper cleanup
        if executor:
            try:
                executor.shutdown(wait=True)
            except Exception:
                pass