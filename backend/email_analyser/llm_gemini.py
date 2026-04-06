# llm_gemini.py

import os
import re
import time
import subprocess
import sys
from dotenv import load_dotenv

from backend.error_handling import (
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
# 🔥 SINGLE LLM CALL (NO RETRY, DIRECT)
# --------------------------------------------------
def call_llm(
    prompt: str,
    model: str,
    max_tokens: int,
    temp: float = 0
) -> str:

    TIMEOUT_SECONDS = 60

    print("\n➡️ Entered call_llm")

    try:

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        WORKER_PATH = os.path.join(BASE_DIR, "llm_worker.py")

        print("⏳ Spawning LLM worker...")

        result = subprocess.run(
            [sys.executable, WORKER_PATH, model, str(temp), str(max_tokens)],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            encoding="utf-8",
            errors="replace"
        )

        print("✅ Worker finished execution")

        output = (result.stdout or "").strip()

        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("RETURN CODE:", result.returncode)

        # --------------------------------------------------
        # ERROR FROM WORKER
        # --------------------------------------------------
        if output.startswith("ERROR::"):

            error_type = output.split("::")[1]

            if error_type == "NetworkError":
                raise NetworkError("LLM network error")

            elif error_type == "RateLimitError":
                raise RateLimitError("Rate limit hit")

            elif error_type == "AuthenticationError":
                raise AuthenticationError("Invalid API key")

            elif error_type == "ServiceUnavailableError":
                raise ServiceUnavailableError("Service unavailable")

            elif error_type == "NetworkDownError":
                raise NetworkDownError("Network down")

            else:
                raise LLMAPIError(output)

        # --------------------------------------------------
        # EMPTY RESPONSE CHECK
        # --------------------------------------------------
        if not output:
            raise LLMAPIError("Empty response from LLM")

        return output

    except subprocess.TimeoutExpired:
        print("⏱ TIMEOUT → killing worker (safe isolation)")
        raise LLMAPIError("LLM request timed out")

    except (NetworkError, RateLimitError, AuthenticationError, ServiceUnavailableError, NetworkDownError):
        raise

    except Exception as e:

        print(f"❌ Exception caught: {e}")
        msg = str(e).lower()

        if "quota" in msg or "limit" in msg:

            if "perday" in msg or "free_tier_requests" in msg:
                print("🛑 DAILY QUOTA EXHAUSTED")
                raise RateLimitError("DAILY_QUOTA_EXHAUSTED")

            raise RateLimitError("TEMP_RATE_LIMIT")

        if "api key" in msg or "permission" in msg or "unauthorized" in msg:
            raise AuthenticationError("Invalid or missing API key")

        if (
            "getaddrinfo failed"
            or "name or service not known"
            or "temporary failure in name resolution"
        ):
            raise NetworkDownError(f"DNS/network failure: {e}")

        if (
            "timeout" in msg
            or "connection" in msg
            or "timed out" in msg
        ):
            raise NetworkError(f"LLM network error: {e}")

        if "500" in msg or "503" in msg or "unavailable" in msg:
            raise ServiceUnavailableError("LLM service unavailable")

        raise LLMAPIError(f"LLM API failed: {e}")