from fastapi import FastAPI
from pydantic import BaseModel

# ✅ ADD THIS IMPORT (CORS FIX)
from fastapi.middleware.cors import CORSMiddleware

# 🔥 Import your orchestrator
from backend.query_engine.query_orchestrator import handle_query

app = FastAPI()

# ✅ ADD THIS BLOCK (CORS FIX)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow all origins (dev mode)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str


@app.post("/query")
def query_handler(req: QueryRequest):

    user_query = req.question

    # 🔥 Call your full pipeline
    answer = handle_query(user_query)

    return {
        "question": user_query,
        "answer": answer
    }