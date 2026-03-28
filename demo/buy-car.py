import streamlit as st
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# 1. Create a function that has dummy data of car models and prices
def get_car_info() -> str:
    """
    Get the available car models and their prices from the dealership database. 
    """
    return """
    Available Car Data:
    
    Suzuki:
    - Swift: $15,000 (Compact Hatchback)
    - Baleno: $17,000 (Premium Hatchback)
    - Brezza: $20,000 (Compact SUV)
    
    Honda:
    - Civic: $25,000 (Sedan)
    - City: $20,000 (Sedan)
    - Accord: $30,000 (Premium Sedan)
    
    Tata:
    - Nexon: $18,000 (Compact SUV)
    - Harrier: $22,000 (SUV)
    - Safari: $25,000 (Large SUV)
    """

st.title("🚗 Car Purchase Agent AI")
st.write("I can help you decide which car to buy! Our dealership currently has **Suzuki**, **Honda**, and **Tata** vehicles.")

# 2. Setup LLM
llm = ChatOllama(model="gemma3:1b", temperature=0.2)

# 3. Build a custom agent execution logic
def run_car_agent(chat_history: list):
    # The agent explicitly uses the function prior to checking the LLM to avoid LangChain tool-binding errors
    car_data = get_car_info()
    
    # 4. Write a good prompt for the agent that instructs it to use the fetched data
    system_prompt = f"""You are a helpful, expert car sales agent. 

We have used our internal 'get_car_info' python function to fetch our current inventory for you. 
Here is the data retrieved from the function:
{car_data}

YOUR INSTRUCTIONS:
1. Base your suggestions ONLY on the data returned by the function above. Don't make up prices or models not listed.
2. Analyze the user's input to suggest the best match based on price, brand, or car type (e.g. if they want an SUV, recommend a Safari, Harrier, or Brezza).
3. If they ask for brands we don't have (like Toyota or Ford), politely inform them we only carry Suzuki, Honda, and Tata right now.
4. Be persuasive but helpful and format your reply nicely using Markdown.
"""

    # 5. Create the message list with the system prompt
    messages = [SystemMessage(content=system_prompt)]
    
    # Append the historical chat messages
    for msg in chat_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    
    response = llm.invoke(messages)
    return response.content

# 6. Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 7. Get user input via chat input
if prompt := st.chat_input("Tell me what you are looking for (e.g., 'I want a cheap car' or 'What SUVs do you have?'):"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        with st.spinner("Analyzing request and checking database..."):
            try:
                # Execute our agent with the full chat history
                decision = run_car_agent(st.session_state.messages)
                st.markdown(decision)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": decision})
            except Exception as e:
                st.error(f"An error occurred: {e}")
