"""
tools.py - All tool implementations for the Wiki-LLM / Nexus-Knowledge agent.
Extends the original agent_modular tools with:
  - semantic_search (ChromaDB)
  - parse_document (PDF, image, DOCX auto-detect)
  - parse_url (web article extraction)
  - upload_raw_file (base64 upload + auto-ingest)
"""

import os
import sys
import subprocess
import glob
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Add nexus to path so tools can import it ──────────────────────────────────
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

WIKI_DIR = _ROOT / "wiki"
WIKI_DIR.mkdir(exist_ok=True)
RAW_DIR = _ROOT / "raw"
RAW_DIR.mkdir(exist_ok=True)
CLIPPINGS_DIR = _ROOT / "Clippings"
CLIPPINGS_DIR.mkdir(exist_ok=True)
SKILL_DIR = _ROOT / "Skills"
SKILL_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# Lazy imports for optional dependencies
# ─────────────────────────────────────────────
def _get_vector_store():
    try:
        from nexus.vector_store import get_vector_store
        return get_vector_store()
    except Exception:
        return None

def _get_parser():
    try:
        from nexus.document_parser import parse_file, parse_url as _parse_url
        return parse_file, _parse_url
    except Exception:
        return None, None


# ─────────────────────────────────────────────
# Tool: Read a raw file (with multi-format parsing)
# ─────────────────────────────────────────────
def read_raw_file(filename: str) -> dict:
    """Read and parse the content of a raw file (supports PDF, image, DOCX, TXT, MD)."""
    filename = Path(filename).name
    path = RAW_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found in raw."}

    parse_file, _ = _get_parser()
    if parse_file:
        doc = parse_file(str(path))
        if doc.error:
            # Fallback to plain text
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                return {"filename": filename, "content": content, "lines": len(content.splitlines())}
            except Exception as e:
                return {"error": str(e)}
        return {
            "filename": filename,
            "content": doc.content,
            "title": doc.title,
            "source_type": doc.source_type,
            "lines": len(doc.content.splitlines()),
            "metadata": doc.metadata,
        }

    # Plain text fallback (no nexus parser)
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return {"filename": filename, "content": content, "lines": len(content.splitlines())}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: Parse a document from /raw (explicit parser call)
# ─────────────────────────────────────────────
def parse_document(filename: str) -> dict:
    """
    Parse a document from the /raw directory using the appropriate parser.
    Supports PDF (text + tables), images (AI vision), DOCX, CSV, JSON, TXT.
    Returns extracted text content as markdown.
    """
    filename = Path(filename).name
    path = RAW_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found in raw."}

    parse_file, _ = _get_parser()
    if not parse_file:
        return {"error": "Document parser not available. Ensure nexus/ package is installed."}

    doc = parse_file(str(path))
    if doc.error:
        return {"error": doc.error}

    return {
        "filename": filename,
        "title": doc.title,
        "source_type": doc.source_type,
        "content": doc.content,
        "lines": len(doc.content.splitlines()),
        "metadata": doc.metadata,
    }


# ─────────────────────────────────────────────
# Tool: Parse a URL
# ─────────────────────────────────────────────
def parse_url(url: str) -> dict:
    """
    Fetch and extract the main article content from a web URL.
    Returns clean markdown-formatted text with title and source metadata.
    Strips navigation, ads, and boilerplate.
    """
    _, url_parser = _get_parser()
    if not url_parser:
        return {"error": "URL parser not available. Install trafilatura or beautifulsoup4."}

    doc = url_parser(url)
    if doc.error:
        return {"error": doc.error, "url": url}

    return {
        "url": url,
        "title": doc.title,
        "source_type": doc.source_type,
        "content": doc.content,
        "lines": len(doc.content.splitlines()),
        "metadata": doc.metadata,
    }


