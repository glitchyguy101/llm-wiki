"""
server.py - FastAPI backend for Wiki-LLM integrated with Supabase Storage.
Serves the UI and provides cloud bucket sync capabilities.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# For serverless wrapper matching Vercel deployment requirements
try:
    from mangum import Mangum
except ImportError:
    Mangum = None

# Add agent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import run_agent
# tools.py now connects directly to Supabase storage buckets
from tools import list_wiki_files, read_wiki_file, write_wiki_file, delete_wiki_file

ROOT = Path(__file__).parent.parent
UI_DIR = ROOT / "ui"

app = FastAPI(title="Wiki-LLM", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static UI files (Fallback if hosting everything together)
if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")


@app.get("/")
async def root():
    if (UI_DIR / "index.html").exists():
        return FileResponse(str(UI_DIR / "index.html"))
    return JSONResponse({"status": "Wiki-LLM API is running successfully"})


# ─────────────────────────────────────────────
# Wiki REST API (Now hitting Supabase Storage)
# ─────────────────────────────────────────────
@app.get("/api/wiki")
async def api_list_wiki():
    files = list_wiki_files()
    if isinstance(files, dict) and "error" in files:
        raise HTTPException(status_code=500, detail=files["error"])
    return files


@app.get("/api/wiki/{filename:path}")
async def api_read_wiki(filename: str):
    result = read_wiki_file(filename)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/wiki/{filename:path}")
async def api_write_wiki(filename: str, body: dict):
    content = body.get("content", "")
    result = write_wiki_file(filename, content)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.delete("/api/wiki/{filename:path}")
async def api_delete_wiki(filename: str):
    result = delete_wiki_file(filename)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ─────────────────────────────────────────────
# SERVERLESS BACKUP: HTTP Streaming route for Pure Vercel
# ─────────────────────────────────────────────
@app.post("/api/chat/stream")
async def http_stream_endpoint(body: dict):
    """
    Alternative endpoint for pure Vercel deployments where WebSockets fail.
    Expects a payload like: {"message": "User prompt here", "history": []}
    """
    task = body.get("message", "").strip()
    history = body.get("history", [])

    if not task:
        raise HTTPException(status_code=400, detail="Message token cannot be empty")

    async def event_generator():
        try:
            async for event in run_agent(task, history):
                yield f"data: {json.dumps(event)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# WebSocket — Streaming agent (For Hybrid Cloud Setups)
# ─────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    conversation_history = []

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            task = data.get("message", "").strip()

            if not task:
                continue

            conversation_history.append({"role": "user", "content": task})

            answer_parts = []
            async for event in run_agent(task, conversation_history[:-1]):
                await websocket.send_text(json.dumps(event))
                if event["type"] == "answer":
                    answer_parts.append(event["content"])

            if answer_parts:
                conversation_history.append({
                    "role": "model",
                    "content": " ".join(answer_parts),
                })

            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
        except:
            pass


# AWS Lambda/Vercel Handler initialization
handler = Mangum(app) if Mangum else None

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n[*] Wiki-LLM starting in Cloud Hybrid Mode...")
    print("[*] Open your local browser or production frontend deployment link.\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)