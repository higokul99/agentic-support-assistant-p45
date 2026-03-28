from __future__ import annotations

import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from phone_allocation.agent_runner import run_assignment, run_chat
from phone_allocation.config import get_settings
from phone_allocation.db import init_db, insert_log, record_allocation
from phone_allocation.ldap_people import describe_ldap_people_table

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _extract_userid_from_chat(message: str) -> str | None:
    m = re.search(r"\b(EMP\d+)\b", message, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m = re.search(
        r"(?:userid|user\s*id|user|login)\s*[:=#]\s*([A-Za-z0-9._@+-]+)",
        message,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    return None


def _extract_phone_if_reserved_summary(msg: str) -> str | None:
    if "reserved" not in msg.lower():
        return None
    for m in re.finditer(r"\d[\d\-\s\u00a0]{5,18}\d", msg):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) >= 8:
            return digits
    return None


def _require_groq(settings):
    if not settings.groq_api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured (set in environment or .env).",
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Phone allocation agent API", lifespan=lifespan)


class AssignRequest(BaseModel):
    userid: str = Field(..., min_length=1, description="Employee id (ldap_people id column)")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Natural language request to the agent")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema/ldap_people")
def ldap_people_schema():
    """Verify `ldap_people` (or configured table): columns, types, row count."""
    settings = get_settings()
    try:
        return describe_ldap_people_table(settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def chat_ui():
    path = _STATIC_DIR / "chat.html"
    if not path.is_file():
        return HTMLResponse("<p>Chat UI missing.</p>", status_code=404)
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.post("/chat")
def chat(req: ChatRequest):
    settings = get_settings()
    _require_groq(settings)
    try:
        out = run_chat(req.message, settings)
        if not out.get("final_message"):
            out["hint"] = (
                "Model returned no assistant text. Check Groq model/tools, "
                "or open GET /schema/ldap_people to confirm ldap_people columns match "
                "LDAP_PEOPLE_ID_COLUMN (default userid) and that city/building match phone_numbers rows."
            )
        insert_log("chat_complete", {"message": req.message[:500], **out})
        msg = out.get("final_message") or ""
        phone = _extract_phone_if_reserved_summary(msg)
        uid = _extract_userid_from_chat(req.message)
        if phone and uid:
            record_allocation(uid, phone)
        return out
    except Exception as exc:
        insert_log("chat_error", {"message": req.message[:500], "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/assign")
def assign(req: AssignRequest):
    settings = get_settings()
    _require_groq(settings)
    try:
        out = run_assignment(req.userid, settings)
        insert_log("assign_complete", out)
        msg = out.get("final_message") or ""
        phone = _extract_phone_if_reserved_summary(msg)
        if phone:
            record_allocation(req.userid, phone)
        return out
    except Exception as exc:
        insert_log("assign_error", {"userid": req.userid, "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc
