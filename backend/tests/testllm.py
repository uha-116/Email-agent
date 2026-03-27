from google import genai
import inspect

client = genai.Client(api_key="test")

print(inspect.signature(client.models.generate_content))