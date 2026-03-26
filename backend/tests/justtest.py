import time
from datetime import datetime

from backend.email_analyser.llm_gemini import call_llm
from backend.error_handling import (
    ServiceUnavailableError,
    RateLimitError,
    NetworkError,
    AuthenticationError,
    NetworkDownError
)

MODEL = "models/gemini-3.1-flash-lite-preview"   # change if needed


# =========================================================
# SINGLE TEST
# =========================================================

def test_once():

    print("\n" + "="*60)
    print("⏱️ Testing LLM Server at:", datetime.now())
    print("="*60)

    start = time.time()

    try:
        response = call_llm("Say hello in one line", MODEL, 0)

        end = time.time()

        print("\n✅ SUCCESS")
        print("Response:", response)
        print(f"⏳ Time taken: {round(end - start, 2)} sec")

        return True

    except ServiceUnavailableError as e:
        print("\n❌ SERVICE UNAVAILABLE:", e.user_message)

    except RateLimitError as e:
        print("\n⚠️ RATE LIMIT:", e.user_message)

    except NetworkDownError as e:
        print("\n🛑 NO INTERNET:", e.user_message)

    except NetworkError as e:
        print("\n⚠️ NETWORK ISSUE:", e.user_message)

    except AuthenticationError as e:
        print("\n🔑 AUTH ERROR:", e.user_message)

    except Exception as e:
        print("\n❌ UNKNOWN ERROR:", e)

    return False


# =========================================================
# CONTINUOUS MONITOR
# =========================================================

def monitor(retries=5, delay=10):
    """
    Keeps checking server every `delay` seconds
    """

    print("\n🚀 Starting LLM Server Monitor\n")

    success_count = 0

    for i in range(retries):

        print(f"\n🔁 Attempt {i+1}/{retries}")

        success = test_once()

        if success:
            success_count += 1

        if i < retries - 1:
            print(f"\n⏳ Waiting {delay} seconds...\n")
            time.sleep(delay)

    print("\n" + "="*60)
    print("📊 FINAL REPORT")
    print("="*60)
    print(f"Total Attempts: {retries}")
    print(f"Successful: {success_count}")
    print(f"Failed: {retries - success_count}")

    if success_count == 0:
        print("\n🚨 LLM is completely unavailable")
    elif success_count < retries:
        print("\n⚠️ LLM is unstable")
    else:
        print("\n✅ LLM is stable")


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("\n🧪 LLM SERVER TEST TOOL\n")

    mode = input("Choose mode (1 = single test, 2 = monitor): ").strip()

    if mode == "1":
        test_once()

    elif mode == "2":
        monitor(retries=6, delay=15)

    else:
        print("Invalid option")