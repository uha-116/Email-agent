# llm_worker.py

import sys
import os
from dotenv import load_dotenv
from google import genai

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# 🔥 Load env inside worker process
load_dotenv()


def run():
    prompt = sys.stdin.read()
    model = sys.argv[1]
    temp = float(sys.argv[2])
    max_tokens = int(sys.argv[3])

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    try:
        # --------------------------------------------------
        # LLM CALL (SINGLE ATTEMPT ONLY)
        # --------------------------------------------------
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "temperature": temp,
                "max_output_tokens": max_tokens
            }
        )

        # --------------------------------------------------
        # EMPTY RESPONSE CHECK
        # --------------------------------------------------
        if not response or not getattr(response, "text", None):
            raise Exception("Empty response")

        print(response.text)

    except Exception as e:
        msg = str(e).lower()

        # --------------------------------------------------
        # NETWORK DOWN
        # --------------------------------------------------
        if (
            "getaddrinfo failed" in msg
            or "name or service not known" in msg
            or "temporary failure in name resolution" in msg
        ):
            print("ERROR::NetworkDownError")
            return

        # --------------------------------------------------
        # NETWORK ERROR
        # --------------------------------------------------
        if (
            "timeout" in msg
            or "connection" in msg
            or "timed out" in msg
        ):
            print("ERROR::NetworkError")
            return

        # --------------------------------------------------
        # RATE LIMIT
        # --------------------------------------------------
        if "quota" in msg or "limit" in msg:
            print("ERROR::RateLimitError")
            return

        # --------------------------------------------------
        # AUTH ERROR
        # --------------------------------------------------
        if (
            "api key" in msg
            or "unauthorized" in msg
            or "permission" in msg
        ):
            print("ERROR::AuthenticationError")
            return

        # --------------------------------------------------
        # SERVICE DOWN
        # --------------------------------------------------
        if "500" in msg or "503" in msg or "unavailable" in msg:
            print("ERROR::ServiceUnavailableError")
            return

        # --------------------------------------------------
        # UNKNOWN ERROR
        # --------------------------------------------------
        print(f"ERROR::LLMAPIError::{str(e)}")
        return


if __name__ == "__main__":
    run()