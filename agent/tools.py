"""
tools.py - All tool implementations for the Wiki-LLM agent.
The agent can read/write wiki files, list notes, execute Python code, and search.
"""

import os
import subprocess
import sys
import glob
import re
from pathlib import Path
from datetime import datetime
from google.genai import types
import serpapi

WIKI_DIR = Path(__file__).parent.parent / "wiki"
WIKI_DIR.mkdir(exist_ok=True)
RAW_DIR = Path(__file__).parent.parent / "raw"
RAW_DIR.mkdir(exist_ok=True)
CLIPPINGS_DIR = Path(__file__).parent.parent / "Clippings"
CLIPPINGS_DIR.mkdir(exist_ok=True)
SKILL_DIR = Path(__file__).parent.parent / "Skills"
SKILL_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# Tool: Read a raw file (filename with .txt .md .docx .html .json .csv or regex)
# ─────────────────────────────────────────────
def read_raw_file(filename: str) -> dict:
    """Read the content of a raw file by name (relative to raw/)."""
    filename = Path(filename).name
    path = RAW_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found in raw."}
    try:
        content = path.read_text(encoding="utf-8")
        return {"filename": filename, "content": content, "lines": len(content.splitlines())}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: List raw files
# ─────────────────────────────────────────────
def list_raw_files() -> dict:
    """List all raw files in the raw directory."""
    files = sorted(RAW_DIR.glob("**/*"))
    result = []
    for f in files:
        rel = f.relative_to(RAW_DIR)
        stat = f.stat()
        result.append({
            "name": str(rel),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return {"files": result, "count": len(result)}



# ─────────────────────────────────────────────
# Tool: List wiki files
# ─────────────────────────────────────────────
def list_wiki_files() -> dict:
    """List all markdown files in the wiki directory."""
    files = sorted(WIKI_DIR.glob("**/*.md"))
    result = []
    for f in files:
        rel = f.relative_to(WIKI_DIR)
        stat = f.stat()
        result.append({
            "name": str(rel),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return {"files": result, "count": len(result)}


# ─────────────────────────────────────────────
# Tool: Read a wiki file
# ─────────────────────────────────────────────
def read_wiki_file(filename: str) -> dict:
    """Read the content of a wiki file by name (relative to wiki/)."""
    path = WIKI_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found in wiki."}
    try:
        content = path.read_text(encoding="utf-8")
        return {"filename": filename, "content": content, "lines": len(content.splitlines())}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: Write / update a wiki file
# ─────────────────────────────────────────────
def write_wiki_file(filename: str, content: str) -> dict:
    """Write or overwrite a markdown file in the wiki directory."""
    if not filename.endswith(".md"):
        filename += ".md"
    # Sanitize path — no escaping the wiki dir
    filename = Path(filename).name
    path = WIKI_DIR / filename
    try:
        path.write_text(content, encoding="utf-8")
        return {"success": True, "filename": filename, "bytes_written": len(content.encode())}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: Append to a wiki file
# ─────────────────────────────────────────────
def append_wiki_file(filename: str, content: str) -> dict:
    """Append content to an existing wiki file (creates it if missing)."""
    if not filename.endswith(".md"):
        filename += ".md"
    filename = Path(filename).name
    path = WIKI_DIR / filename
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        new_content = existing + "\n" + content
        path.write_text(new_content, encoding="utf-8")
        return {"success": True, "filename": filename, "total_lines": len(new_content.splitlines())}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: Search wiki
# ─────────────────────────────────────────────
def search_wiki(query: str) -> dict:
    """Search all wiki files for a keyword or phrase (case-insensitive)."""
    query_lower = query.lower()
    results = []
    for path in WIKI_DIR.glob("**/*.md"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        matches = []
        for i, line in enumerate(lines, 1):
            if query_lower in line.lower():
                matches.append({"line": i, "text": line.strip()})
        if matches:
            results.append({"file": path.name, "matches": matches})
    return {"query": query, "results": results, "total_files_matched": len(results)}


# ─────────────────────────────────────────────
# Tool: Execute Python code
# ─────────────────────────────────────────────
def execute_python(code: str) -> dict:
    """Execute a Python code snippet and return stdout/stderr. Timeout: 15s."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {
            "stdout": result.stdout[:4000],
            "stderr": result.stderr[:2000],
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": "Code execution timed out (15s limit)."}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: Delete a wiki file
# ─────────────────────────────────────────────
def delete_wiki_file(filename: str) -> dict:
    """Delete a wiki file by name."""
    filename = Path(filename).name
    path = WIKI_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found."}
    path.unlink()
    return {"success": True, "deleted": filename}

# ────────────────────────────────────────────
# Tool: Google Web-search
# ────────────────────────────────────────────
def google_search(query:str) -> dict:
    """Perform a Google web search and return the top results."""
    client = serpapi.Client(api_key=os.getenv("SERPAPI_KEY"))
    try:
        results = client.search(q=query, engine="google")
        return {"results": results.get("organic_results", [])}
    except Exception as e:
        return {"error": str(e or "Unknown error during search")}

# ____________________________________________
# Tool: List all tools (for debugging)
# ____________________________________________
def list_tools() -> dict:
    """Return a list of all available tools."""
    return {"tools": list(TOOL_MAP.keys())}

# ____________________________________________
# Tool: list clippings
# ____________________________________________
def list_clippings() -> dict:
    """List all clipping files in the clippings directory."""
    CLIPPINGS_DIR = Path(__file__).parent.parent / "Clippings"
    CLIPPINGS_DIR.mkdir(exist_ok=True)
    files = sorted(CLIPPINGS_DIR.glob("**/*.md"))
    result = []
    for f in files:
        rel = f.relative_to(CLIPPINGS_DIR)
        stat = f.stat()
        result.append({
            "name": str(rel),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return {"files": result, "count": len(result)}


# ─────────────────────────────────────────────
# navigate Clippings folder (for agent to access clippings)
# ─────────────────────────────────────────────
def read_clipping_file(filename: str) -> dict:
    """Read the content of a clipping file."""
    path = CLIPPINGS_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found."}
    content = path.read_text(encoding="utf-8", errors="ignore")
    return {"content": content}

# ─────────────────────────────────────────────
# Search clippings
# ─────────────────────────────────────────────
def search_clippings(query: str) -> dict:
    """Search all clipping files for a keyword or phrase (case-insensitive)."""
    CLIPPINGS_DIR = Path(__file__).parent.parent / "Clippings"
    CLIPPINGS_DIR.mkdir(exist_ok=True)
    query_lower = query.lower()
    results = []
    for path in CLIPPINGS_DIR.glob("**/*.md"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        matches = []
        for i, line in enumerate(lines, 1):
            if query_lower in line.lower():
                matches.append({"line": i, "text": line.strip()})
        if matches:
            results.append({"file": path.name, "matches": matches})
    return {"query": query, "results": results, "total_files_matched": len(results)}


# ─────────────────────────────────────────────
# list skills
# ─────────────────────────────────────────────
def list_skills() -> dict:
    """List all skill files in the skills directory."""
    SKILL_DIR = Path(__file__).parent.parent / "Skills"
    SKILL_DIR.mkdir(exist_ok=True)
    files = sorted(SKILL_DIR.glob("**/*.py"))
    result = []
    for f in files:
        rel = f.relative_to(SKILL_DIR)
        stat = f.stat()
        result.append({
            "name": str(rel),
            "size_bytes": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return {"files": result, "count": len(result)}


# ─────────────────────────────────────────────
# navigate Skills folder (for agent to access skills)
# ─────────────────────────────────────────────
def read_skill_file(filename: str) -> dict:
    """Read the content of a skill file."""
    path = SKILL_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found."}
    content = path.read_text(encoding="utf-8", errors="ignore")
    return {"content": content}


# ─────────────────────────────────────────────
# search skills
# ─────────────────────────────────────────────
def search_skills(query: str) -> dict:
    """Search all skill files for a keyword or phrase (case-insensitive)."""
    SKILL_DIR = Path(__file__).parent.parent / "Skills"
    SKILL_DIR.mkdir(exist_ok=True)
    query_lower = query.lower()
    results = []
    for path in SKILL_DIR.glob("**/*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        matches = []
        for i, line in enumerate(lines, 1):
            if query_lower in line.lower():
                matches.append({"line": i, "text": line.strip()})
        if matches:
            results.append({"file": path.name, "matches": matches})
    return {"query": query, "results": results, "total_files_matched": len(results)}

# ─────────────────────────────────────────────
# Gemini function declarations (tool schemas)
# ─────────────────────────────────────────────
TOOL_DECLARATIONS = [
    {
        "name": "list_raw_files",
        "description": "List all files in the raw directory.",
        "parameters": {
            "type": "object",
            "properties": {},
            #"required": [],
        },
    },
    {
        "name": "read_raw_file",
        "description": "Read the content of a file in the raw directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename (e.g. 'source.txt') relative to raw/.",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "list_wiki_files",
        "description": "List all markdown note files in the wiki knowledge base.",
        "parameters": {
            "type": "object",
            "properties": {},
            #"required": [],
        },
    },
    {
        "name": "read_wiki_file",
        "description": "Read the full content of a specific wiki note file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The markdown filename (e.g. 'transformers.md') relative to the wiki directory.",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "write_wiki_file",
        "description": "Create or overwrite a markdown note in the wiki. Use this to save research, summaries, or findings.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename to write (e.g. 'transformers.md').",
                },
                "content": {
                    "type": "string",
                    "description": "The full markdown content to write into the file.",
                },
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "append_wiki_file",
        "description": "Append new content to an existing wiki note (e.g. add new findings to an existing topic).",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "search_wiki",
        "description": "Search the wiki knowledge base for a keyword or phrase across all notes.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search term or phrase to look for.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_python",
        "description": "Execute a Python code snippet and return the output. Use for calculations, data processing, or verification.(allowed libraries: random, numpy, pandas, json, os, date)",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Valid Python code to execute.",
                }
            },
            "required": ["code"],
        },
    },
    {
        "name": "delete_wiki_file",
        "description": "Delete a wiki note file that is no longer needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"}
            },
            "required": ["filename"],
        },
    },
    {
        "name": "google_search",
        "description": "Perform a Google web search and return the top results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_tools",
        "description": "List all available tools.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_clippings",
        "description": "List all clipping files in the clippings directory.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "search_clippings",
        "description": "Search all clipping files for a keyword or phrase (case-insensitive).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_clipping_file",
        "description": "Read the content of a clipping file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename of the clipping to read.",
                }
            },
            "required": ["filename"],
        },
    }
]


# Dispatcher
TOOL_MAP = {
    "list_raw_files": lambda args: list_raw_files(),
    "read_raw_file": lambda args: read_raw_file(args["filename"]),
    "list_wiki_files": lambda args: list_wiki_files(),
    "read_wiki_file": lambda args: read_wiki_file(args["filename"]),
    "write_wiki_file": lambda args: write_wiki_file(args["filename"], args["content"]),
    "append_wiki_file": lambda args: append_wiki_file(args["filename"], args["content"]),
    "search_wiki": lambda args: search_wiki(args["query"]),
    "execute_python": lambda args: execute_python(args["code"]),
    "delete_wiki_file": lambda args: delete_wiki_file(args["filename"]),
    "google_search": lambda args: google_search(args["query"]),
    "list_tools": lambda args: list_tools(),
    "list_clippings": lambda args: list_clippings(),
    "search_clippings": lambda args: search_clippings(args["query"]),
    "read_clipping_file": lambda args: read_clipping_file(args["filename"])
}


def dispatch_tool(name: str, args: dict) -> dict:
    if name in TOOL_MAP:
        return TOOL_MAP[name](args)
    return {"error": f"Unknown tool: {name}"}
