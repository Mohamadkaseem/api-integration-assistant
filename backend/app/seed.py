"""Starter data: your three real-world test projects.

Added only when the database has no projects yet, so your own edits are never overwritten.
"""

from sqlmodel import Session, select

from app.models.project import Project, ProjectStatus

STARTER_PROJECTS = [
    dict(
        name="Project A: Zwayam ↔ Zoho Sign offer letters",
        source_app="Zwayam",
        target_app="Zoho Sign",
        status=ProjectStatus.planning,
        requirement=(
            "When an offer letter is created in Zwayam, send it to Zoho Sign. "
            "The company signatory (Impetus) signs first. After the signatory signs, update the "
            "candidate status in Zwayam and send the document to the candidate. "
            "When the candidate signs, update the candidate status in Zwayam to Offer Accepted."
        ),
        notes="Two signing stages, each followed by a Zwayam status update.",
    ),
    dict(
        name="Project B: HubSpot → Zoho CRM company sync",
        source_app="HubSpot",
        target_app="Zoho CRM",
        status=ProjectStatus.planning,
        requirement=(
            "When a new company is created in HubSpot, retrieve the company data and search "
            "Zoho CRM Accounts. If the account exists, update it. Otherwise, create a new "
            "account. Log the result."
        ),
        notes="Zoho upsert can match on Account_Name (duplicate check field).",
    ),
    dict(
        name="Project C: Zoho Sign API testing",
        source_app="",
        target_app="Zoho Sign",
        status=ProjectStatus.planning,
        requirement=(
            "Configure OAuth for Zoho Sign, obtain an access token, refresh it when required, "
            "test API requests, analyze errors and generate request documentation."
        ),
        notes="Use a sandbox / test account.",
    ),
]


def seed_starter_projects(session: Session) -> None:
    if session.exec(select(Project)).first() is not None:
        return
    for data in STARTER_PROJECTS:
        session.add(Project(**data))
    session.commit()
