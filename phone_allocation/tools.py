from __future__ import annotations

import json

from langchain_core.tools import tool

from phone_allocation import servicenow
from phone_allocation.config import Settings
from phone_allocation.db import list_available_numbers_for_site, reserve_phone_number_in_inventory
from phone_allocation.ldap_people import fetch_ldap_person_row


def build_tools(settings: Settings):
    @tool
    def get_employee_details(userid: str) -> str:
        """Fetch employee from Postgres `ldap_people` by `userid`."""
        try:
            row = fetch_ldap_person_row(userid, settings)
            if row:
                return json.dumps(row, default=str)
            return json.dumps({"error": "not_found", "userid": userid})
        except Exception as exc:
            return json.dumps(
                {"error": "lookup_failed", "userid": userid, "detail": str(exc)}
            )

    @tool
    def get_available_phone_numbers(location: str, building: str) -> str:
        """List available numbers in `phone_numbers`. `location` must match the employee's `city` value."""
        numbers = list_available_numbers_for_site(location, building)
        return json.dumps(
            {"location": location, "building": building, "numbers": numbers},
            default=str,
        )

    @tool
    def reserve_phone_number(number: str) -> str:
        """Reserve a number in Postgres `phone_numbers` (must be status available)."""
        out = reserve_phone_number_in_inventory(number)
        return json.dumps(out)

    @tool
    def create_servicenow_ticket(summary: str, details: str) -> str:
        """Escalate when allocation cannot complete. ServiceNow is not wired unless configured."""
        ticket = servicenow.create_ticket({"summary": summary, "details": details})
        return json.dumps(ticket, default=str)

    return [
        get_employee_details,
        get_available_phone_numbers,
        reserve_phone_number,
        create_servicenow_ticket,
    ]
