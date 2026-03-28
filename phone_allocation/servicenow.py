"""ServiceNow: no fake tickets. Wire API via settings when ready."""


def create_ticket(data: dict) -> dict:
    from phone_allocation.config import get_settings

    s = get_settings()
    if s.servicenow_instance_url and s.servicenow_username and s.servicenow_password:
        return {
            "status": "not_implemented",
            "message": "REST client not implemented; configure credentials and add HTTP call here.",
            "payload": data,
        }
    return {
        "status": "not_configured",
        "message": (
            "ServiceNow is not configured (set SERVICENOW_INSTANCE_URL and credentials in .env). "
            "Record this escalation in your ITSM manually."
        ),
        "summary": data.get("summary"),
        "details": data.get("details"),
    }
