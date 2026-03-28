from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from phone_allocation.config import Settings
from phone_allocation.tools import build_tools

SYSTEM_PROMPT = """You are an IT automation agent for phone number allocation.

Steps:
1. Fetch employee with get_employee_details: pass their ldap_people `userid`.
2. If missing, call create_servicenow_ticket (escalation log; ITSM may be not_configured) then stop.
3. Require `city` and `building` (use `location` from the tool response — it equals `city`).
4. Call get_available_phone_numbers(location, building) where location is the exact `city` string and building the exact `building` string.
5. If the list is empty, create_servicenow_ticket and stop.
6. Choose the best available number (prefer the first listed number for that site).
7. Call reserve_phone_number with that number.
8. Reply with a clear Final summary: userid, fullname, chosen number, reservation status.

Directory columns: userid, fullname, title, emp_type, building, city, manager_id; use `location` (same as city) and `building` for get_available_phone_numbers."""


def _build_agent(settings: Settings):
    tools = build_tools(settings)
    llm = ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key or None,
        temperature=0,
    )
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


def _stringify_content(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif "text" in block:
                    parts.append(str(block["text"]))
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content).strip()


def _final_assistant_text(result: dict) -> str:
    messages = result.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            text = _stringify_content(msg.content)
            if text:
                return text
    return ""


def run_assignment(userid: str, settings: Settings) -> dict:
    agent = _build_agent(settings)
    user_text = (
        f"Assign a corporate phone number to userid={userid!r}. "
        "Follow the system steps and use tools until the number is reserved or a ticket is filed."
    )
    result = agent.invoke({"messages": [HumanMessage(content=user_text)]})
    messages = result.get("messages") or []
    return {
        "userid": userid,
        "final_message": _final_assistant_text(result),
        "message_count": len(messages),
    }


def run_chat(user_message: str, settings: Settings) -> dict:
    agent = _build_agent(settings)
    result = agent.invoke({"messages": [HumanMessage(content=user_message.strip())]})
    messages = result.get("messages") or []
    return {
        "final_message": _final_assistant_text(result),
        "message_count": len(messages),
    }
