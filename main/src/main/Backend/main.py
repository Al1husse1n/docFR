
from fastapi import FastAPI, HTTPException, status, Depends
from .schema import DataCreate, DataResponse
from ..agent.graph import *
from langchain_core.messages import HumanMessage
import httpx, json, asyncio
from typing import Optional, Dict, Any




api = FastAPI()

def normalize_messages(messages):
    if not isinstance(messages, list):
        return messages

    normalized = []
    for item in messages:
        if isinstance(item, dict):
            content = item.get('content', '')
            normalized.append(HumanMessage(content=content))
        else:
            normalized.append(item)

    return normalized


def convert_message(message):
    converted = []
    converted.append(HumanMessage(message))
    
    return converted

@api.post("/")
async def get_answer(data: DataCreate):
    state = data.model_dump()       #change to dictionary
    state["messages"] = convert_message(state["messages"][0]["content"])

    if state.get("found_hidden_json_url") != None:
        state["openapi_schema"] = await request_hidden_schema(state.get("found_hidden_json_url", ""))

    result = app.invoke(state)
    return result    



async def request_hidden_schema(url:str):
    print("called request hidden schema")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                timeout=30.0,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'DocFR-Extension/1.0'
                }
            )
            
            response.raise_for_status()
            schema = response.json()
            
            if not isinstance(schema, dict):
                print(f"❌ Response is not a JSON object")
                return None
            
            if 'openapi' not in schema and 'swagger' not in schema:
                print(f"⚠️ Response doesn't look like OpenAPI (missing version field)")
            
            print(f"✅ Successfully fetched OpenAPI schema from {url}")
            return schema
            
    except httpx.TimeoutException:
        print(f"❌ Timeout fetching {url}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP error {e.response.status_code}: {url}")
        return None
    except httpx.RequestError as e:
        print(f"❌ Request error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON response: {e}")
        return None                                                       
