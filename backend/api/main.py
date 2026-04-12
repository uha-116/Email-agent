from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import asyncio
import json

# ✅ ADD THIS IMPORT (CORS FIX)
from fastapi.middleware.cors import CORSMiddleware

# 🔥 Import your orchestrator
from backend.query_engine.query_orchestrator import handle_query_stream

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




# =========================================================
# 🔥 NEW STREAMING ENDPOINT (ADDED)
# =========================================================

async def process_query_stream(question: str):

    try:
        for step in handle_query_stream(question):

            # ✅ FINAL OUTPUT
            if isinstance(step, tuple) and step[0] == "FINAL":
                yield f"data: FINAL::{json.dumps(step[1])}\n\n"

            # ✅ STATUS UPDATE
            else:
                yield f"data: {step}\n\n"

            # ⚡ small flush delay (NOT fake UX delay)
            await asyncio.sleep(0.10)

    except Exception as e:
        yield f"data: ERROR::{str(e)}\n\n"

@app.get("/query-stream")
async def query_stream(q: str):
    return StreamingResponse(
        process_query_stream(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )