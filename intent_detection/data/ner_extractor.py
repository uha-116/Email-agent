import json
import re
import spacy
import dateparser

# Load spaCy model
nlp = spacy.load("en_core_web_lg")

# ---------- JOB MODES ----------
JOB_MODES = {
    "remote": ["remote", "wfh", "work from home"],
    "hybrid": ["hybrid"],
    "onsite": ["onsite", "on site", "in office", "office"],
    "campus": ["campus", "on campus"]
}

# ---------- ROLE KEYWORDS ----------
ROLE_KEYWORDS = [
    "intern", "internship",
    "fresher", "student",
    "engineer", "software engineer",
    "ai engineer", "ml engineer",
    "frontend", "backend", "fullstack",
    "developer", "entry level"
]

# ---------- SALARY PATTERNS ----------
SALARY_REGEX = re.compile(
    r'(\d+(?:\.\d+)?\s*(k|lpa|lakh|lakhs|per month|per year|month|year))',
    re.IGNORECASE
)

# ---------- RELATIVE TIME ----------
RELATIVE_TIME_REGEX = re.compile(
    r'(last|past|next)\s+\d+\s+(day|days|week|weeks|month|months)',
    re.IGNORECASE
)

# ---------- SIMPLE TIME KEYWORDS ----------
TIME_KEYWORDS = [
    "today", "tomorrow", "yesterday",
    "recently", "now", "currently",
    "last week", "this week", "next week",
    "last month", "this month", "next month"
]


def extract_entities(question: str):
    question = question.lower()
    doc = nlp(question)

    entities = {
        "role": [],
        "salary": [],
        "time": [],
        "location_mode": []
    }

    # ---------- DATE / TIME via spaCy ----------
    for ent in doc.ents:
        if ent.label_ == "DATE":
            parsed = dateparser.parse(ent.text)
            if parsed:
                entities["time"].append(ent.text.lower())

    # ---------- Relative time (last 5 days etc.) ----------
    for match in RELATIVE_TIME_REGEX.findall(question):
        entities["time"].append(" ".join(match).lower())

    # ---------- Simple time keywords ----------
    for t in TIME_KEYWORDS:
        if t in question:
            entities["time"].append(t)

    # ---------- Job modes ----------
    for mode, keywords in JOB_MODES.items():
        for kw in keywords:
            if kw in question:
                entities["location_mode"].append(mode)

    # ---------- Roles ----------
    for role in ROLE_KEYWORDS:
        if role in question:
            entities["role"].append(role)

    # ---------- Salary ----------
    for match in SALARY_REGEX.findall(question):
        entities["salary"].append(match[0].lower())

    # Deduplicate all fields
    for k in entities:
        entities[k] = list(set(entities[k]))

    return entities


# ---------- MAIN ----------
if __name__ == "__main__":
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\n--- NER EXTRACTION RESULTS (NO COMPANY / LOCATION) ---\n")

    for item in data:
        q = item["question"]
        extracted = extract_entities(q)

        print(f"QUESTION: {q}")
        print(extracted)
        print("-" * 60)
