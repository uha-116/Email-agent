import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

# Use ONLY one stable Gemini model
MODEL_NAME = "models/gemini-2.5-flash"

client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY")
)


class LLMQuotaExhausted(Exception):
    pass


def call_llm(prompt: str) -> str:
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text

    except Exception as e:
        msg = str(e).lower()

        if "quota" in msg or "limit" in msg:
            raise LLMQuotaExhausted(
                "Gemini free tier quota exhausted. Resume tomorrow."
            )

        raise
