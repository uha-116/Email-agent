import os
import psycopg2
from dotenv import load_dotenv

from error_handling import retry, DBConnectionError

# --------------------------------------------------
# LOAD ENV ONCE
# --------------------------------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# --------------------------------------------------
# GET DB CONNECTION (WITH RETRY)
# --------------------------------------------------

@retry(max_attempts=2)
def get_db_connection():
    """
    Establish PostgreSQL connection.

    Raises:
        DBConnectionError (retryable)
    """

    if not DATABASE_URL:
        raise DBConnectionError("DATABASE_URL not configured")

    try:
        conn = psycopg2.connect(DATABASE_URL)

        # Optional but good practice
        conn.autocommit = False

        return conn

    except psycopg2.OperationalError as e:
        raise DBConnectionError(f"Database connection failed: {e}")

    except Exception as e:
        # Unexpected but still DB-level issue
        raise DBConnectionError(f"Unexpected DB connection error: {e}")