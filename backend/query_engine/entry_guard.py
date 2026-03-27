import json
import os
from rapidfuzz import fuzz

# --------------------------------------------------
# LOAD CONFIG
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "data", "entry_guard.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    GUARD_CONFIG = json.load(f)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def normalize(text: str) -> str:
    return text.lower().strip()


def exact_match(query: str, patterns: list) -> bool:
    return any(p in query for p in patterns)


def fuzzy_match(query: str, patterns: list, threshold: int = 85) -> bool:
    for p in patterns:
        if fuzz.partial_ratio(query, p) >= threshold:
            return True
    return False


def match_patterns(query: str, patterns: list) -> bool:
    """
    Hybrid matching:
    1. Exact match
    2. Fuzzy match
    """
    if exact_match(query, patterns):
        return True

    if fuzzy_match(query, patterns):
        return True

    return False


# --------------------------------------------------
# MAIN GUARD FUNCTION
# --------------------------------------------------

def check_entry_guard(query: str) -> dict:
    """
    Returns:
        {
            "block": bool,
            "message": str | None
        }
    """

    query = normalize(query)

    # --------------------------------------------------
    # 🟡 PERSON SCOPE CHECK
    # --------------------------------------------------
    person_cfg = GUARD_CONFIG.get("person_scope", {})
    if match_patterns(query, person_cfg.get("patterns", [])):
        return {
            "block": True,
            "message": person_cfg.get(
                "message",
                "I can only track your job applications."
            )
        }

    # --------------------------------------------------
    # 🟠 HISTORY QUERY CHECK
    # --------------------------------------------------
    history_cfg = GUARD_CONFIG.get("history_queries", {})
    if match_patterns(query, history_cfg.get("patterns", [])):
        return {
            "block": True,
            "message": history_cfg.get(
                "message",
                "I currently track only the latest stage."
            )
        }

    # --------------------------------------------------
    # ✅ ALLOW
    # --------------------------------------------------
    return {
        "block": False,
        "message": None
    }