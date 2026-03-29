#llm_worker.py
import sys
import os
import time
from dotenv import load_dotenv
from google import genai
import sys

sys.stdout.reconfigure(encoding='utf-8')


# 🔥 Load env inside worker process
load_dotenv()


def run():
    prompt = sys.stdin.read()
    model = sys.argv[1]
    temp = float(sys.argv[2])

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    MAX_RETRIES = 2  # 🔥 only 1 retry

    for attempt in range(MAX_RETRIES):
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
                raise Exception("Empty response")

            print(response.text)
            return

        except Exception as e:
            msg = str(e).lower()

            # -----------------------------
            # NETWORK DOWN (NO RETRY)
            # -----------------------------
            if (
                "getaddrinfo failed" in msg
                or "name or service not known" in msg
                or "temporary failure in name resolution" in msg
            ):
                print("ERROR::NetworkDownError")
                return

            # -----------------------------
            # NETWORK ERROR (RETRYABLE)
            # -----------------------------
            if (
                "timeout" in msg
                or "connection" in msg
                or "timed out" in msg
            ):
                if attempt < MAX_RETRIES - 1:
                    time.sleep(1)
                    continue

                print("ERROR::NetworkError")
                return

            # -----------------------------
            # RATE LIMIT
            # -----------------------------
            if "quota" in msg or "limit" in msg:
                print("ERROR::RateLimitError")
                return

            # -----------------------------
            # AUTH ERROR
            # -----------------------------
            if (
                "api key" in msg
                or "unauthorized" in msg
                or "permission" in msg
            ):
                print("ERROR::AuthenticationError")
                return

            # -----------------------------
            # SERVICE DOWN
            # -----------------------------
            if "500" in msg or "503" in msg or "unavailable" in msg:
                print("ERROR::ServiceUnavailableError")
                return

            # -----------------------------
            # UNKNOWN ERROR
            # -----------------------------
            print(f"ERROR::LLMAPIError::{str(e)}")
            return


if __name__ == "__main__":
    run()