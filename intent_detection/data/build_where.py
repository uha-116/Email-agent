from typing import Any, Mapping


ALLOWED_TIME_RANGES = {
    "FUTURE",
    "PAST",
    "THIS_WEEK",
    "RECENT",
    "TODAY",
    "TOMORROW",
    "YESTERDAY",
    "MISSED",
}


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_where(
    filters: Mapping[str, Any] | None,
    capability: str | None
) -> str:

    if not filters:
        return ""

    conditions = []

    # Choose correct time column
    if capability.upper() in ("OPPORTUNITY", "APPLICATION_STATUS"):
        time_column = "o.last_updated_at"
    elif capability.upper() == "LINKEDIN_STATUS":
        time_column = "e.received_at"
    else:
        time_column = "COALESCE(o.event_date, o.deadline)"

    for key, value in filters.items():

        if value is None:
            continue

        # -------------------------------------------------
        # BASIC FILTERS
        # -------------------------------------------------

        if key == "company":
            conditions.append(f"o.company ILIKE {_quote(value)}")

        elif key == "role":
            if isinstance(value, list):
                role_conditions = [
                    f"o.role ILIKE {_quote('%' + v + '%')}"
                    for v in value
                ]
                conditions.append("(" + " OR ".join(role_conditions) + ")")
            else:
                conditions.append(f"o.role ILIKE {_quote('%' + value + '%')}")
        
        # -------------------------------------------------
        # ROLE EXCLUDE FILTER (SIMPLE VERSION)
        # -------------------------------------------------

        elif key == "role_exclude":
            conditions.append(
                f"o.role NOT ILIKE {_quote('%' + value + '%')}"
            )

        elif key == "location":
            conditions.append(f"o.location ILIKE {_quote('%' + value + '%')}")

        elif key == "pipeline_stage":
            if isinstance(value, list):
                stages = ", ".join(_quote(v) for v in value)
                conditions.append(f"o.pipeline_stage IN ({stages})")
            else:
                conditions.append(f"o.pipeline_stage = {_quote(value)}")

        elif key == "action_required":
            conditions.append(
                f"o.action_required = {'TRUE' if value else 'FALSE'}"
            )

        # -------------------------------------------------
        # TIME FILTERS
        # -------------------------------------------------

        elif key == "time_range":

            tr = value.upper()

            if tr not in ALLOWED_TIME_RANGES:
                continue

            if tr == "TODAY":
                conditions.append(f"{time_column} = CURRENT_DATE")

            elif tr == "TOMORROW":
                conditions.append(
                    f"{time_column} = CURRENT_DATE + INTERVAL '1 day'"
                )

            elif tr == "YESTERDAY":
                conditions.append(
                    f"{time_column} = CURRENT_DATE - INTERVAL '1 day'"
                )

            elif tr == "FUTURE":
                conditions.append(f"{time_column} > CURRENT_DATE")

            elif tr == "PAST":
                conditions.append(f"{time_column} < CURRENT_DATE")

            elif tr in ("THIS_WEEK", "RECENT"):
                conditions.append(
                    f"{time_column} >= CURRENT_DATE - INTERVAL '7 days'"
                )

            elif tr == "MISSED":
                conditions.append(f"{time_column} < CURRENT_DATE")

        elif key == "number":
            conditions.append(
                f"{time_column} >= CURRENT_DATE - INTERVAL '{int(value)} days'"
            )

        # -------------------------------------------------
        # SALARY FILTERS
        # -------------------------------------------------

        elif key == "salary_amount":

            mode = filters.get("salary_mode", "EXACT")
            value = float(value)

            if mode == "RANGE":
                tolerance = 0.10
                lower = value * (1 - tolerance)
                upper = value * (1 + tolerance)
                conditions.append(
                    f"o.salary_amount BETWEEN {lower} AND {upper}"
                )

            elif mode == "GT":
                conditions.append(f"o.salary_amount > {value}")

            elif mode == "LT":
                conditions.append(f"o.salary_amount < {value}")

            else:
                conditions.append(f"o.salary_amount = {value}")

        elif key == "salary_period":
            conditions.append(f"o.salary_period = {_quote(value)}")

        elif key == "salary_exist":
            if value:
                conditions.append("o.salary_amount IS NOT NULL")
            else:
                conditions.append("o.salary_amount IS NULL")

        # -------------------------------------------------
        # LOCATION EXISTENCE
        # -------------------------------------------------

        elif key == "location_exist":
            if value:
                conditions.append("o.location IS NOT NULL")
            else:
                conditions.append("o.location IS NULL")

        # -------------------------------------------------
        # EXPERIENCE FILTERS
        # -------------------------------------------------

        
        elif key == "fresher":
            if value:
                conditions.append(
                    "("
                    "o.min_experience_years = 0 "
                    "OR "
                    "COALESCE(o.min_experience_years, o.max_experience_years) IS NULL"
                    ")"
                )
            else:
                conditions.append(
                    "o.min_experience_years >0"
                )


        elif key == "experience_exist":
            if value:
                conditions.append(
                    "COALESCE(o.min_experience_years, "
                    "o.max_experience_years) IS NOT NULL"
                )
            else:
                conditions.append(
                    "COALESCE(o.min_experience_years, "
                    "o.max_experience_years) IS NULL"
                )
        
        

        # -------------------------------------------------
        # LINKEDIN FILTERS
        # -------------------------------------------------

        elif key == "interaction_type":
            values = ", ".join(_quote(v) for v in value)
            conditions.append(f"le.interaction_type IN ({values})")

        elif key == "person_company":
            conditions.append(
                f"le.person_company ILIKE {_quote('%' + value + '%')}"
            )

        elif key == "person_name":
            conditions.append(
                f"le.person_name ILIKE {_quote('%' + value + '%')}"
            )

        elif key == "requires_follow_up":
            conditions.append(
                f"le.requires_follow_up = {'TRUE' if value else 'FALSE'}"
            )

    if not conditions:
        return ""

    return "WHERE " + " AND ".join(conditions)