# ─────────────────────────────────────────────
# Tool: Semantic search (ChromaDB)
# ─────────────────────────────────────────────
def semantic_search(query: str, n_results: int = 5) -> dict:
    """
    Search the knowledge base using semantic similarity (vector search).
    Returns the most relevant chunks from indexed wiki and raw documents.
    More powerful than keyword search — finds conceptually related content.
    """
    store = _get_vector_store()
    if not store:
        # Graceful fallback to keyword search
        return search_wiki(query)

    results = store.semantic_search(query, n_results=n_results)
    if not results:
        return {"query": query, "results": [], "total_results": 0}

    return {
        "query": query,
        "results": [
            {
                "content": r.content,
                "source": r.source,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in results
        ],
        "total_results": len(results),
    }


# ─────────────────────────────────────────────
# Tool: Ingest document into vector store
# ─────────────────────────────────────────────
def ingest_document(filename: str) -> dict:
    """
    Parse and ingest a document from /raw into the semantic vector store.
    Call this after uploading a new file to make it searchable.
    """
    filename = Path(filename).name
    path = RAW_DIR / filename
    if not path.exists():
        return {"error": f"File '{filename}' not found in raw."}

    store = _get_vector_store()
    if not store:
        return {"error": "Vector store not available."}

    parse_file, _ = _get_parser()
    content = ""
    source_type = "text"
    if parse_file:
        doc = parse_file(str(path))
        content = doc.content if not doc.error else ""
        source_type = doc.source_type

    if not content:
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return {"error": str(e)}

    result = store.ingest_document(content, source=filename, metadata={"source_type": source_type})
    return result


# ─────────────────────────────────────────────
# Tool: List raw files
# ─────────────────────────────────────────────
def list_raw_files() -> dict:
    """List all raw files in the raw directory."""
    files = sorted(RAW_DIR.glob("**/*"))
    result = []
    for f in files:
        if f.is_file():
            rel = f.relative_to(RAW_DIR)
            stat = f.stat()
            result.append({
                "name": str(rel),
                "extension": f.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return {"files": result, "count": len(result)}


# ─────────────────────────────────────────────
# Tool: List wiki files
# ─────────────────────────────────────────────
def list_wiki_files() -> dict:
    """List all markdown files in the wiki knowledge base."""
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
    """Read the full content of a specific wiki note file."""
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
    """Create or overwrite a markdown note in the wiki. Automatically indexes in vector store."""
    if not filename.endswith(".md"):
        filename += ".md"
    filename = Path(filename).name
    path = WIKI_DIR / filename
    try:
        path.write_text(content, encoding="utf-8")

        # Auto-ingest into vector store
        store = _get_vector_store()
        if store:
            store.ingest_document(content, source=filename, metadata={"type": "wiki"})

        return {"success": True, "filename": filename, "bytes_written": len(content.encode())}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: Append to a wiki file
# ─────────────────────────────────────────────
def append_wiki_file(filename: str, content: str) -> dict:
    """Append new content to an existing wiki note (creates it if missing)."""
    if not filename.endswith(".md"):
        filename += ".md"
    filename = Path(filename).name
    path = WIKI_DIR / filename
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        new_content = existing + "\n" + content
        path.write_text(new_content, encoding="utf-8")

        # Re-ingest updated file
        store = _get_vector_store()
        if store:
            store.ingest_document(new_content, source=filename, metadata={"type": "wiki"})

        return {"success": True, "filename": filename, "total_lines": len(new_content.splitlines())}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# Tool: Keyword search wiki
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
    """Delete a wiki note file that is no longer needed."""
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
    try:
        import serpapi
    except ImportError:
        return {"error": "serpapi module is not installed. Install with `pip install serpapi`."}

    client = serpapi.Client(api_key=os.getenv("SERPAPI_KEY"))
    try:
        results = client.search(q=query, engine="google")
        return {"results": results.get("organic_results", [])}
    except Exception as e:
        return {"error": str(e or "Unknown error during search")}


# ─────────────────────────────────────────────
# Tool: Sync wiki to vector store
# ─────────────────────────────────────────────
def sync_wiki_to_vectorstore() -> dict:
    """Re-index all wiki files into the semantic vector store. Run after bulk changes."""
    store = _get_vector_store()
    if not store:
        return {"error": "Vector store not available."}
    return store.sync_wiki(str(WIKI_DIR))



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
# Unified Tool Declarations (JSON Schema)
# ─────────────────────────────────────────────
UNIFIED_TOOL_DECLARATIONS = [
    {
        "name": "list_raw_files",
        "description": "List all files in the raw directory (PDFs, images, text, DOCX, etc).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "read_raw_file",
        "description": "Read and parse a file from the /raw directory. Automatically handles PDF, image (AI vision), DOCX, CSV, JSON, and text formats.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The filename (e.g. 'paper.pdf') relative to raw/."}
            },
            "required": ["filename"],
        },
    },
    {
        "name": "parse_document",
        "description": "Explicitly parse a document from /raw using AI-powered extraction. Best for PDFs with tables, images with diagrams/handwriting, and DOCX files.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The filename to parse (e.g. 'lecture.pdf', 'diagram.png')."}
            },
            "required": ["filename"],
        },
    },
    {
        "name": "parse_url",
        "description": "Fetch a web URL and extract the main article content as clean markdown. Strips navigation, ads, and boilerplate. Great for research from web pages.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The full URL to fetch (e.g. 'https://arxiv.org/abs/...')"}
            },
            "required": ["url"],
        },
    },
    {
        "name": "semantic_search",
        "description": "Search the knowledge base using semantic similarity. Finds conceptually related content even if exact keywords differ. Use this before keyword search.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query or concept to find."},
                "n_results": {"type": "integer", "description": "Number of results to return (default: 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ingest_document",
        "description": "Parse and index a /raw document into the semantic vector store to make it searchable.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The filename to ingest."}
            },
            "required": ["filename"],
        },
    },
    {
        "name": "sync_wiki_to_vectorstore",
        "description": "Re-index all wiki markdown files into the vector store. Run this after bulk wiki updates.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "list_wiki_files",
        "description": "List all markdown note files in the wiki knowledge base.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "read_wiki_file",
        "description": "Read the full content of a specific wiki note file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The markdown filename (e.g. 'transformers.md')."}
            },
            "required": ["filename"],
        },
    },
    {
        "name": "write_wiki_file",
        "description": "Create or overwrite a markdown note in the wiki. Automatically indexes in vector store.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The filename to write (e.g. 'transformers.md')."},
                "content": {"type": "string", "description": "The full markdown content to write."},
            },
            "required": ["filename", "content"],
        },
    },
    {
        "name": "append_wiki_file",
        "description": "Append new content to an existing wiki note (creates if missing).",
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
        "description": "Keyword search across all wiki files. Use semantic_search first for better results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search term or phrase."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_python",
        "description": "Execute a Python code snippet and return the output.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Valid Python code to execute."}
            },
            "required": ["code"],
        },
    },
    {
        "name": "delete_wiki_file",
        "description": "Delete a wiki note file that is no longer needed.",
        "parameters": {
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
    },
    {
        "name": "google_search",
        "description": "Search the web using DuckDuckGo and return top results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."}
            },
            "required": ["query"],
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
    },
    {
        "name": "list_skills",
        "description": "List all skill files in the skills directory.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    }, 
    {
        "name": "search_skills",
        "description": "Search all skill files for a keyword or phrase (case-insensitive).",
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
        "name": "read_skill_file",
        "description": "Read the content of a skill file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename of the skill to read.",
                }
            },
            "required": ["filename"],
        },
    },
]


