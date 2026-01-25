# db_test.py
import os
import psycopg2
from dotenv import load_dotenv


def get_db_connection():
    """
    Creates and returns a PostgreSQL database connection
    using environment variables.

    Raises:
        Exception if connection fails
    """
    load_dotenv()

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )
    return conn


if __name__ == "__main__":
    print("🔍 Testing PostgreSQL connection...")

    try:
        conn = get_db_connection()
        print("✅ PostgreSQL connected successfully!")
        conn.close()
        print("🔌 Connection closed cleanly.")

    except Exception as e:
        print("❌ Database connection failed:")
        print(e)
