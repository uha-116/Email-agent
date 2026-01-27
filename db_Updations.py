STAGE_PRIORITY = {
    "OPPORTUNITY_FOUND": 1,
    "APPLIED": 2,
    "SHORTLISTED": 3,
    "ASSESSMENT": 4,
    "INTERVIEW": 5,
    "SELECTED": 6,
    "REJECTED": 7
}


def get_stage_priority(stage: str) -> int:
    return STAGE_PRIORITY.get(stage, 0)


def decide_insert_or_update(
    cur,
    *,
    company: str,
    role: str | None,
    new_stage: str
):
    """
    Decides whether to INSERT or UPDATE an opportunity.

    Logic:
    - Find all matching records (company + role if role exists else company)
    - Ignore records already at higher stage
    - From remaining, pick the closest lower stage
    - If multiple candidates → AMBIGUOUS
    """

    new_priority = get_stage_priority(new_stage)

    # ---------------------------
    # 1. Fetch matching records
    # ---------------------------
    if role:
        cur.execute(
            """
            SELECT id, pipeline_stage
            FROM opportunities
            WHERE company = %s AND role = %s;
            """,
            (company, role)
        )
    else:
        cur.execute(
            """
            SELECT id, pipeline_stage
            FROM opportunities
            WHERE company = %s;
            """,
            (company,)
        )

    rows = cur.fetchall()

    # ---------------------------
    # 2. No existing records
    # ---------------------------
    if not rows:
        return "INSERT", None

    # ---------------------------
    # 3. Classify candidates
    # ---------------------------
    lower_stage_candidates = []
    same_stage_candidates = []

    for opp_id, stage in rows:
        priority = get_stage_priority(stage)

        if priority < new_priority:
            lower_stage_candidates.append((opp_id, priority))
        elif priority == new_priority:
            same_stage_candidates.append(opp_id)
        else:
            # Higher stage exists → ignore downgrade
            pass

    # ---------------------------
    # 4. Exact stage match
    # ---------------------------
    if len(same_stage_candidates) == 1:
        return "UPDATE", same_stage_candidates[0]

    if len(same_stage_candidates) > 1:
        return "AMBIGUOUS", None

    # ---------------------------
    # 5. Closest lower stage
    # ---------------------------
    if lower_stage_candidates:
        # pick the one with highest priority < new_stage
        lower_stage_candidates.sort(key=lambda x: x[1], reverse=True)

        top_priority = lower_stage_candidates[0][1]
        best_matches = [
            opp_id for opp_id, p in lower_stage_candidates
            if p == top_priority
        ]

        if len(best_matches) == 1:
            return "UPDATE", best_matches[0]

        return "AMBIGUOUS", None

    # ---------------------------
    # 6. No valid candidate
    # ---------------------------
    return "INSERT", None
