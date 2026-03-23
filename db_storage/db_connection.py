import os
import psycopg2
from dotenv import load_dotenv

from error_handling import (
    retry,
    DBConnectionError,
    NetworkDownError   # 🔥 ADDED
)

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

        conn.autocommit = False

        return conn

    except psycopg2.OperationalError as e:

        msg = str(e).lower()

        # 🔥 HARD NETWORK FAILURE (NO INTERNET)
        if (
            "could not translate host name" in msg
            or "name or service not known" in msg
            or "temporary failure in name resolution" in msg
        ):
            raise NetworkDownError(f"Database DNS/network failure: {e}")

        raise DBConnectionError(f"Database connection failed: {e}")

    except Exception as e:
        raise DBConnectionError(f"Unexpected DB connection error: {e}")