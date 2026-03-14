import os
from google import genai
from dotenv import load_dotenv

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# Initialize Gemini Client
# --------------------------------------------------
client = genai.Client(
    api_key=os.getenv("GOOGLE_API_KEY")
)

# --------------------------------------------------
# Custom Exception
# --------------------------------------------------
class LLMQuotaExhausted(Exception):
    """Raised when Gemini free-tier quota is exhausted."""
    pass


# --------------------------------------------------
# Generic LLM Caller
# --------------------------------------------------
def call_llm(prompt: str, model: str, temperature: float = 0) -> str:
    """
    Generic Gemini LLM caller.

    Args:
        prompt (str): Prompt text
        model (str): Gemini model name
        temperature (float): Sampling temperature

    Returns:
        str: LLM generated text
    """

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "temperature": temperature
            }
        )

        if response and response.text:
            return response.text

        return ""

    except Exception as e:
        msg = str(e).lower()

        # Handle quota exhaustion
        if "quota" in msg or "limit" in msg:
            raise LLMQuotaExhausted(
                "Gemini free tier quota exhausted. Resume tomorrow."
            )

        # Re-raise unknown errors
        raise

