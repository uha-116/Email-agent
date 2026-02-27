# entity_cache.py

from db_Connection_test import get_db_connection
from rapidfuzz import process


class EntityCache:
    def __init__(self):
        self.companies = set()
        self.roles = set()
        self.locations = set()

    # -------------------------------------------------
    # Load distinct values from DB (called at startup)
    # -------------------------------------------------
    def load_from_db(self):
        conn = get_db_connection()
        cur = conn.cursor()

        # Load companies
        cur.execute("SELECT DISTINCT company FROM opportunities WHERE company IS NOT NULL;")
        self.companies = {row[0].strip().lower() for row in cur.fetchall()}

        # Load roles
        cur.execute("SELECT DISTINCT role FROM opportunities WHERE role IS NOT NULL;")
        self.roles = {row[0].strip().lower() for row in cur.fetchall()}

        # Load locations
        cur.execute("SELECT DISTINCT location FROM opportunities WHERE location IS NOT NULL;")
        self.locations = {row[0].strip().lower() for row in cur.fetchall()}

        cur.close()
        conn.close()

        print("EntityCache loaded successfully.")
        print(f"Companies: {len(self.companies)}")
        print(f"Roles: {len(self.roles)}")
        print(f"Locations: {len(self.locations)}")

    # -------------------------------------------------
    # Generic matching logic with:
    # - Token-based matching
    # - Longest-match preference
    # - Fuzzy fallback
    # -------------------------------------------------
    def _match_entity(self, text, entity_set, threshold=85):
        text = text.lower()
        text_tokens = text.split()

        best_match = None
        best_token_count = 0
        best_match_ratio = 0

        # 1️⃣ Token-based matching (preferred method)
        for entity in entity_set:
            entity_tokens = entity.split()

            match_count = sum(1 for token in entity_tokens if token in text_tokens)

            if len(entity_tokens) > 1:
                match_ratio = match_count / len(entity_tokens)
            else:
                match_ratio = 1.0 if entity in text_tokens else 0

            if match_ratio >= 0.7:
                # Prefer entity with:
                # - Higher match ratio
                # - If tie → more tokens (more specific)
                if (
                    match_ratio > best_match_ratio
                    or (
                        match_ratio == best_match_ratio
                        and len(entity_tokens) > best_token_count
                    )
                ):
                    best_match = entity
                    best_token_count = len(entity_tokens)
                    best_match_ratio = match_ratio

        if best_match:
            return best_match

        # 2️⃣ Fuzzy fallback (only if no token match found)
        for token in text.split():
            if len(token) > 3:
                match, score, _ = process.extractOne(token, entity_set)
                if score >= threshold:
                    return match


        return None

    # -------------------------------------------------
    # Public matching methods
    # -------------------------------------------------
    def match_company(self, text):
        return self._match_entity(text, self.companies)

    def match_role(self, text):
        return self._match_entity(text, self.roles)

    def match_location(self, text):
        return self._match_entity(text, self.locations)

    # -------------------------------------------------
    # Optional: refresh after email sync
    # -------------------------------------------------
    def refresh(self):
        print("Refreshing EntityCache...")
        self.load_from_db()
