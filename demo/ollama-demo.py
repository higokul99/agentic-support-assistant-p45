from langchain_community.chat_models import ChatOllama
import streamlit as st


llm = ChatOllama(model="gemma3:1b")
st.title("Ollama Demo")

question = st.text_input("Ask me anything")

if question:
    response = llm.invoke(question)
    st.write(response.content)