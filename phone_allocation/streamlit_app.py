import os
import certifi
import streamlit as st
from dotenv import load_dotenv

# Fix SSL FileNotFoundError issues for httpx requests on Windows
os.environ["SSL_CERT_FILE"] = certifi.where()

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

import re
def local_extract_uid(msg: str) -> str | None:
    """A slightly more generous regex extractor for Streamlit."""
    m = re.search(r"\b(EMP\d+)\b", msg, re.IGNORECASE)
    if m: return m.group(1).upper()
    m = re.search(r"(?:userid|user\s*id|user|for|login)\s*[:=#]?\s*([A-Za-z0-9._@+-]+)", msg, re.IGNORECASE)
    if m: return m.group(1)
    
    # Catch raw user IDs if they stand alone or follow a simple pattern Like first.last
    m = re.search(r"\b([a-z]+[._][a-z0-9]+)\b", msg, re.IGNORECASE)
    if m: return m.group(1)
    
    return None

from phone_allocation.config import get_settings
from phone_allocation.db import init_db, list_available_numbers_for_site, reserve_phone_number_in_inventory, record_allocation, get_active_allocation
from phone_allocation.ldap_people import fetch_ldap_person_row

# Load environment variables
load_dotenv()
settings = get_settings()

# Initialize DB for phone_allocation tools
init_db()

st.title("📞 Phone Allocation Agent")
st.write("I can help you look up employee LDAP records and fetch available phone numbers for their location automagically. Give me an employee ID, e.g. **'Check EMP001'**")

# Setup LLM with the API key loaded from .env
llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2)

def gather_context(user_query: str) -> str:
    """Extracts User ID via regex, fetches LDAP info, and iterates over to find available phone numbers database matching that LDAP record's city/building."""
    uid = local_extract_uid(user_query)
    context_text = ""
    
    if uid:
        st.session_state.current_userid = uid
        st.info(f"🔍 Extracted User ID: **{uid}**. Fetching LDAP details...")
        try:
            row = fetch_ldap_person_row(uid, settings)
            if row:
                context_text += f"\n### LDAP DATA FOR {uid}\n"
                for k, v in row.items():
                    context_text += f"- **{k}**: {v}\n"
                
                # Check for location mapping: ldap_people sometimes uses city as location.
                location = row.get("location") or row.get("city")
                building = row.get("building")
                
                if location and building:
                    active_phone = get_active_allocation(uid)
                    if active_phone:
                        st.warning(f"⚠️ User already has an active allocation: {active_phone}")
                        context_text += f"\n### CURRENT ASSIGNMENT STATUS\n[BLOCKED] The user currently has an active phone number assigned to them: `{active_phone}`. You MUST outright refuse their request to allocate a new one and inform them of their existing number.\n"
                    else:
                        st.info(f"🏢 Fetching available unreserved phones residing in {location} ({building})...")
                        numbers = list_available_numbers_for_site(location, building)
                        context_text += f"\n### AVAILABLE PHONE NUMBERS FOR {location}/{building}\n"
                        if numbers:
                            for n in numbers:
                                context_text += f"- {n}\n"
                        else:
                            context_text += "> No available numbers for this location currently in our database.\n"
            else:
                context_text += f"\n### LDAP DATA FOR {uid}\n[CRITICAL ERROR] User '{uid}' was NOT FOUND in our company LDAP sqlite/postgres database! You MUST explicitly tell the user that this UserId does not exist in the directory. DO NOT attempt to summarize missing fields like Department or Employee ID.\n"
        except Exception as e:
            context_text += f"\n[ERROR: Failed to fetch backend data: {str(e)}]\n"
            
    return context_text

def run_agent(chat_history: list, context_text: str):
    cached_uid = st.session_state.get('current_userid', 'None specified yet')
    system_prompt = f"""You are an IT automation agent for corporate phone number allocation.
    
We have securely queried our backend databases to proactively verify the user's request.
Currently working with User ID focus: {cached_uid}

Here is the factual context fetched dynamically based on their inputted UserID:
{context_text if context_text else 'No specific background data fetched for this turn (Waiting for a valid Employee ID in the prompt).'}

YOUR INSTRUCTIONS:
1. STRICT: Base your answers ONLY on the provided backend LDAP data and Available Phone Numbers. Do not hallucinate numbers or names.
2. Summarize the user's LDAP details cleanly.
3. CRITICAL: If the context says the user already has an active phone number assigned to them, you MUST NOT allocate a new phone number. You must explicitly inform the user of their existing active phone number, refuse the new allocation, and DO NOT output the <ALLOCATE> tag!
4. If they asked for a phone number allocation (and don't currently have one), suggest one of the available phone numbers explicitly using Markdown. 
5. CRITICAL: If the context says "No available numbers for this location", you MUST NOT hallucinate or invent a phone number. You must tell the user that inventory is depleted for their specific location/building.
6. IMPORTANT: If the user confirms they want to allocate a specific number, or if you are directly executing their allocation request, you MUST output the exact tag `<ALLOCATE>[#]</ALLOCATE>` (replace [#] with the actual chosen number from the available list) at the very end of your response. The backend system will parse this to execute the actual database record update!
7. Be helpful, clear, and professional.
"""

    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
            
    response = llm.invoke(messages)
    return response.content

# Streamlit Chat interface
if "p_messages" not in st.session_state:
    st.session_state.p_messages = []

for message in st.session_state.p_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Enter your request... (e.g. 'I need a phone for EMP010')"):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.p_messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Processing request..."):
            try:
                # 1. Proactively run the database functions if applicable
                context_text = gather_context(prompt)
                
                # 2. Query Groq with the safely injected background data
                decision = run_agent(st.session_state.p_messages, context_text)
                
                # 3. Intercept Physical DB Allocation commands from the LLM
                match = re.search(r"<ALLOCATE>([\d\-]+)</ALLOCATE>", decision)
                if match:
                    number_to_allocate = match.group(1)
                    target_uid = st.session_state.get("current_userid")
                    if target_uid:
                        # Double check if someone tried bypassing the UI
                        if get_active_allocation(target_uid):
                            decision = decision.replace(match.group(0), "").strip()
                            decision += f"\n\n❌ **System Execution Failed:** Number `{number_to_allocate}` could not be allocated because **{target_uid}** already has an active phone assignment."
                        else:
                            res = reserve_phone_number_in_inventory(number_to_allocate)
                            decision = decision.replace(match.group(0), "").strip()
                            if res.get("status") == "reserved":
                                record_allocation(target_uid, number_to_allocate)
                                decision += f"\n\n✅ **System Execution Success:** Number `{number_to_allocate}` has been permanently reserved from inventory and allocated to **{target_uid}** in the database!"
                            else:
                                decision += f"\n\n❌ **System Execution Failed:** Could not reserve number `{number_to_allocate}`. Status: {res.get('current_status', 'not found')}."
                    else:
                        decision = decision.replace(match.group(0), "").strip()
                        decision += f"\n\n⚠️ **System Warning:** Attempted to allocate `{number_to_allocate}`, but the exact User ID has been forgotten in my cache context. Please provide the User ID again (e.g. EMP001)."
                
                st.markdown(decision)
                st.session_state.p_messages.append({"role": "assistant", "content": decision})
            except Exception as e:
                st.error(f"Error communicating with LLM: {str(e)}")
