from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode 
from dotenv import load_dotenv
from .helper_functions import (
    no_doc_similarity_search,
    format_search_results,
    openapi_schema_similarity_search,
    format_openapi_results
)

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
    found_hidden_json_url: str | None
    openapi_url: str | None
    openapi_schema: dict | None                                                 
    schema_source: str | None   #Direct or hidden
    
    #parsed data
    endpoints: list[str]
    examples: list[str]
                                                

llm = ChatOllama(
    model="llama3.2:3b"
)


def initialize(state: AgentState) -> AgentState:
    return state

def no_doc_answer(state: AgentState) -> AgentState:
    print("no_doc_answer called")
    if not state.get("messages") or len(state["messages"]) == 0:
        return {"messages": [AIMessage(content="No question found.")]}

    search_results = no_doc_similarity_search(
        question= state['messages'][-1].content,
        content= state.get("content", ""),
        headings= state.get("headings", []),
        codeblocks= state.get("code_blocks", []),
        links= state.get("links", [])
    )

    context = format_search_results(search_results)
    
    system_content = f""""
    You are an AI assistant embedded in a browser extension that helps users understand technical content.

The current webpage is NOT documentation. Do NOT assume the page contains API details, endpoints, or structured technical references.

Your job is to:

1. Clearly acknowledge that the current page does not appear to be documentation if relevant.
2. Answer the user's question using:

   * General programming knowledge
   * Any relevant information from the page (if useful)
3. Do NOT hallucinate or invent APIs, endpoints, or technical details that are not present.
4. If the question depends on documentation that is not available:

   * Politely say the information is not found on this page
   * Suggest what kind of page or documentation the user should look for
5. Keep answers concise, clear, and helpful.
6. If the question is unrelated to the page, still try to provide a useful general answer.

Tone:

* Professional but friendly
* Honest and transparent
* No unnecessary filler

Output:

* Direct answer to the question
* Optional short suggestion if the page is not useful for the query

Input - The content or information from the webpage you answer from is
    {context}

    """
    
    system_prompt = SystemMessage(content=system_content)
    response = llm.invoke([system_prompt] + state["messages"])

    return {"messages": [response]} 


def no_openapi_answer(state:AgentState) -> AgentState:
    print("no openapi answer called")
    if not state.get("messages") or len(state["messages"]) == 0:
        return {"messages": [AIMessage(content="No question found.")]}

    search_results = no_doc_similarity_search(
        question= state['messages'][-1].content,
        content= state.get("content", ""),
        headings= state.get("headings", []),
        codeblocks= state.get("code_blocks", []),
        links= state.get("links", [])
    )

    context = format_search_results(search_results)

    system_content = f"""
    You are an AI assistant that helps users understand API and technical documentation.

The current page IS documentation, but it does NOT contain a structured OpenAPI/Swagger specification. The content may be unstructured, incomplete, or noisy.

Your job is to:

1. Carefully analyze the provided page content, headings, and code blocks.
2. Extract relevant technical details such as:

   * API endpoints (e.g., GET /users, POST /auth)
   * Authentication methods
   * Request/response examples
   * Important usage notes
3. Answer the user’s question using ONLY information that:

   * Appears in the provided content
   * Or is a reasonable interpretation of it

STRICT RULES:

* Do NOT hallucinate endpoints, parameters, or authentication methods.
* If the exact answer is not found, say so clearly.
* You MAY infer small details only if they are strongly implied by the content.

When answering:

* Be concise and structured
* Use bullet points if helpful
* Include code examples if available from the page
* Prefer concrete details over general explanations

If the answer is partially available:

* Provide what you can
* Then clearly state what is missing

If the answer is not found:

* Say: “This page does not provide enough information…”
* Suggest what the user should look for (e.g., authentication section, API reference)

Tone:

* Clear, technical, and helpful
* No filler or vague statements

Output:

* Direct answer
* Optional extracted endpoints/examples if relevant

Input - The content or information from the webpage you answer from is
    {context}

    """

    system_prompt = SystemMessage(content= system_content)
    response = llm.invoke([system_prompt] + state["messages"])

    return {"messages" : [response]}



