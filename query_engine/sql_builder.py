from typing import Any, Mapping
from query_engine.build_where import build_where


ALLOWED_COLUMNS = {
    "id",
    "company",
    "role",
    "pipeline_stage",
    "action_required",
    "deadline",
    "event_date",
    "location",
    "salary_amount",
    "salary_period",
    "min_experience_years",
    "max_experience_years",
    "last_updated_at",
    "details",
    "interaction_type",
    "person_name",
    "person_title",
    "person_company",
    "subject",
    "sender",
    "received_at",
    "gmail_message_id"
}


def _col(column: str, alias: str) -> str:
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column: {column}")

    if column == "details":
        return "d.details"

    if column == "gmail_message_id":
        return "e.gmail_message_id"

    return f"{alias}.{column}"


def build_sql(query_json: Mapping[str, Any]) -> dict[str, str]:

    projection = list(query_json.get("projection", []))
    group_by = query_json.get("group_by")
    filters = query_json.get("filters", {})
    capability = query_json.get("capability")

    # -------------------------------------------------
    # BASE SWITCH
    # -------------------------------------------------

    if capability == "LINKEDIN_STATUS":
        base = """
FROM linkedin_events le
LEFT JOIN emails e ON le.email_id = e.id
""".strip()
        sort_column = "e.received_at"
        base_alias = "le"
    else:
        base = """
                FROM opportunities o
                LEFT JOIN emails e ON o.email_id = e.id
                """.strip()
        sort_column = "o.last_updated_at"
        base_alias = "o"
        # -------------------------------------------------
        # DEADLINE SUPERLATIVE LOGIC
        # -------------------------------------------------

        if capability == "DEADLINE_STATUS" and filters.get("superlative"):
            sort_column = "COALESCE(o.deadline, o.event_date)"

    where_clause = build_where(filters, capability)

    superlative = filters.get("superlative")

    # -------------------------------------------------
    # DETAILS JOIN LOGIC
    # -------------------------------------------------

    needs_details_join = (
        "details" in projection or group_by == "details"
    )

    if needs_details_join:
        base += "\nLEFT JOIN opportunity_details d ON o.id = d.opportunity_id"

    # =====================================================
    # COUNT QUERY
    # =====================================================

    if superlative and not group_by:
        count_sql = None

    elif group_by:

        group_col = _col(group_by, base_alias)

        null_filter = f"{group_col} IS NOT NULL"

        if where_clause:
            where_clause += f" AND {null_filter}"
        else:
            where_clause = f"WHERE {null_filter}"

        direction = "DESC"
        limit_clause = ""

        if superlative == "LEAST":
            direction = "ASC"

        if superlative:
            limit_clause = "\nLIMIT 1"

        count_sql = f"""
SELECT {group_col}, COUNT(*) AS total
{base}
{where_clause}
GROUP BY {group_col}
ORDER BY total {direction}{limit_clause};
""".strip()

    else:

        count_sql = f"""
SELECT COUNT(*) AS total
{base}
{where_clause};
""".strip()

    # =====================================================
    # LIST QUERY
    # =====================================================

    if not projection:
        projection = ["company", "role"]

    # Inner select columns (with table alias)
    select_columns = [
        _col(col, base_alias)
        for col in projection
        if col in ALLOWED_COLUMNS
    ]

    select_sql = ", ".join(select_columns)

    # Outer select columns (without table alias)
    outer_select = ", ".join(
        col.split(".")[-1] for col in select_columns
    )

    if group_by:

        if superlative:

            direction = "DESC" if superlative == "MOST" else "ASC"

            list_sql = f"""
    SELECT {select_sql}
    {base}
    WHERE {base_alias}.{group_by} = (
        SELECT {base_alias}.{group_by}
        {base}
        WHERE {base_alias}.{group_by} IS NOT NULL
        GROUP BY {base_alias}.{group_by}
        ORDER BY COUNT(*) {direction}
        LIMIT 1
    )
    ORDER BY {sort_column} DESC
    LIMIT 15;
    """.strip()

        else:

            group_col_inner = _col(group_by, base_alias)
            sort_col_name = sort_column.split(".")[-1]

            list_sql = f"""
    SELECT {outer_select}
    FROM (
        SELECT
            {select_sql},
            {sort_column},
            ROW_NUMBER() OVER (
                PARTITION BY {group_col_inner}
                ORDER BY {sort_column} DESC
            ) AS rn
        {base}
        {where_clause}
    ) sub
    WHERE rn <= 7
    ORDER BY sub.{group_by}, sub.{sort_col_name} DESC;
    """.strip()

    else:

        if superlative and capability == "SALARY_STATUS":

            order_col = f"{base_alias}.salary_amount"
            direction = "DESC" if superlative == "MOST" else "ASC"

            if where_clause:
                where_clause += f" AND {order_col} IS NOT NULL"
            else:
                where_clause = f"WHERE {order_col} IS NOT NULL"

            list_sql = f"""
    SELECT {select_sql}
    {base}
    {where_clause}
    ORDER BY {order_col} {direction}
    LIMIT 1;
    """.strip()

        else:
            limit_clause = ""

            if filters.get("superlative") == "LATEST":
                limit_clause = "\nLIMIT 1"
            else:
                limit_clause = "\nLIMIT 15"


            list_sql = f"""
        SELECT {select_sql}
        {base}
        {where_clause}
        ORDER BY {sort_column} DESC{limit_clause};
        """.strip()

    return {
        "count_sql": count_sql,
        "list_sql": list_sql,
    }