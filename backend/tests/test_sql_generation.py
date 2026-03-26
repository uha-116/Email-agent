import os
from dotenv import load_dotenv

from backend.email_analyser.llm_gemini import call_llm
from backend.email_analyser.prompts import SQL_GENERATION_PROMPT


# --------------------------------------------------
# LOAD ENV
# --------------------------------------------------
load_dotenv()

MODEL_NAME = os.getenv("SQL_GENERATION_MODEL")

if not MODEL_NAME:
    raise ValueError("SQL_GENERATION_MODEL not found in .env")


# --------------------------------------------------
# READ QUESTIONS
# --------------------------------------------------
def load_questions(file_path="sample.txt"):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} not found")

    with open(file_path, "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

    return questions


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
    print("🔥 Batch SQL Generation Test\n")

    questions = load_questions()

    for idx, user_query in enumerate(questions, start=1):
        try:
            print(f"📌 Q{idx}: {user_query}")

            # --------------------------------------------------
            # BUILD PROMPT
            # --------------------------------------------------
            prompt = SQL_GENERATION_PROMPT.format(
                user_question=user_query
            )
            print("🚀 Generating SQL...\n")

            sql = call_llm(
                prompt=prompt,
                model=MODEL_NAME,
                temp=0
            )

            print("🧾 Generated SQL:\n")
            print(sql)

        except Exception as e:
            print(f"❌ Error: {e}")

        print("\n" + "=" * 80 + "\n")


# --------------------------------------------------
# ENTRY
# --------------------------------------------------
if __name__ == "__main__":
    main()