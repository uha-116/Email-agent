# filter_extractor.py

import re
from dateutil import parser as dateparser


STAGE_KEYWORDS = {
    "interview": "INTERVIEW",
    "assessment": "ASSESSMENT",
    "selected": "SELECTED",
    "rejected": "REJECTED",
    "applied": "APPLIED",
    "shortlisted": "SHORTLISTED"
}


ACTION_REQUIRED_KEYWORDS = [
    "need to act",
    "act upon",
    "pending",
    "incomplete",
    "requires action",
    ""
]


def detect_filters(text, entity_cache):
    text = text.lower()
    filters = {}

    # ----------------------------
    # 1️⃣ Entity Detection
    # ----------------------------
    company = entity_cache.match_company(text)
    if company:
        filters["company"] = company

    role = entity_cache.match_role(text)
    if role:
        if role=='internship':
            filters["role"] = 'intern'
        else:
            filters["role"]=role

    location = entity_cache.match_location(text)
    if location:
        filters["location"] = location

    # ----------------------------
    # Stage Detection (Priority-Based)
    # ----------------------------

    NEGATION_WORDS = ["not", "havent", "didnt", "without"]

    STAGE_PRIORITY = {
        "INTERVIEW": 6,
        "ASSESSMENT": 5,
        "SELECTED": 4,
        "REJECTED": 3,
        "APPLIED": 2,
        "OPPORTUNITY_FOUND": 1
    }

    detected_stages = []

    for word, stage in STAGE_KEYWORDS.items():
        if word in text:
            # Check if stage word is negated nearby
            negated = any(neg in text for neg in NEGATION_WORDS)

            if not negated:
                detected_stages.append(stage)

    # If we found positive stages, pick highest priority
    if detected_stages:
        highest_stage = max(
            detected_stages,
            key=lambda s: STAGE_PRIORITY.get(s, 0)
        )
        filters["pipeline_stage"] = [highest_stage]

    # If no stage found → check generic job words
    elif any(word in text for word in ["job", "jobs", "opportunity", "opportunities","interns","internships"]):
        filters["pipeline_stage"] = ["OPPORTUNITY_FOUND"]



    # ----------------------------
    # 3️⃣ Action Required
    # ----------------------------
    if any(keyword in text for keyword in ACTION_REQUIRED_KEYWORDS):
        filters["action_required"] = True

    # ----------------------------
    # 4️⃣ Time Detection
    # ----------------------------

    # ----------------------------
    # Relative Day Detection
    # ----------------------------

    day_match = re.search(r"(\d+)\s*day", text)

    if day_match:
        number = int(day_match.group(1))

        # Check if context implies past range
        if any(word in text for word in ["last", "past", "previous", "back", "ago"]):
            filters["last_n_days"] = number


    # Today / Tomorrow
    if "today" in text:
        filters["event_date"] = "TODAY"

    if "tomorrow" in text:
        filters["event_date"] = "TOMORROW"

    if "this week" in text:
        filters["time_range"] = "THIS_WEEK"
    
        # Recently / Latest
    if any(word in text for word in ["recent", "recently","latest", "new"]):
        filters["time_range"] = "RECENT"


    # Specific Date
    try:
        if any(month in text for month in [
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec"
    ]):
            parsed_date = dateparser.parse(text)
            if parsed_date:
                filters["parsed_date"] = parsed_date.date().isoformat()

    except:
        pass

    # ----------------------------
    # 5️⃣ Salary Detection
    # ----------------------------

    salary_match = re.search(
        r"(above|greater than|more than|below|less than)?\s*(\d+(?:\.\d+)?)\s*(k|lakh|lakhs|lpa|per month|per year|month|year)?",
        text
    )

    if salary_match and salary_match.group(3):
        comparator = salary_match.group(1)
        amount = float(salary_match.group(2))
        unit = salary_match.group(3)

        # Normalize amount
        if unit in ["lakh", "lakhs", "lpa"]:
            amount *= 100000
            filters["salary_period"] = "YEARLY"
        elif unit == "k":
            amount *= 1000
        elif unit in ["per month", "month"]:
            filters["salary_period"] = "MONTHLY"
        elif unit in ["per year", "year"]:
            filters["salary_period"] = "YEARLY"

        if comparator in ["above", "greater than", "more than"]:
            filters["salary_min"] = amount
        elif comparator in ["below", "less than"]:
            filters["salary_max"] = amount
        else:
            filters["salary_exact"] = amount

    return filters
