"""
server.py - FastAPI backend for Nexus-Knowledge (Wiki-LLM Evolution)

Endpoints:
  WebSocket /ws          — streaming agent (legacy single-agent mode)
  WebSocket /ws/nexus    — multi-agent Nexus pipeline (LangGraph)
  REST /api/wiki/*       — wiki file management
  REST /api/upload       — file upload with auto-parsing
  REST /api/graph        — knowledge graph data (nodes + edges)
  REST /api/stats        — knowledge base statistics
  REST /api/semantic-search — semantic similarity search
  REST /api/educator/*   — learning roadmaps, flashcards, quizzes
  GET  /                 — serve React UI (nexus-ui/dist/) or legacy ui/
"""

import json
import os
import sys
import re
import base64
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agent import run_agent
from tools import (
    list_wiki_files, read_wiki_file, write_wiki_file, delete_wiki_file,
    list_raw_files, semantic_search, parse_url as tool_parse_url,
    WIKI_DIR, RAW_DIR,
)

# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────
app = FastAPI(title="Nexus-Knowledge", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving ───────────────────────────────────────────────────────
# Prefer React build; fallback to legacy vanilla UI
NEXUS_UI_DIST = ROOT / "nexus-ui" / "dist"
LEGACY_UI = ROOT / "ui"

if NEXUS_UI_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(NEXUS_UI_DIST / "assets")), name="assets")
    UI_MODE = "react"
else:
    app.mount("/ui", StaticFiles(directory=str(LEGACY_UI)), name="ui")
    UI_MODE = "legacy"


