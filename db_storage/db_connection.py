import os
import psycopg2
from dotenv import load_dotenv

def get_db_connection():
    load_dotenv()
    return psycopg2.connect(os.getenv("DATABASE_URL"))
