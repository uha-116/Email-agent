from fastapi import FastAPI
from pydantic import BaseModel

# 🔥 Import your orchestrator
from backend.query_engine.query_orchestrator import handle_query

app = FastAPI()

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