def json_hidden_answer(state: AgentState) -> AgentState:
    print("no json hidden answer called")
    if not state.get("messages") or len(state["messages"]) == 0:
        return {"messages": [AIMessage(content="No question found.")]}
    
    search_result = openapi_schema_similarity_search(
        question=state["messages"][-1].content,
        openapi_schema=state.get("openapi_schema")
    )

    formatted_result = format_openapi_results(search_result)

    system_content = f"""
You are an AI assistant that helps users understand APIs using a structured OpenAPI (Swagger) specification.

The OpenAPI schema you received was extracted from a hidden JSON source on the webpage. This schema is the MOST reliable and authoritative representation of the API.

THe OpenAPI schema is as follows: {formatted_result}

Your job is to:

1. Answer the user's question using ONLY the provided OpenAPI schema.
2. Identify relevant:

   * Endpoint paths (e.g., /users)
   * HTTP methods (GET, POST, etc.)
   * Parameters (query, path, body)
   * Request body structure (if available)
   * Authentication requirements (if defined)
3. Provide a clear and precise answer based strictly on the schema.

STRICT RULES:

* Do NOT hallucinate or invent endpoints, parameters, or behaviors.
* Do NOT rely on general knowledge or assumptions.
* Do NOT reference webpage text — use ONLY the OpenAPI schema.
* If the requested information is not present, say:
  “This API specification does not include information about this request.”

WHEN ANSWERING:

* Always include:

  * HTTP method
  * Endpoint path
* If available, include:

  * Required parameters
  * Request body fields
  * Authentication details
* Provide a short example (e.g., curl or JSON) when possible.

IF MULTIPLE ENDPOINTS MATCH:

* Return the most relevant ones (limit to a few)

TONE:

* Technical, precise, and concise
* No unnecessary explanation

OUTPUT FORMAT:

* Direct answer
* Relevant endpoint(s)
* Optional example

""" 
    
    system_prompt = SystemMessage(content= system_content)
    response = llm.invoke([system_prompt] + state["messages"])

    return {"messages" : [response]}

def json_not_hidden_answer(state: AgentState) -> AgentState:
    print("json_not hidden answer called")
    if not state.get("messages") or len(state["messages"]) == 0:
        return {"messages": [AIMessage(content="No question found.")]}

    search_result = openapi_schema_similarity_search(
        question=state["messages"][-1].content,
        openapi_schema=state.get("openapi_schema")
    )

    formatted_result = format_openapi_results(search_result)

    system_content = f"""
    You are an AI assistant that helps users understand APIs using a provided OpenAPI (Swagger) JSON specification.

You are given a VALID OpenAPI JSON. This is the ONLY source of truth.
context: {formatted_result}

Your job is to:

1. Analyze the OpenAPI JSON and locate endpoints relevant to the user's question.
2. Identify:

   * HTTP method (GET, POST, etc.)
   * Endpoint path (e.g., /users)
   * Parameters (query, path, body)
   * Request body structure (if available)
   * Authentication requirements (if defined)
3. Answer the user's question clearly and precisely using ONLY this data.

STRICT RULES:

* Do NOT hallucinate or invent endpoints, parameters, or authentication.
* Do NOT use general knowledge outside the provided JSON.
* If the requested information is not present, clearly say so.

When answering:

* Always include the endpoint and method if relevant
* Provide required parameters or request body fields if available
* Include a short example (e.g., curl or JSON) when possible
* Prefer concise, structured answers

If multiple endpoints match:

* Show the most relevant ones

If nothing matches:

* Say: “This OpenAPI specification does not include information about this request.”

Tone:

* Technical, precise, and concise
* No unnecessary explanations

Output format:

* Direct answer
* Relevant endpoint(s)
* Optional example

"""
    system_prompt = SystemMessage(content= system_content)
    response = llm.invoke([system_prompt] + state["messages"])

    return {"messages" : [response]}

