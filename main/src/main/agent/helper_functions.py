from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
import json
from typing import List, Dict, Any
from langchain_core.documents import Document   

def format_search_results(search_results: dict) -> str:
    """Convert similarity search results into clean text for the LLM"""
    context = ""

    if search_results.get("content"):
        context += "**Page Content:**\n"
        for doc in search_results["content"]:
            context += f"- {doc.page_content}\n"
        context += "\n"

    if search_results.get("headings"):
        context += "**Headings:**\n"
        for doc in search_results["headings"]:
            context += f"- {doc.page_content}\n"
        context += "\n"

    if search_results.get("codeblocks"):
        context += "**Code Blocks:**\n"
        for doc in search_results["codeblocks"]:
            context += f"```python\n{doc.page_content}\n```\n\n"

    if search_results.get("links"):
        context += "**Relevant Links:**\n"
        for doc in search_results["links"]:
            context += f"- {doc.page_content}\n"

    return context.strip() or "No relevant information found on this page."


def no_doc_similarity_search(question:str, content: str, headings:list[str], codeblocks: list[str], links: list[str]) -> dict:
    """return a similarity search with the question"""

    similars = {
        "content" : [],
        "headings" : [],
        "codeblocks" : [],
        "links" : []
    }
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    #similar content retrieval
    content_splitter = RecursiveCharacterTextSplitter(
        chunk_size = 800,
        chunk_overlap = 100,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = content_splitter.split_text(content)
    content_vector_store = FAISS.from_texts(
        texts = chunks,
        embedding= embeddings
    )
    
    content_retriever = content_vector_store.as_retriever(search_kwargs={"k": 4})
    content_docs = content_retriever.invoke(question)
    similars["content"] = content_docs

    #similar headings retrieval
    headings_vector_store = FAISS.from_texts(
        texts = headings,
        embedding=embeddings    
    )
    headings_retriever = headings_vector_store.as_retriever(search_kwargs = {"k" : 3})
    headings_docs = headings_retriever.invoke(question)
    similars["headings"] = headings_docs
    
    #similar code blocks retrieval
    codeblocks_vector_store = FAISS.from_texts(
        texts = codeblocks,
        embedding=embeddings    
    )
    codeblocks_retriever = codeblocks_vector_store.as_retriever(search_kwargs = {"k" : 3})
    codeblocks_docs = codeblocks_retriever.invoke(question)
    similars["codeblocks"] = codeblocks_docs
    
    #similar link retrieval
    links_vector_store = FAISS.from_texts(
        texts = links,
        embedding=embeddings    
    )
    links_retriever = links_vector_store.as_retriever(search_kwargs = {"k" : 3})
    links_docs = links_retriever.invoke(question)
    similars["links"] = links_docs
    
    return similars





def chunk_openapi_dict(
    openapi_dict: Dict[str, Any], 
    source_name: str = "openapi_spec",
    max_chunk_size: int = 1000
) -> List[Document]:
    """
    Converts an OpenAPI schema (given as a Python dictionary) into 
    a list of Document objects suitable for embedding and FAISS.
    
    This is much better than splitting raw JSON because it creates 
    meaningful chunks (one per endpoint).
    """
    
    documents: List[Document] = []
    spec = openapi_dict   # Just for easier reading

    # ====================== 1. Add Global API Information ======================
    # We add general info about the API only once (title, version, description, servers)
    info = spec.get("info", {})
    servers = spec.get("servers", [])

    global_context = f"""API Title: {info.get('title', 'Unknown API')}
Version: {info.get('version', 'N/A')}
Description: {info.get('description', '')}

Servers: {json.dumps(servers, indent=2)}
"""

    documents.append(Document(
        page_content=global_context.strip(),
        metadata={
            "type": "api_info",      # Helps us know this is general info
            "source": source_name
        }
    ))

    # ====================== 2. Chunk Each Endpoint ======================
    # OpenAPI has a "paths" section that contains all endpoints
    paths = spec.get("paths", {})

    for path_url, methods in paths.items():
        for method, operation in methods.items():
            # Skip if it's not a valid operation
            if not isinstance(operation, dict):
                continue

            # Build a clean, readable text block for this specific endpoint
            content = f"""Path: {method.upper()} {path_url}

Operation ID: {operation.get('operationId', 'N/A')}
Summary: {operation.get('summary', '')}
Description: {operation.get('description', '')}
Tags: {', '.join(operation.get('tags', []))}

Parameters:
{json.dumps(operation.get('parameters', []), indent=2)}

Request Body:
{json.dumps(operation.get('requestBody', {}), indent=2)[:700]}

Responses:
{json.dumps(operation.get('responses', {}), indent=2)[:800]}
"""

            # Create a Document object for this endpoint
            doc = Document(
                page_content=content.strip(),   # This text will be embedded
                metadata={
                    "type": "endpoint",                     # Helps identify it's an endpoint
                    "path": path_url,
                    "method": method.upper(),
                    "operationId": operation.get('operationId'),
                    "tags": operation.get('tags', []),
                    "source": source_name
                }
            )
            documents.append(doc)

    # ====================== 3. Optional: Further Split Large Chunks ======================
    # If any endpoint description is very long, split it into smaller chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_size,      # Maximum characters per chunk
        chunk_overlap=100,              # Overlap between chunks for better context
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    # Split the documents further if needed
    final_documents = text_splitter.split_documents(documents)

    print(f"✅ Created {len(final_documents)} document chunks from OpenAPI dictionary")
    
    return final_documents

def openapi_schema_similarity_search(question:str, openapi_schema: dict) -> List[Document]:
    similars = []
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    chunks = chunk_openapi_dict(
        openapi_dict= openapi_schema,
        source_name="user_openapi_spec",
        max_chunk_size=1100
    )

    vector_store = FAISS.from_documents(chunks, embeddings)
    retriever = vector_store.as_retriever(search_kwargs={"k": 4})
    docs = retriever.invoke(question)

    return docs


def format_openapi_results(docs: list[Document]) -> str:
    """Convert retrieved OpenAPI documents into clean text for the LLM"""
    if not docs:
        return "No relevant endpoints found in the API specification."

    context = "**Relevant API Endpoints:**\n\n"
    
    for i, doc in enumerate(docs, 1):
        context += f"{i}. {doc.page_content}\n\n"
    
    return context.strip()
    
    