# ─────────────────────────────────────────────
# Tool Dispatcher
# ─────────────────────────────────────────────
TOOL_MAP = {
    "list_raw_files":          lambda args: list_raw_files(),
    "read_raw_file":           lambda args: read_raw_file(args["filename"]),
    "parse_document":          lambda args: parse_document(args["filename"]),
    "parse_url":               lambda args: parse_url(args["url"]),
    "semantic_search":         lambda args: semantic_search(args["query"], args.get("n_results", 5)),
    "ingest_document":         lambda args: ingest_document(args["filename"]),
    "sync_wiki_to_vectorstore":lambda args: sync_wiki_to_vectorstore(),
    "list_wiki_files":         lambda args: list_wiki_files(),
    "read_wiki_file":          lambda args: read_wiki_file(args["filename"]),
    "write_wiki_file":         lambda args: write_wiki_file(args["filename"], args["content"]),
    "append_wiki_file":        lambda args: append_wiki_file(args["filename"], args["content"]),
    "search_wiki":             lambda args: search_wiki(args["query"]),
    "execute_python":          lambda args: execute_python(args["code"]),
    "delete_wiki_file":        lambda args: delete_wiki_file(args["filename"]),
    "google_search": lambda args: google_search(args["query"]),
    "list_tools": lambda args: list_tools(),
    "list_clippings": lambda args: list_clippings(),
    "search_clippings": lambda args: search_clippings(args["query"]),
    "read_clipping_file": lambda args: read_clipping_file(args["filename"]),
    "list_skills": lambda args: list_skills(),
    "search_skills": lambda args: search_skills(args["query"]),
    "read_skill_file": lambda args: read_skill_file(args["filename"]),
}


def dispatch_tool(name: str, args: dict) -> dict:
    if name in TOOL_MAP:
        return TOOL_MAP[name](args)
    return {"error": f"Unknown tool: {name}"}