def json_not_found_answer(state: AgentState) -> AgentState:
    print("json not found answer called")
    if not state.get("messages") or len(state["messages"]) == 0:
        return {"messages": [AIMessage(content="No question found.")]}

    search_results = no_doc_similarity_search(
        question= state['messages'][-1].content,
        content= state.get("content", ""),
        headings= state.get("headings", []),
        codeblocks= state.get("code_blocks", []),
        links= state.get("links", [])
    )

    context = format_search_results(search_results)

    system_content = f"""
You are an AI assistant that helps users understand APIs from a Swagger/OpenAPI documentation interface when the underlying JSON schema is NOT accessible.

The current page appears to be an API documentation UI (e.g., Swagger UI), but no structured OpenAPI JSON was found. Therefore, you must rely ONLY on the visible content extracted from the page.

Context/information you answer from: {context}

Your job is to:

1. Extract and interpret API information from the provided content.
2. Identify:

   * Endpoint paths (e.g., /users)
   * HTTP methods (GET, POST, etc.)
   * Descriptions or summaries
   * Parameters (if visible)
   * Request body fields (if visible)
3. Answer the user's question based ONLY on the visible content.

STRICT RULES:

* Do NOT assume or invent endpoints that are not present in the content.
* Do NOT rely on general API knowledge.
* Do NOT claim full accuracy — this is a best-effort extraction.
* If the information is unclear or incomplete, say so.

WHEN ANSWERING:

* Include endpoint and method if available
* Prefer exact text or close paraphrasing from the content
* If multiple endpoints match, list the most relevant ones
* If the answer is not clearly present, say:
  “This information is not clearly available in the current API documentation view.”

IMPORTANT:

* The documentation may be incomplete or partially rendered
* Some endpoints or details may be missing due to lack of structured data access

TONE:

* Technical but cautious
* Clear and concise
* Avoid overconfidence

OUTPUT FORMAT:

* Direct answer
* Relevant endpoint(s) (if found)
* Optional explanation or note about uncertainty

"""
    system_prompt = SystemMessage(content= system_content)
    response = llm.invoke([system_prompt] + state["messages"])

    return {"messages" : [response]}


#conditional edges/functions
def decide_is_doc(state: AgentState) -> str:
    if state["is_docs"] == True:
        return "is_doc"
    else:
        return "is_not_doc"
    
def decide_is_openapi(state: AgentState) -> str:
    if state["is_openapi"] == True:
        return "is_openapi"
    else:
        return "is_not_openapi"

def decide_is_json_hidden(state: AgentState) -> str:
    if state["is_json_hidden"] == True:
        return "is_json_hidden"
    else:
        return "is_json_not_hidden"

def decide_is_json_found(state: AgentState) -> str:  
    if state["openapi_schema"] != None:
        return "is_json_found"
    else:
        return "is_json_not_found"


#graph generation
graph = StateGraph(AgentState)
graph.add_node("entry", initialize)
graph.add_node("no_doc_answer", no_doc_answer)
graph.add_node("no_openapi_answer", no_openapi_answer)
graph.add_node("json_hidden_answer", json_hidden_answer)
graph.add_node("json_not_hidden_answer", json_not_hidden_answer)
graph.add_node("json_not_found_answer", json_not_found_answer)
# Add passthrough nodes for each decision point
graph.add_node("decide_is_openapi", lambda state: state) 
graph.add_node("decide_is_json_hidden", lambda state: state)  
graph.add_node("decide_is_json_found", lambda state: state)  

#edges
graph.add_conditional_edges(
    "decide_is_json_found",
    decide_is_json_found,
    {
        "is_json_found": "json_hidden_answer",
        "is_json_not_found": "json_not_found_answer"
    }
)

graph.add_conditional_edges(
    "decide_is_json_hidden",
    decide_is_json_hidden,
    {
       "is_json_hidden": "decide_is_json_found",
       "is_json_not_hidden": "json_not_hidden_answer" 
    }   
)

graph.add_conditional_edges(
    "decide_is_openapi",
    decide_is_openapi,
    {
        "is_openapi": "decide_is_json_hidden",
        "is_not_openapi": "no_openapi_answer"
    }
)

graph.add_conditional_edges(
    "entry",
    decide_is_doc,
    {
        "is_doc": "decide_is_openapi",
        "is_not_doc": "no_doc_answer"
    }
)



graph.add_edge(START, "entry")
graph.add_edge("no_doc_answer", END)
graph.add_edge("no_openapi_answer", END)
graph.add_edge("json_hidden_answer", END)
graph.add_edge("json_not_hidden_answer", END)
graph.add_edge("json_not_found_answer", END)
app = graph.compile()


test_state = {
    "messages": [HumanMessage(content="What is this API about?")],
    "url": "https://example.com",
    "title": "Test Page",
    "content": "Some test content",
    "headings": [],
    "code_blocks": [],
    "links": [],
    "is_docs": True,
    "is_openapi": True,
    "is_json_hidden": False,
    "found_hidden_json_url": None,
    "openapi_url": None,
    "openapi_schema": None,
    "schema_source": None,
    "endpoints": [],
    "examples": []
}