# ─────────────────────────────────────────────
# Root → serve UI
# ─────────────────────────────────────────────
@app.get("/")
async def root():
    if UI_MODE == "react" and (NEXUS_UI_DIST / "index.html").exists():
        return FileResponse(str(NEXUS_UI_DIST / "index.html"))
    return FileResponse(str(LEGACY_UI / "index.html"))




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
# File Upload API
# ─────────────────────────────────────────────
@app.post("/api/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """
    Upload a file to /raw and optionally parse + ingest it.
    Supports: PDF, images (JPG, PNG), DOCX, TXT, MD, CSV, JSON.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Sanitize filename
    safe_name = Path(file.filename).name
    dest = RAW_DIR / safe_name

    try:
        content = await file.read()
        dest.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Auto-ingest into vector store
    ingest_result = {}
    try:
        from tools import ingest_document
        ingest_result = ingest_document(safe_name)
    except Exception as e:
        ingest_result = {"warning": f"Vector store ingest failed: {str(e)}"}

    return JSONResponse({
        "success": True,
        "filename": safe_name,
        "size_bytes": len(content),
        "ingest_result": ingest_result,
        "message": f"File '{safe_name}' uploaded and indexed successfully.",
    })


@app.post("/api/upload-url")
async def api_upload_url(body: dict):
    """Fetch and ingest content from a URL into the knowledge base."""
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    result = tool_parse_url(url)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return JSONResponse({
        "success": True,
        "url": url,
        "title": result.get("title", ""),
        "lines": result.get("lines", 0),
        "content_preview": result.get("content", "")[:500],
    })


# ─────────────────────────────────────────────
# Knowledge Graph API
# ─────────────────────────────────────────────
@app.get("/api/graph")
async def api_get_graph():
    """
    Build and return knowledge graph data (nodes + edges) from wiki backlinks.
    Nodes = wiki files, Edges = [[backlink]] references between them.
    """
    nodes = []
    edges = []
    edge_set = set()

    files = list_wiki_files().get("files", [])

    for f in files:
        name = f["name"]
        node_id = name.replace(".md", "")

        # Read file for backlinks and tags
        wiki_data = read_wiki_file(name)
        content = wiki_data.get("content", "")
        size = f.get("size_bytes", 0)

        # Extract tags
        tags = []
        tag_match = re.search(r"Tags?:\s*([^\n]+)", content, re.IGNORECASE)
        if tag_match:
            tags = [t.strip().strip("[]#*") for t in tag_match.group(1).split(",") if t.strip()]

        # Extract backlinks [[Topic Name]]
        backlinks = re.findall(r"\[\[([^\]]+)\]\]", content)

        nodes.append({
            "id": node_id,
            "label": node_id.replace("_", " "),
            "size": max(10, min(50, size // 100)),  # Node size from file size
            "modified": f.get("modified", ""),
            "tags": tags[:4],
            "backlink_count": len(backlinks),
        })

        # Build edges from backlinks
        for link in backlinks:
            link_id = link.strip().replace(" ", "_").replace(".md", "")
            edge_key = tuple(sorted([node_id, link_id]))
            if edge_key not in edge_set and node_id != link_id:
                edge_set.add(edge_key)
                edges.append({
                    "id": f"{node_id}--{link_id}",
                    "source": node_id,
                    "target": link_id,
                    "label": "links to",
                })

    return JSONResponse({"nodes": nodes, "edges": edges, "node_count": len(nodes), "edge_count": len(edges)})


# ─────────────────────────────────────────────
# Stats API
# ─────────────────────────────────────────────
@app.get("/api/stats")
async def api_stats():
    """Return knowledge base statistics."""
    wiki_files = list_wiki_files()
    raw_files = list_raw_files()

    # Vector store stats
    vs_stats = {}
    try:
        from nexus.vector_store import get_vector_store
        vs_stats = get_vector_store().get_stats()
    except Exception:
        pass

    return JSONResponse({
        "wiki_files": wiki_files.get("count", 0),
        "raw_files": raw_files.get("count", 0),
        "vector_store": vs_stats,
        "ui_mode": UI_MODE,
        "timestamp": datetime.now().isoformat(),
    })


# ─────────────────────────────────────────────
# Semantic Search API
# ─────────────────────────────────────────────
@app.post("/api/semantic-search")
async def api_semantic_search(body: dict):
    """Run a semantic similarity search over the knowledge base."""
    query = body.get("query", "").strip()
    n = int(body.get("n_results", 5))
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    return JSONResponse(semantic_search(query, n))


@app.post("/api/sync-vectorstore")
async def api_sync_vectorstore():
    """Re-index all wiki files into the vector store."""
    try:
        from nexus.vector_store import get_vector_store
        result = get_vector_store().sync_wiki(str(WIKI_DIR))
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Educator API
# ─────────────────────────────────────────────
@app.post("/api/educator/roadmap")
async def api_generate_roadmap(body: dict):
    """Generate a structured learning roadmap."""
    goal = body.get("goal", "").strip()
    if not goal:
        raise HTTPException(status_code=400, detail="goal is required")
    try:
        from nexus.educator.engine import generate_roadmap
        result = generate_roadmap(goal, body.get("context", ""))
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/educator/flashcards")
async def api_generate_flashcards(body: dict):
    """Generate a flashcard deck for a topic."""
    topic = body.get("topic", "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    try:
        from nexus.educator.engine import generate_flashcards
        result = generate_flashcards(topic)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/educator/quiz/start")
async def api_start_quiz(body: dict):
    """Start a quiz session on a topic."""
    topic = body.get("topic", "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic is required")
    try:
        from nexus.educator.engine import start_quiz
        result = start_quiz(
            topic,
            difficulty=body.get("difficulty", "medium"),
            num_questions=int(body.get("num_questions", 5)),
        )
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/educator/quiz/answer")
async def api_answer_quiz(body: dict):
    """Submit an answer for the current quiz question."""
    quiz_id = body.get("quiz_id", "").strip()
    answer = body.get("answer", "").strip()
    if not quiz_id or not answer:
        raise HTTPException(status_code=400, detail="quiz_id and answer are required")
    try:
        from nexus.educator.engine import evaluate_answer
        result = evaluate_answer(quiz_id, answer)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/educator/profile")
async def api_get_profile():
    """Get the student proficiency profile."""
    try:
        from nexus.educator.student_profile import load_profile
        return JSONResponse(load_profile())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# WebSocket — Legacy single-agent streaming
# ─────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_legacy(websocket: WebSocket):
    """Original single-agent WebSocket endpoint (preserved for backward compat)."""
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
        except Exception:
            pass


# ─────────────────────────────────────────────
# WebSocket — Nexus multi-agent pipeline
# ─────────────────────────────────────────────
@app.websocket("/ws/nexus")
async def websocket_nexus(websocket: WebSocket):
    """
    Multi-agent Nexus pipeline WebSocket.
    Receives: {"message": "...", "mode": "nexus"}
    Emits:    agent_start, agent_thinking, agent_tool_call, agent_tool_result,
              agent_handoff, wiki_update, agent_complete, answer, done
    """
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            task = data.get("message", "").strip()
            if not task:
                continue

            await websocket.send_text(json.dumps({
                "type": "thinking",
                "content": "🚀 Initializing Nexus multi-agent pipeline...",
            }))

            try:
                from nexus.agents.graph import run_nexus_pipeline
                final_state = await run_nexus_pipeline(task, websocket=websocket)

                # Emit any buffered events not sent via callbacks
                for event in final_state.get("agent_events", []):
                    try:
                        await websocket.send_text(json.dumps(event))
                    except Exception:
                        break

                # Final answer
                answer = final_state.get("final_answer", "Research pipeline completed.")
                await websocket.send_text(json.dumps({"type": "answer", "content": answer}))

            except ImportError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": "Nexus agents not available. Install langchain and langgraph.",
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": f"Nexus pipeline error: {str(e)[:300]}",
                }))

            await websocket.send_text(json.dumps({"type": "done"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "content": str(e)}))
        except Exception:
            pass


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """React SPA catch-all — serve index.html for client-side routing."""
    if UI_MODE == "react":
        index = NEXUS_UI_DIST / "index.html"
        if index.exists() and not full_path.startswith("api"):
            return FileResponse(str(index))
    raise HTTPException(status_code=404)


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("\n╔══════════════════════════════════════╗")
    print("║       NEXUS-KNOWLEDGE  v2.0.0        ║")
    print("╠══════════════════════════════════════╣")
    print(f"║  UI Mode  : {UI_MODE:<25}║")
    print(f"║  Wiki Dir : {str(WIKI_DIR)[:25]:<25}║")
    print("║  URL      : http://localhost:8000    ║")
    print("╚══════════════════════════════════════╝\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
