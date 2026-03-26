import json

from backend.query_engine.intent_to_sql import resolve_user_question


# ---------------------------------------------------------
# Pretty printer
# ---------------------------------------------------------

def print_result(result):

    print("\n" + "=" * 100)

    if result is None:
        print("❌ No result returned.")
        return

    # -----------------------------
    # LLM route
    # -----------------------------

    if result.get("route") == "LLM_SQL_GENERATION":

        print("🚨 ROUTE → LLM SQL GENERATION")
        print("User Question:", result["user_question"])
        print("=" * 100)
        return

    # -----------------------------
    # SBERT matched route
    # -----------------------------

    print("🧠 USER QUESTION:")
    print(result["user_question"])

    print("\n🎯 MATCHED DATASET QUESTION:")
    print(result["matched_question"])

    print("\n📊 SIMILARITY SCORE:")
    print(round(result["similarity"], 3))

    print("\n🔎 EXTRACTED FILTERS:")
    print(json.dumps(result["filters"], indent=4))

    print("\n📦 FINAL QUERY JSON:")
    print(json.dumps(result["query_json"], indent=4))

    print("\n🧮 COUNT SQL:")
    print(result["count_sql"])

    print("\n📄 LIST SQL:")
    print(result["list_sql"])

    print("=" * 100)


# ---------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------

def main():

    print("\n🚀 Conversational Query Engine Test")
    print("Type your question and press Enter")
    print("Press Ctrl+C to exit\n")

    try:

        while True:

            question = input("Ask a question: ").strip()

            if not question:
                continue

            result = resolve_user_question(question)

            print_result(result)

    except KeyboardInterrupt:

        print("\n\n👋 Exiting test program.")


if __name__ == "__main__":
    main()