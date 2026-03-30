#llm_gemini.py
import os
import re
import time
import subprocess
import sys
from dotenv import load_dotenv

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
# 🔥 GENERIC LLM CALLER (SUBPROCESS VERSION)
# --------------------------------------------------
@retry(max_attempts=1)
def call_llm(prompt: str, model: str, temp: float = 0,max_tokens:int) -> str:

    TIMEOUT_SECONDS = 60

    print("\n➡️ Entered call_llm")

    try:
        time.sleep(1)  # 🔥 basic rate limiter

        # 🔥 Absolute path to worker
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        WORKER_PATH = os.path.join(BASE_DIR, "llm_worker.py")

        print("⏳ Spawning LLM worker...")

        result = subprocess.run(
            [sys.executable, WORKER_PATH, model, str(temp),str(max_tokens)],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            encoding="utf-8",
             errors="replace"
        )

        print("✅ Worker finished execution")

        output = (result.stdout or "").strip()

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

    except subprocess.TimeoutExpired as e:
        print("⏱ TIMEOUT → killing worker (safe isolation)")
        raise LLMAPIError("LLM request timed out")

    # -----------------------------
    # 🔥 ADD THIS BLOCK (CRITICAL)
    # -----------------------------
    except (NetworkError, RateLimitError, AuthenticationError, ServiceUnavailableError, NetworkDownError):
        raise

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