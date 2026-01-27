import os
import time
from groq import Groq

# Initialize Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# Single stable model (enough for your project)
MODEL_NAME = "llama-3.1-8b-instant"


class LLMQuotaExhausted(Exception):
    pass


def call_llm(prompt: str) -> str:
    """
    Calls Groq LLM safely.
    Raises LLMQuotaExhausted if rate limit hit.
    """

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        return response.choices[0].message.content

    except Exception as e:
        msg = str(e)

        # Handle rate limits explicitly
        if "429" in msg or "rate limit" in msg.lower():
            raise LLMQuotaExhausted(
                "Groq quota exhausted. Stop ingestion and resume later."
            )

        raise
