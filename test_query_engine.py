# intent_debug_cli.py

from intent_registry import INTENT_KEYWORDS, FILTER_KEYWORDS
from pathlib import Path

QUESTIONS_FILE = Path("questions.txt")


def normalize(text: str) -> str:
    return text.lower().strip()


def detect_intents(question: str):
    q = normalize(question)
    matches = []

    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                matches.append((intent, kw))
                break

    return matches


def detect_filters(question: str):
    q = normalize(question)
    matches = []

    for flt, keywords in FILTER_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                matches.append((flt, kw))
                break

    return matches


def main():
    print("🧠 Intent Debug Batch CLI\n")

    if not QUESTIONS_FILE.exists():
        print("❌ questions.txt not found")
        return

    questions = [
        line.strip()
        for line in QUESTIONS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    for question in questions:
        print(f"❓ Question: {question}\n")

        intents = detect_intents(question)
        filters = detect_filters(question)

        print("🔍 Analysis")

        if intents:
            print("🧩 Intents detected:")
            for intent, kw in intents:
                print(f"   • {intent} (keyword: '{kw}')")
        else:
            print("🧩 Intents detected: ❌ none")

        if filters:
            print("🧩 Filters detected:")
            for flt, kw in filters:
                print(f"   • {flt} (keyword: '{kw}')")
        else:
            print("🧩 Filters detected: ❌ none")

        print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    main()
