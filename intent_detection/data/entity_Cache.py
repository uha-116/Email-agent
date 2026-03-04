# entity_cache.py

import re
from rapidfuzz import fuzz, process
from db_Connection_test import get_db_connection


class EntityCache:
    def __init__(self):
        self.companies = set()
        self.roles = set()
        self.locations = set()

    # -------------------------------------------------
    # Load distinct values from DB
    # -------------------------------------------------
    def load_from_db(self):
        conn = get_db_connection()
        cur = conn.cursor()

        # Companies
        cur.execute(
            "SELECT DISTINCT company FROM opportunities WHERE company IS NOT NULL;"
        )
        self.companies = {
            row[0].strip().lower()
            for row in cur.fetchall()
            if row[0] and len(row[0].strip()) > 2
        }

        # Roles
        cur.execute(
            "SELECT DISTINCT role FROM opportunities WHERE role IS NOT NULL;"
        )
        self.roles = {
            row[0].strip().lower()
            for row in cur.fetchall()
            if row[0] and len(row[0].strip()) > 2
        }

        # Locations
        cur.execute(
            "SELECT DISTINCT location FROM opportunities WHERE location IS NOT NULL;"
        )
        self.locations = {
            row[0].strip().lower()
            for row in cur.fetchall()
            if row[0] and len(row[0].strip()) > 2
        }

        cur.close()
        conn.close()

        print("EntityCache loaded successfully.")
        print(f"Companies: {len(self.companies)}")
        print(f"Roles: {len(self.roles)}")
        print(f"Locations: {len(self.locations)}")

    # -------------------------------------------------
    # STRICT PHRASE MATCHING (PRIMARY)
    # -------------------------------------------------
    def _exact_phrase_match(self, text, entity_set):
        for entity in entity_set:
            pattern = rf"\b{re.escape(entity)}\b"
            if re.search(pattern, text):
                return entity
        return None

    # -------------------------------------------------
    # FUZZY FULL-PHRASE MATCH (FALLBACK ONLY)
    # -------------------------------------------------
    def _fuzzy_match(self, text, entity_set, threshold=92):
        best_match = None
        best_score = 0

        for entity in entity_set:
            score = fuzz.partial_ratio(entity, text)

            if score >= threshold and score > best_score:
                best_match = entity
                best_score = score

        return best_match

    # -------------------------------------------------
    # GENERIC SAFE MATCH
    # -------------------------------------------------
    def _match_entity(self, text, entity_set, fuzzy_threshold=92):
        text = text.lower()

        # 1️⃣ Strict exact phrase match first
        exact = self._exact_phrase_match(text, entity_set)
        if exact:
            return exact

        # 2️⃣ Conservative fuzzy fallback
        return self._fuzzy_match(text, entity_set, threshold=fuzzy_threshold)

    # -------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------
    def match_company(self, text):
        # Companies must be VERY strict
        return self._match_entity(text, self.companies, fuzzy_threshold=93)

    def match_role(self, text):
        # Roles slightly less strict
        return self._match_entity(text, self.roles, fuzzy_threshold=90)

    def match_location(self, text):
        return self._match_entity(text, self.locations, fuzzy_threshold=90)

    # -------------------------------------------------
    # Optional refresh
    # -------------------------------------------------
    def refresh(self):
        print("Refreshing EntityCache...")
        self.load_from_db()