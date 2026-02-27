def build_sql(intent: str, filters: list[str]) -> str | None:
    base_sql = SQL_QUERIES.get(intent)
    if not base_sql:
        return None

    conditions = []

    # ---- Time filters (generic) ----
    if "TODAY" in filters:
        conditions.append(
            "(DATE(event_date) = CURRENT_DATE OR DATE(deadline) = CURRENT_DATE)"
        )

    if "UPCOMING" in filters:
        conditions.append(
            "(event_date > CURRENT_DATE OR deadline > CURRENT_DATE)"
        )

    # ---- Assessment-specific filters ----
    if intent == "ASSESSMENTS":

        if "COMPLETED" in filters:
            conditions.append("action_required = false")

        if "PENDING" in filters:
            conditions.append("""
                action_required = true AND (
                    event_date >= CURRENT_DATE
                    OR deadline >= CURRENT_DATE
                    OR (event_date IS NULL AND deadline IS NULL)
                )
            """)

        if "MISSED" in filters:
            conditions.append("""
                action_required = true AND (
                    event_date < CURRENT_DATE
                    OR deadline < CURRENT_DATE
                )
            """)

    sql = base_sql.strip()

    if conditions:
        sql += " AND " + " AND ".join(f"({c.strip()})" for c in conditions)

    if "COUNT" in filters:
        sql = f"SELECT COUNT(*) FROM ({sql}) sub"

    return sql + ";"
