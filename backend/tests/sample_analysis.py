"""A realistic analysis of Project B, used by tests instead of calling Claude."""

from app.ai.requirement_analyzer import RequirementAnalysis

SAMPLE_ANALYSIS = RequirementAnalysis.model_validate(
    {
        "summary": "New HubSpot companies are copied into Zoho CRM as Accounts without creating duplicates.",
        "trigger": {"event": "A new company is created", "app": "HubSpot", "detection": "unknown", "notes": ""},
        "source_app": "HubSpot",
        "target_apps": ["Zoho CRM"],
        "steps": [
            {"order": 1, "app": "HubSpot", "action": "read", "description": "Get the new company's details",
             "condition": "", "waits_for": ""},
            {"order": 2, "app": "Zoho CRM", "action": "search", "description": "Look for an existing Account",
             "condition": "", "waits_for": ""},
            {"order": 3, "app": "Zoho CRM", "action": "update", "description": "Update the existing Account",
             "condition": "only if an Account was found", "waits_for": ""},
            {"order": 4, "app": "Zoho CRM", "action": "create", "description": "Create a new Account",
             "condition": "only if no Account was found", "waits_for": ""},
            {"order": 5, "app": "Integration", "action": "log", "description": "Record the result",
             "condition": "", "waits_for": ""},
        ],
        "data_to_transfer": [
            {"name": "Company name", "from_app": "HubSpot", "to_app": "Zoho CRM", "notes": ""},
        ],
        "conditions": ["Update if the account exists, otherwise create it."],
        "status_updates": [],
        "expected_outcome": "Every HubSpot company exists exactly once as a Zoho CRM Account.",
        "assumptions": ["Matching is done on company name."],
        "clarification_questions": [
            {"question": "Which field identifies the same company in both systems?",
             "why_it_matters": "Decides how duplicates are detected.", "priority": "high"},
        ],
        "readiness": "needs_clarification",
    }
)
