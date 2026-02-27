# intent_detector.py

import re
from intent_registry import INTENT_KEYWORDS, FILTER_KEYWORDS


# ---------------- NORMALIZATION ----------------

def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------- KEYWORD MATCH ----------------

def keyword_match(keyword: str, text: str) -> bool:
    """
    Multi-word phrase → substring match
    Single word → strict word boundary match
    """
    if " " in keyword:
        return keyword in text

    return re.search(rf"\b{re.escape(keyword)}\b", text) is not None


# ---------------- INTENT DETECTION ----------------

def detect_intents(query: str):
    q = normalize(query)
    matches = []

    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            kw_norm = normalize(kw)

            if keyword_match(kw_norm, q):
                matches.append((intent, kw))
                break

    return matches


# ---------------- FILTER DETECTION ----------------

def detect_filters(query: str):
    q = normalize(query)
    matches = []

    for flt, keywords in FILTER_KEYWORDS.items():
        for kw in keywords:
            kw_norm = normalize(kw)

            if keyword_match(kw_norm, q):
                matches.append((flt, kw))
                break

    return matches

