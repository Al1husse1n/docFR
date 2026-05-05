from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from langchain_core.messages import HumanMessage
from typing import Any

class DataBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    messages: Any
    url: str = Field(min_length=1)

    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    headings: list | None = Field(default= None)
    code_blocks: list | None = Field(default= None)
    links: list | None = Field(default= None)

    is_docs: bool
    is_openapi: bool
    is_json_hidden: bool

    found_hidden_json_url: str | None = Field(default=None, min_length=1)
    openapi_url: str | None = Field(default=None, min_length=1)

    openapi_schema: dict | None = Field(default= None)
    schema_source: str | None = Field(default=None, min_length=1)


class DataResponse(DataBase):
    pass

class DataCreate(DataBase):
    pass

