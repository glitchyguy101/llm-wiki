"""
server.py - FastAPI backend for Wiki-LLM.
Serves the UI and provides:
  - WebSocket /ws for streaming agent events
  - REST endpoints for wiki file management
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Add agent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import run_agent
from tools import list_wiki_files, read_wiki_file, write_wiki_file, delete_wiki_file, WIKI_DIR

ROOT = Path(__file__).parent.parent
UI_DIR = ROOT / "ui"

app = FastAPI(title="Wiki-LLM", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static UI files
app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")


# ─────────────────────────────────────────────
# Root → serve UI
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    return FileResponse(str(UI_DIR / "index.html"))


# ─────────────────────────────────────────────
# Wiki REST API
# ─────────────────────────────────────────────
@app.get("/api/wiki")
async def api_list_wiki():
    return list_wiki_files()


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
# WebSocket — Streaming agent
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

            # Add user message to history
            conversation_history.append({"role": "user", "content": task})

            # Stream agent events
            answer_parts = []
            async for event in run_agent(task, conversation_history[:-1]):
                await websocket.send_text(json.dumps(event))
                if event["type"] == "answer":
                    answer_parts.append(event["content"])

            # Store assistant response in history
            if answer_parts:
                conversation_history.append({
                    "role": "model",
                    "content": " ".join(answer_parts),
                })

            # Signal done
            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
        except:
            pass


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n[*] Wiki-LLM starting...")
    print(f"[*] Wiki directory: {WIKI_DIR}")
    print("[*] Open http://localhost:8000 in your browser\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
