# 📘 LLM-Powered Phone Allocation Agent (LangChain + FastAPI + MCP)

## 🧠 Overview
This document outlines the design and implementation plan for an AI-powered agent that automates phone number allocation for new employees.

The system integrates:
- LDAP API → Employee data
- DID API → Available phone numbers
- ServiceNow → Ticketing & tracking
- LangChain → LLM agent orchestration
- MCP → Tool standardization

---

## 🏗️ Architecture

```
User / Trigger
      ↓
LLM Agent (LangChain)
      ↓
Tool Layer (MCP Standardized)
      ↓
LDAP API | DID API | ServiceNow API
      ↓
Database + Logs
      ↓
Notifications
```

---

## ⚙️ Workflow

1. Trigger (new hire / manual request)
2. Fetch employee details (LDAP)
3. Validate data
4. Fetch available numbers (DID)
5. Smart selection (location/building-based)
6. Reserve number
7. Create ServiceNow ticket
8. Notify stakeholders

---

## 🧩 MCP Tool Definitions

Example:

```json
{
  "name": "get_employee_details",
  "description": "Fetch employee details from LDAP",
  "input_schema": {
    "type": "object",
    "properties": {
      "employee_id": { "type": "string" }
    },
    "required": ["employee_id"]
  }
}
```

---

## 🚀 FastAPI Services

### LDAP API

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/employee/{employee_id}")
def get_employee(employee_id: str):
    return {
        "employee_id": employee_id,
        "name": "John Doe",
        "location": "Bangalore",
        "building": "B1",
        "manager_id": "M123"
    }
```

---

### DID API

```python
@app.get("/available-numbers")
def get_numbers(location: str, building: str):
    return {
        "numbers": ["080123456", "080123457"]
    }

@app.post("/reserve-number")
def reserve_number(number: str):
    return {"status": "reserved", "number": number}
```

---

## 🧠 LangChain Agent

### Install

```bash
pip install langchain openai fastapi uvicorn
```

---

### Tool Definitions

```python
from langchain.tools import Tool
import requests

def get_employee(employee_id):
    return requests.get(f"http://localhost:8000/employee/{employee_id}").json()

def get_numbers(data):
    return requests.get(
        "http://localhost:8001/available-numbers",
        params=data
    ).json()

def reserve_number(number):
    return requests.post(
        "http://localhost:8001/reserve-number",
        json={"number": number}
    ).json()

tools = [
    Tool(name="LDAP Lookup", func=get_employee, description="Fetch employee details"),
    Tool(name="Get Available Numbers", func=get_numbers, description="Get DID numbers"),
    Tool(name="Reserve Number", func=reserve_number, description="Reserve phone number")
]
```

---

### System Prompt

```python
SYSTEM_PROMPT = """
You are an IT automation agent.

Steps:
1. Fetch employee details
2. Validate data
3. Get available numbers
4. Choose best number based on location/building
5. Reserve number
6. Return final result

If data missing → create ServiceNow ticket.
"""
```

---

### Agent Initialization

```python
from langchain.agents import initialize_agent
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(model="gpt-4")

agent = initialize_agent(
    tools,
    llm,
    agent="zero-shot-react-description",
    verbose=True
)
```

---

### Run Agent

```python
response = agent.run("Assign phone number to employee EMP123")
print(response)
```

---

## 🔌 ServiceNow Integration (Mock)

```python
def create_ticket(data):
    return {"ticket_id": "INC001234"}
```

---

## 🌐 FastAPI Agent Endpoint

```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/assign")
def assign(employee_id: str):
    result = agent.run(f"Assign phone to {employee_id}")
    return {"result": result}
```

---

## 🗄️ Database Design

### employees
- id
- name
- location
- building
- manager_id

### phone_numbers
- id
- number
- location
- building
- status

### allocations
- id
- employee_id
- phone_number
- status
- created_at

### logs
- id
- event
- data
- timestamp

---

## 🔐 Security
- API authentication (JWT)
- Role-based access
- Mask sensitive data in logs

---

## 🚀 Enhancements

### 1. Memory
- Prevent duplicate assignments

### 2. Retry Mechanism
- Handle API failures

### 3. Observability
- Logging + tracing

### 4. Event-Driven
- Kafka / RabbitMQ triggers

### 5. Multi-Agent System
- Validation agent
- Allocation agent
- Ticketing agent

### 6. RAG Layer
- Store allocation policies

---

## 🧭 Implementation Plan

1. Build FastAPI services (LDAP + DID mock)
2. Create LangChain agent
3. Integrate tools
4. Add database
5. Add ServiceNow integration
6. Add logging & retry
7. Add intelligence layer

---

## 💡 Outcome

A scalable AI-driven IT automation system capable of:
- Zero-touch onboarding
- Intelligent resource allocation
- Enterprise-grade workflow automation

---

## 📌 Future Scope
- Extend to laptop allocation
- Software license automation
- Access provisioning
- Full onboarding platform

