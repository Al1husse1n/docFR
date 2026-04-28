
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import requests
from starlette.responses import JSONResponse
from ..agent.graph import app as langgraph_app

# --- Logging setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("talk-to-api-backend")

# --- FastAPI app setup ---
app = FastAPI()
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],  # In production, restrict this to your extension's origin
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# --- Pydantic request model ---
class AskRequest(BaseModel):
	question: str
	url: str
	title: Optional[str] = None
	content: Optional[str] = None
	headings: Optional[List[str]] = None
	code_blocks: Optional[List[str]] = None
	links: Optional[List[str]] = None
	is_docs: Optional[bool] = False
	is_openapi: Optional[bool] = False
	is_json_hidden: Optional[bool] = False
	found_hidden_json_url: Optional[str] = None
	openapi_url: Optional[str] = None
	endpoints: Optional[List[str]] = None
	examples: Optional[List[str]] = None

# --- Utility: Safe OpenAPI JSON fetch ---
def fetch_openapi_json(base_url: str, json_url: str, timeout: int = 5) -> Optional[dict]:
	try:
		from urllib.parse import urljoin
		if json_url.startswith("http://") or json_url.startswith("https://"):
			full_url = json_url
		else:
			full_url = urljoin(base_url, json_url)
		headers = {"Accept": "application/json"}
		logger.info(f"Fetching OpenAPI JSON from: {full_url}")
		resp = requests.get(full_url, timeout=timeout, headers=headers)
		resp.raise_for_status()
		try:
			data = resp.json()
		except Exception as e:
			logger.warning(f"Failed to decode JSON from {full_url}: {e}")
			return None
		if not isinstance(data, dict) or "paths" not in data:
			logger.warning(f"Fetched OpenAPI JSON from {full_url} is invalid or missing 'paths'.")
			return None
		logger.info(f"Successfully fetched and validated OpenAPI JSON from {full_url}.")
		return data
	except Exception as e:
		logger.warning(f"Failed to fetch OpenAPI JSON from {json_url}: {e}")
		return None

# --- POST /ask endpoint ---
from langchain_core.messages import HumanMessage

@app.post("/ask")
async def ask_endpoint(req: AskRequest):
	if not req.question or not req.question.strip():
		return JSONResponse(status_code=400, content={"answer": "No question provided."})

	state = {
		"messages": [HumanMessage(content=req.question)],
		"url": req.url,
		"title": req.title or "",
		"content": req.content or "",
		"headings": req.headings or [],
		"code_blocks": req.code_blocks or [],
		"links": req.links or [],
		"is_docs": req.is_docs,
		"is_openapi": req.is_openapi,
		"is_json_hidden": req.is_json_hidden,
		"found_hidden_json_url": req.found_hidden_json_url,
		"openapi_url": req.openapi_url,
		"openapi_schema": None,
		"schema_source": None,
		"endpoints": [],
		"examples": []
	}


	openapi_schema = None
	schema_source = None

	if state["is_openapi"] and state["found_hidden_json_url"]:
		openapi_schema = fetch_openapi_json(state["url"], state["found_hidden_json_url"])
		if openapi_schema is not None:
			schema_source = "hidden"
			logger.info("Fetched hidden OpenAPI JSON successfully.")
		else:
			logger.debug("OpenAPI detected but hidden schema could not be fetched or is invalid.")
	elif state["is_openapi"] and state["openapi_url"]:
		openapi_schema = fetch_openapi_json(state["url"], state["openapi_url"])
		if openapi_schema is not None:
			schema_source = "direct"
			logger.info("Fetched direct OpenAPI JSON successfully.")
		else:
			logger.debug("OpenAPI detected but direct schema could not be fetched or is invalid.")
	elif state["is_openapi"]:
		logger.debug("OpenAPI detected but no schema URL provided.")

	state["openapi_schema"] = openapi_schema
	state["schema_source"] = schema_source

	try:
		result = langgraph_app.invoke(state)
		answer = None
		if result and isinstance(result, dict) and "messages" in result and result["messages"]:
			answer = result["messages"][-1].content
		else:
			answer = "No answer generated."
		return {"answer": answer}
	except Exception as e:
		logger.error(f"Error during LangGraph invocation: {e}")
		return JSONResponse(status_code=500, content={"answer": "Internal server error."})
