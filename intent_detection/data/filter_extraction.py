# filter_extractor.py

import re


# =========================================================
# TIME SEMANTIC MAPPINGS (bucket -> variants)
# =========================================================

TIME_MAPPINGS = {
    "TODAY": ["today"],
    "TOMORROW": ["tomorrow"],
    "THIS_WEEK": ["this week"],
    "RECENT": [
        "recent",
        "recently",
        "latest",
        "new",
        "last week",
        "past few days",
        "in the last few days",
        "right now",
        "past",
        "earlier",
        "previously"
        "previous",
        "lastly",
        "last"
    ],
    "FUTURE": [
        "upcoming",
        "future",
        "coming up",
        "next week",
        "coming",
        "next"
    ],
    "MISSED": ["miss", "missed", "forget", "forgot", "forgotten"]
}

# =========================================================
# SUPERLATIVE MAPPINGS
# =========================================================

SUPERLATIVE_MAPPINGS = {
    "MOST": ["most", "highest", "top", "maximum", "max","common","most common"],
    "LEAST": ["least", "lowest", "minimum", "min"]
}

# ---------------------------------------------------------
# Relative Time Pattern (captures number)
# Example:
#   last 5 days
#   past 2 weeks
#   next 3 months
# ---------------------------------------------------------

RELATIVE_TIME_PATTERN = re.compile(
    r"(last|past|next)\s+(\d+)\s+(day|days|week|weeks|month|months|year|years)",
    re.IGNORECASE
)


# =========================================================
# SALARY PATTERN (STRICT — salary-only units)
# =========================================================

SALARY_PATTERN = re.compile(
    r"(above|greater than|more than|below|less than)?\s*"
    r"(\d+(?:\.\d+)?)\s*"
    r"(k|lakh|lakhs|lpa|per month|per year|monthly|yearly|annum)",
    re.IGNORECASE
)




# =========================================================
# MAIN FILTER DETECTOR
# =========================================================

def detect_filters(text: str, entity_cache) -> dict:
    """
    Extract ONLY dynamic placeholders defined in data.json:
        - company
        - role
        - location
        - time_range
        - number (if explicitly mentioned)
        - salary_amount
        - salary_period
    """

    text = text.lower()
    filters = {}

    # -----------------------------------------------------
    # 7️⃣ SUPERLATIVE DETECTION (MOST / LEAST)
    # -----------------------------------------------------
    for label, keywords in SUPERLATIVE_MAPPINGS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                filters["superlative"] = label
                break
        if "superlative" in filters:
            break

    # -----------------------------------------------------
    # 1️⃣ COMPANY
    # -----------------------------------------------------
    company = entity_cache.match_company(text)
    if company:
        filters["company"] = company

    # -----------------------------------------------------
    # 2️⃣ ROLE
    # -----------------------------------------------------
    role = entity_cache.match_role(text)
    if role:
        if role in ["internship", "internships"]:
            filters["role"] = "intern"
        else:
            filters["role"] = role

    # -----------------------------------------------------
    # 3️⃣ LOCATION
    # -----------------------------------------------------
    location = entity_cache.match_location(text)
    if location:
        filters["location"] = location

    # -----------------------------------------------------
    # 4️⃣ RELATIVE TIME WITH NUMBER (Highest Priority)
    # -----------------------------------------------------
    relative_match = RELATIVE_TIME_PATTERN.search(text)
    relative_time_detected = False

    if relative_match:
        direction = relative_match.group(1).lower()
        number = int(relative_match.group(2))

        if direction in ["last", "past"]:
            filters["time_range"] = "PAST"
        elif direction == "next":
            filters["time_range"] = "FUTURE"

        filters["number"] = number
        relative_time_detected = True

    else:
        # -------------------------------------------------
        # 5️⃣ Semantic Time Bucket Matching
        # -------------------------------------------------
        for mapped_value, phrases in TIME_MAPPINGS.items():
            for phrase in phrases:
                if re.search(rf"\b{re.escape(phrase)}\b", text):
                    filters["time_range"] = mapped_value
                    break
            if "time_range" in filters:
                break

    # -----------------------------------------------------
    # 6️⃣ SALARY EXTRACTION (ONLY if NOT relative time)
    # -----------------------------------------------------
    if not relative_time_detected:

        salary_match = SALARY_PATTERN.search(text)

        if salary_match:
            amount = float(salary_match.group(2))
            unit = salary_match.group(3).lower()

            # Normalize amount
            if unit in ["lakh", "lakhs", "lpa"]:
                amount *= 100000
                filters["salary_period"] = "year"

            elif unit in ["annum", "yearly", "per year"]:
                filters["salary_period"] = "year"

            elif unit in ["monthly", "per month","stipend"]:
                filters["salary_period"] = "month"

            elif unit == "k":
                amount *= 1000

            filters["salary_amount"] = amount

            # -----------------------------------------------------
            # SALARY OPERATOR DETECTION
            # -----------------------------------------------------

            if "salary_amount" in filters:

                if re.search(r"\b(around|near|nearby|near to)\b", text):
                    filters["salary_mode"] = "RANGE"

                elif re.search(r"\b(above|greater than|more than|over)\b", text):
                    filters["salary_mode"] = "GT"

                elif re.search(r"\b(below|less than|under)\b", text):
                    filters["salary_mode"] = "LT"

                else:
                    filters["salary_mode"] = "EXACT"
        # -----------------------------------------------------
        # 7️⃣ SALARY PERIOD WITHOUT NUMBER
        # -----------------------------------------------------

        if "salary_period" not in filters:
            if re.search(r"\bmonthly\b|\bper month\b|\bmonth\b|\bstipend\b", text):
                filters["salary_period"] = "month"

            elif re.search(r"\byearly\b|\bper year\b|\bannum\b|\blpa\b", text):
                filters["salary_period"] = "year"

        

    return filters