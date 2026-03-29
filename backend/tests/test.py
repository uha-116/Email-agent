from dotenv import load_dotenv
import os

load_dotenv()

print("ENV VALUE:", os.getenv("GMAIL_TOKEN"))