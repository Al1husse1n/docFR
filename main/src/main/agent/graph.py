from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph import StateGraph, End
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from dotenv import load_dotenv

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

    #page content
    url: str                                          
    title: str

    #raw data
    content: str
    headings: list[str]
    code_blocks: list[str]
    links: list[str]

    #detection flags
    is_docs: bool
    is_openapi: bool
    is_json_hidden: bool
    found_hidden_json_url: None
    openapi_url: None

    #parsed data
    endpoints: list[str]
    examples: list[str]


llm = ChatOllama(
    model="llama3.2:3b"
)

def find_json(state:AgentState) -> AgentState:     #if not json try to find json and if you find it (to node 1) if you dont find it (to node 2), if its json(to node 1)
    if state["is_openapi"]:
        if not state["is_json_hidden"]:
            return state
        else:
            






    

