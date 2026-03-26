import json

from backend.query_engine.sbert_model import SBERTMatcher
from backend.query_engine.filter_extraction import detect_filters
from backend.query_engine.entity_cache import EntityCache
from backend.query_engine.sql_builder import build_sql


SIMILARITY_THRESHOLD = 0.6
DATA_FILE = "data/data.json"


# -------------------------------------------------------
# Load dataset JSON
# -------------------------------------------------------

def load_dataset():

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    mapping = {}

    for item in data:
        q = item["question"].strip().lower()
        mapping[q] = item

    return mapping


# -------------------------------------------------------
# Detect placeholder values
# -------------------------------------------------------

def is_placeholder(value):

    if isinstance(value, str):
        return value.startswith("{") and value.endswith("}")

    if isinstance(value, list):
        for v in value:
            if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                return True

    return False


# -------------------------------------------------------
# Initialize components once
# -------------------------------------------------------

matcher = SBERTMatcher()

entity_cache = EntityCache()
entity_cache.load_from_db()

dataset_map = load_dataset()


# -------------------------------------------------------
# MAIN FUNCTION
# -------------------------------------------------------

def resolve_user_question(user_question):

    matches = matcher.find_top_matches(user_question, top_k=1)

    top_match = matches[0]

    matched_question = top_match["question"]
    score = top_match["score"]

    print("\nTop Match:", matched_question)
    print("Score:", score)

    # ---------------------------------------------------
    # PATH 1 — SBERT DATASET MATCH
    # ---------------------------------------------------

    if score >= SIMILARITY_THRESHOLD:

        query_json = dataset_map.get(matched_question)

        if not query_json:
            print("Dataset mapping missing.")
            return None

        # Extract dynamic filters from user question
        dynamic_filters = detect_filters(user_question, entity_cache)

        base_filters = query_json.get("filters", {})

        # ---------------------------------------------------
        # Remove placeholder filters from dataset filters
        # ---------------------------------------------------

        clean_base_filters = {}

        for key, value in base_filters.items():

            if is_placeholder(value):
                continue

            clean_base_filters[key] = value

        # ---------------------------------------------------
        # Merge filters
        # ---------------------------------------------------

        merged_filters = {**clean_base_filters, **dynamic_filters}

        query_json = query_json.copy()
        query_json["filters"] = merged_filters

        sql = build_sql(query_json)

        result = {
            "user_question": user_question,
            "matched_question": matched_question,
            "similarity": score,
            "query_json": query_json,
            "count_sql": sql["count_sql"],
            "list_sql": sql["list_sql"],
        }

        return result

    # ---------------------------------------------------
    # PATH 2 — LLM SQL GENERATION
    # ---------------------------------------------------

    else:

        print("\nLow similarity. Route to LLM SQL generation.")

        return {
            "user_question": user_question,
            "route": "LLM_SQL_GENERATION"
        }