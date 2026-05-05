
from fastapi import FastAPI, HTTPException, status, Depends
from .schema import DataCreate,  DataResponse
from ..agent.graph import *
  


api = FastAPI()

@api.post("/")
def get_answer(data: DataCreate):
    print("here1")
    result = app.invoke(data)
    print("here2")
    return result
    