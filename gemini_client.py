import os
import time
from google import genai


class QuotaExhausted(Exception):
    """Raised when all LLM quotas are exhausted."""
    pass


class GeminiModel:
    def __init__(self, api_key: str, model_name: str):
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text

        except Exception as e:
            msg = str(e)

            if "RESOURCE_EXHAUSTED" in msg or "Quota" in msg:
                raise QuotaExhausted(
                    f"Quota exhausted for model {self.model_name}"
                )

            raise e


class GeminiPool:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")

        self.models = [
            GeminiModel(api_key, "models/gemini-2.5-flash"),
            GeminiModel(api_key, "models/gemini-2.5-pro"),
            GeminiModel(api_key, "models/gemini-flash-latest"),
        ]

    def call(self, prompt: str) -> str:
        for model in self.models:
            try:
                print(f"🧠 Trying LLM: {model.model_name}")
                return model.generate(prompt)

            except QuotaExhausted as e:
                print(f"⚠️ {e}")
                continue

        # If we reach here → all models exhausted
        raise QuotaExhausted("All Gemini model quotas exhausted")
