from __future__ import annotations

import re
from typing import Any

from sqlalchemy import inspect, select, text

from phone_allocation.config import Settings
from phone_allocation.db import LdapPersonRow, _engine_session

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _require_ident(name: str, label: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"invalid {label}: {name!r} (use letters, digits, underscore)")
    return name


def _row_to_agent_dict(row: LdapPersonRow) -> dict:
    """Expose directory row to the LLM; `phone_numbers.location` matches `city`."""
    d = {c.name: getattr(row, c.name) for c in LdapPersonRow.__table__.columns}
    d["location"] = d.get("city")
    return d


def describe_ldap_people_table(settings: Settings) -> dict[str, Any]:
    """Inspect ldap_people (or configured table name) for debugging / verification."""
    engine, _ = _engine_session()
    table = _require_ident(settings.ldap_people_table, "table")
    insp = inspect(engine)
    names = insp.get_table_names(schema="public")
    if table not in names:
        return {
            "table": table,
            "exists": False,
            "columns": [],
            "row_count": None,
            "public_tables_sample": sorted(names)[:40],
        }
    cols = insp.get_columns(table, schema="public")
    with engine.connect() as conn:
        cnt = conn.execute(text(f"SELECT COUNT(*) AS c FROM {table}")).scalar()
    return {
        "table": table,
        "exists": True,
        "id_column_setting": settings.ldap_people_id_column,
        "orm_model": "LdapPersonRow in db.py",
        "columns": [{"name": c["name"], "type": str(c["type"])} for c in cols],
        "row_count": int(cnt or 0),
    }


def fetch_ldap_person_row(directory_key: str, settings: Settings) -> dict | None:
    """Load one person by `userid` (default). Supports legacy table/column via raw SQL."""
    if (
        settings.ldap_people_table == "ldap_people"
        and settings.ldap_people_id_column == "userid"
    ):
        _, SessionLocal = _engine_session()
        with SessionLocal() as session:
            row = session.scalar(
                select(LdapPersonRow).where(LdapPersonRow.userid == directory_key)
            )
        if not row:
            return None
        return _row_to_agent_dict(row)

    table = _require_ident(settings.ldap_people_table, "table")
    id_col = _require_ident(settings.ldap_people_id_column, "id_column")
    engine, _ = _engine_session()
    sql = text(f"SELECT * FROM {table} WHERE {id_col} = :eid LIMIT 1")
    with engine.connect() as conn:
        raw = conn.execute(sql, {"eid": directory_key}).mappings().first()
    if not raw:
        return None
    d = dict(raw)
    if "city" in d and "location" not in d:
        d["location"] = d.get("city")
    return d
