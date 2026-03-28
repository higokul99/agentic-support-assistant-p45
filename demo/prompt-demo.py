from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import PromptTemplate
import streamlit as st

llm = ChatOllama(model="gemma3:1b")
prompt = PromptTemplate(
    input_variables=["country"],
    template="""You are an expert in traditional cuisines. You provide information about a specific dish from a specific country.
Answer the question: What is the traditional dish of {country}?""",
)

st.title("Prompt Demo - Cuisine Knowledge Base")
country = st.text_input("Enter a country")

if country:
    chain = prompt | llm
    response = chain.invoke({"country": country})
    st.write(response.content)
