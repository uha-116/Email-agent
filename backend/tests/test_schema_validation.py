import pytest

from backend.error_handling import LLMValidationError
from backend.email_analyser.schema_validation import validate_schema, validate_single_item


def valid_job_payload():
    return {
        "index": 0,
        "payload": {
            "email_type": "JOB_PIPELINE",
            "sender": "Acme",
            "subject": "Interview",
            "opportunities": [
                {
                    "company": "Acme",
                    "role": "Engineer",
                    "location": "Bangalore",
                    "salary_amount": 1000000,
                    "salary_period": "year",
                    "min_experience_years": 0,
                    "max_experience_years": 2,
                    "pipeline_stage": "INTERVIEW",
                    "action_required": True,
                    "deadline": "2026-03-30",
                    "event_date": "2026-03-29T10:30:00",
                    "other_important_details": {},
                }
            ],
        },
    }


def test_validate_single_item_accepts_valid_job_pipeline(scenario_printer):
    assert validate_single_item(valid_job_payload()) is True
    scenario_printer(
        "Valid job payload",
        "No error; fully valid JOB_PIPELINE payload",
        "Validation should pass",
        "Payload validated successfully",
    )


def test_validate_single_item_rejects_missing_email_type(scenario_printer):
    with pytest.raises(LLMValidationError, match="Missing email_type"):
        validate_single_item({"payload": {}})
    scenario_printer(
        "Missing email_type",
        "Payload omits email_type",
        "Validation should reject the item",
        "LLMValidationError raised for missing email_type",
    )


def test_validate_single_item_rejects_invalid_salary_pair(scenario_printer):
    item = valid_job_payload()
    item["payload"]["opportunities"][0]["salary_period"] = None

    with pytest.raises(LLMValidationError, match="salary_amount and salary_period"):
        validate_single_item(item)
    scenario_printer(
        "Invalid salary pair",
        "salary_amount present while salary_period is null",
        "Validation should reject mismatched salary fields",
        "LLMValidationError raised for inconsistent salary pairing",
    )


def test_validate_single_item_rejects_invalid_types(scenario_printer):
    item = valid_job_payload()
    item["payload"]["opportunities"][0]["action_required"] = "yes"

    with pytest.raises(LLMValidationError, match="action_required must be boolean"):
        validate_single_item(item)
    scenario_printer(
        "Invalid field type",
        "action_required is a string instead of bool",
        "Validation should reject incorrect boolean type",
        "LLMValidationError raised for action_required type mismatch",
    )


def test_validate_schema_returns_partial_valid_partial_invalid(scenario_printer):
    good = valid_job_payload()
    bad = valid_job_payload()
    bad["payload"]["opportunities"][0]["pipeline_stage"] = "UNKNOWN"

    valid_items, invalid_items = validate_schema([good, bad])

    assert valid_items == [good]
    assert len(invalid_items) == 1
    scenario_printer(
        "Partial valid / partial invalid batch",
        "One item valid, one item has invalid pipeline_stage",
        "Batch validator should return split valid/invalid lists",
        "One valid item returned and one invalid item recorded",
    )
    assert invalid_items[0]["item"] == bad
    assert "pipeline_stage" in invalid_items[0]["error"]


def test_validate_schema_accepts_ignore_payload(scenario_printer):
    valid_items, invalid_items = validate_schema(
        [{"index": 0, "payload": {"email_type": "IGNORE", "subject": "newsletter"}}]
    )

    assert len(valid_items) == 1
    assert invalid_items == []
    scenario_printer(
        "IGNORE payload validation",
        "Valid IGNORE payload",
        "Validator should accept it",
        "IGNORE payload was treated as valid",
    )


def test_linkedin_prompt_shape_is_currently_accepted(scenario_printer):
    linkedin_prompt_payload = {
        "index": 0,
        "payload": {
            "email_type": "LINKEDIN_NETWORKING",
            "sender": "LinkedIn",
            "subject": "Message from recruiter",
            "linkedin_event": {
                "person_name": "A",
                "person_title": "Recruiter",
                "person_company": "Acme",
                "interaction_type": "RECRUITER_MESSAGE",
                "requires_follow_up": True,
            },
        },
    }

    valid_items, invalid_items = validate_schema([linkedin_prompt_payload])

    assert valid_items == [linkedin_prompt_payload]
    assert invalid_items == []
    scenario_printer(
        "LinkedIn schema acceptance",
        "Payload uses linkedin_event shape from prompt/db flow",
        "Current validator should accept linkedin_event object",
        "Payload validated successfully with no invalid items",
    )
