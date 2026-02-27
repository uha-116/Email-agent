from future import annotations

from typing import Any, Iterable, Mapping

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
"last_updated_at",
"details",
}

ALLOWED_PIPELINE_STAGES = {
"OPPORTUNITY_FOUND",
"APPLIED",
"SHORTLISTED",
"ASSESSMENT",
"INTERVIEW",
"SELECTED",
"REJECTED",
}

ALLOWED_TIME_RANGES = {"FUTURE", "PAST", "THIS_WEEK", "RECENT"}
ALLOWED_DEADLINE_STATUS = {"UPCOMING", "MISSED"}
ALLOWED_EVENT_DATE = {"TODAY", "TOMORROW", "EXISTS"}
ALLOWED_FILTERS = {
"company",
"role",
"location",
"pipeline_stage",
"action_required",
"salary_exists",
"time_range",
"deadline_status",
"event_date",
}

def sanitize_column(column: str) -> str:
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column name: {column}")
    return column

def _quote_literal(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected string value")
    return "'" + value.replace("'", "''") + "'"

def _column_expr(column: str) -> str:
    sanitize_column(column)
    return "d.details" if column == "details" else f"o.{column}"

def _non_empty_str(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if not value:
    raise ValueError(f"{field} must be a non-empty string")
    return value

def _bool_value(value: Any, field: str) -> bool:
if not isinstance(value, bool):
raise ValueError(f"{field} must be boolean")
return value

def _string_list(values: Any, field: str) -> list[str]:
if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
raise ValueError(f"{field} must be a list of strings")
items = []
for item in values:
if not isinstance(item, str):
raise ValueError(f"{field} must contain only strings")
item = item.strip()
if not item:
raise ValueError(f"{field} cannot contain empty values")
items.append(item)
if not items:
raise ValueError(f"{field} cannot be empty")
return items

def build_where(filters: Mapping[str, Any] | None) -> str:
if not filters:
return ""

if not isinstance(filters, Mapping):
    raise ValueError("filters must be a mapping")

unknown_keys = set(filters.keys()) - _ALLOWED_FILTERS
if unknown_keys:
    raise ValueError(f"Unsupported filters: {sorted(unknown_keys)}")

conditions: list[str] = []

for key, value in filters.items():
    if value is None:
        continue

    if key == "company":
        company = _non_empty_str(value, "company")
        conditions.append(f"o.company = {_quote_literal(company)}")

    elif key == "role":
        role = _non_empty_str(value, "role")
        conditions.append(f"o.role ILIKE {_quote_literal(f'%{role}%')}")

    elif key == "location":
        location = _non_empty_str(value, "location")
        conditions.append(f"o.location ILIKE {_quote_literal(f'%{location}%')}")

    elif key == "pipeline_stage":
        stages = _string_list(value, "pipeline_stage")
        invalid = [s for s in stages if s not in _ALLOWED_PIPELINE_STAGES]
        if invalid:
            raise ValueError(f"Invalid pipeline_stage values: {invalid}")
        stage_sql = ", ".join(_quote_literal(stage) for stage in stages)
        conditions.append(f"o.pipeline_stage IN ({stage_sql})")

    elif key == "action_required":
        action_required = _bool_value(value, "action_required")
        conditions.append(f"o.action_required = {'TRUE' if action_required else 'FALSE'}")

    elif key == "salary_exists":
        salary_exists = _bool_value(value, "salary_exists")
        if salary_exists:
            conditions.append("o.salary_amount IS NOT NULL")

    elif key == "time_range":
        time_range = _non_empty_str(value, "time_range").upper()
        if time_range not in _ALLOWED_TIME_RANGES:
            raise ValueError(f"Invalid time_range: {time_range}")
        if time_range == "FUTURE":
            conditions.append("COALESCE(o.event_date, o.deadline) > CURRENT_DATE")
        elif time_range == "PAST":
            conditions.append("COALESCE(o.event_date, o.deadline) < CURRENT_DATE")
        elif time_range in {"THIS_WEEK", "RECENT"}:
            conditions.append("o.last_updated_at >= CURRENT_DATE - INTERVAL '7 days'")

    elif key == "deadline_status":
        deadline_status = _non_empty_str(value, "deadline_status").upper()
        if deadline_status not in _ALLOWED_DEADLINE_STATUS:
            raise ValueError(f"Invalid deadline_status: {deadline_status}")
        if deadline_status == "UPCOMING":
            conditions.append("COALESCE(o.deadline, o.event_date) >= CURRENT_DATE")
        elif deadline_status == "MISSED":
            conditions.append("COALESCE(o.deadline, o.event_date) < CURRENT_DATE")

    elif key == "event_date":
        event_date = _non_empty_str(value, "event_date").upper()
        if event_date not in _ALLOWED_EVENT_DATE:
            raise ValueError(f"Invalid event_date filter: {event_date}")
        if event_date == "TODAY":
            conditions.append("DATE(COALESCE(o.event_date, o.deadline)) = CURRENT_DATE")
        elif event_date == "TOMORROW":
            conditions.append("DATE(COALESCE(o.event_date, o.deadline)) = CURRENT_DATE + INTERVAL '1 day'")
        elif event_date == "EXISTS":
            conditions.append("COALESCE(o.event_date, o.deadline) IS NOT NULL")

if not conditions:
    return ""

return "WHERE " + " AND ".join(conditions)
def build_sql(query_json: Mapping[str, Any]) -> str:
if not isinstance(query_json, Mapping):
raise ValueError("query_json must be a mapping")

projection_raw = query_json.get("projection", [])
if projection_raw is None:
    projection_raw = []
if not isinstance(projection_raw, list):
    raise ValueError("projection must be a list")

projection = list(projection_raw)
operation = query_json.get("operation")
group_by = query_json.get("group_by")
limit = query_json.get("limit")
filters = query_json.get("filters", {})

if not isinstance(operation, str):
    raise ValueError("operation must be a string")
operation = operation.upper()

if not isinstance(filters, Mapping):
    raise ValueError("filters must be a mapping")

join_details = "details" in projection or group_by == "details"

base = "FROM opportunities o"
if join_details:
    base += " LEFT JOIN opportunity_details d ON o.id = d.opportunity_id"

where_clause = build_where(filters)

if operation == "COUNT":
    return f"""
SELECT COUNT(*) AS total
{base}
{where_clause};
""".strip()

if operation == "LIST":
    if "company" not in projection:
        projection.insert(0, "company")
    if "role" not in projection:
        projection.insert(1, "role")

    select_parts = [_column_expr(col) for col in projection]
    projection_sql = ", ".join(select_parts)

    sql = f"""
SELECT {projection_sql}
{base}
{where_clause}
ORDER BY o.last_updated_at DESC
""".strip()

    if limit is not None:
        if isinstance(limit, bool):
            raise ValueError("limit must be an integer")
        limit_int = int(limit)
        if limit_int <= 0:
            raise ValueError("limit must be greater than 0")
        sql += f"\nLIMIT {limit_int}"

    return sql + ";"

if operation == "BOOLEAN":
    return f"""
SELECT CASE
WHEN COUNT(*) > 0 THEN TRUE
ELSE FALSE
END AS result
{base}
{where_clause};
""".strip()

if operation == "SUMMARY":
    if not isinstance(group_by, str):
        raise ValueError("group_by is required for SUMMARY")
    group_by_expr = _column_expr(group_by)
    return f"""
SELECT {group_by_expr}, COUNT(*) AS total
{base}
{where_clause}
GROUP BY {group_by_expr}
ORDER BY total DESC;
""".strip()

raise ValueError(f"Unsupported operation: {operation}")

