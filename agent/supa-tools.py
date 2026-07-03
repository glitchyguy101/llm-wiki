"""
tools.py - Cloud-native tool implementations for the Wiki-LLM agent using Supabase Storage.
The agent can read/write cloud files, execute Python code, and perform web searches.
"""

import os
import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path
import serpapi
from supabase import create_client, Client

# Initialize Supabase Client using backend environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # Use Service Role Key to bypass RLS policies

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─────────────────────────────────────────────
# Helper functions for abstracting bucket actions
# ─────────────────────────────────────────────
def _list_bucket_files(bucket_name: str, extension: str = None) -> dict:
    try:
        res = supabase.storage.from_(bucket_name).list()
        result = []
        for f in res:
            name = f["name"]
            # Skip placeholders or dotfiles if present
            if name.startswith("."):
                continue
            if extension and not name.endswith(extension):
                continue
                
            metadata = f.get("metadata", {})
            size = metadata.get("size", f.get("id", {}))  # fallback if size key shifts
            modified = f.get("updated_at", datetime.utcnow().isoformat())
            
            result.append({
                "name": name,
                "size_bytes": size if isinstance(size, int) else 0,
                "modified": modified
            })
        return {"files": sorted(result, key=lambda x: x["name"]), "count": len(result)}
    except Exception as e:
        return {"error": f"Failed to list {bucket_name} bucket: {str(e)}"}


def _read_bucket_file(bucket_name: str, filename: str) -> dict:
    filename = Path(filename).name
    try:
        response = supabase.storage.from_(bucket_name).download(filename)
        content = response.decode("utf-8", errors="ignore")
        return {"filename": filename, "content": content, "lines": len(content.splitlines())}
    except Exception as e:
        return {"error": f"File '{filename}' not found or unreadable in storage bucket '{bucket_name}'. Details: {str(e)}"}


def _write_bucket_file(bucket_name: str, filename: str, content: str, content_type: str = "text/plain") -> dict:
    filename = Path(filename).name
    try:
        content_bytes = content.encode("utf-8")
        # Upsert configuration forces overwrite if the file exists
        supabase.storage.from_(bucket_name).upload(
            path=filename,
            file=content_bytes,
            file_options={"x-upsert": "true", "content-type": content_type}
        )
        return {"success": True, "filename": filename, "bytes_written": len(content_bytes)}
    except Exception as e:
        return {"error": f"Failed to write object to cloud storage bucket '{bucket_name}': {str(e)}"}


def _search_bucket_content(bucket_name: str, extension: str, query: str) -> dict:
    query_lower = query.lower()
    results = []
    
    list_res = _list_bucket_files(bucket_name, extension)
    if "error" in list_res:
        return list_res
        
    for f_info in list_res["files"]:
        filename = f_info["name"]
        file_data = _read_bucket_file(bucket_name, filename)
        if "error" in file_data:
            continue
            
        lines = file_data["content"].splitlines()
        matches = []
        for i, line in enumerate(lines, 1):
            if query_lower in line.lower():
                matches.append({"line": i, "text": line.strip()})
        if matches:
            results.append({"file": filename, "matches": matches})
            
    return {"query": query, "results": results, "total_files_matched": len(results)}


# ─────────────────────────────────────────────
# Tool: Raw Files Buckets
# ─────────────────────────────────────────────
def list_raw_files() -> dict:
    """List all raw files in the cloud storage raw bucket."""
    return _list_bucket_files("raw")


def read_raw_file(filename: str) -> dict:
    """Read the content of a raw file by name from the raw bucket."""
    return _read_bucket_file("raw", filename)


# ─────────────────────────────────────────────
# Tool: Wiki Notes Management (Supabase)
# ─────────────────────────────────────────────
def list_wiki_files() -> dict:
    """List all markdown note files in the wiki knowledge base bucket."""
    return _list_bucket_files("wiki", extension=".md")


def read_wiki_file(filename: str) -> dict:
    """Read the full content of a specific wiki note file from cloud storage."""
    if not filename.endswith(".md"):
        filename += ".md"
    return _read_bucket_file("wiki", filename)


def write_wiki_file(filename: str, content: str) -> dict:
    """Create or overwrite a markdown note in the wiki bucket."""
    if not filename.endswith(".md"):
        filename += ".md"
    return _write_bucket_file("wiki", filename, content, content_type="text/markdown")


def append_wiki_file(filename: str, content: str) -> dict:
    """Append new content to an existing cloud wiki note."""
    if not filename.endswith(".md"):
        filename += ".md"
    
    existing_data = _read_bucket_file("wiki", filename)
    existing_content = "" if "error" in existing_data else existing_data["content"]
    
    new_content = existing_content + "\n" + content
    return write_wiki_file(filename, new_content)


def delete_wiki_file(filename: str) -> dict:
    """Delete a wiki note file from cloud storage."""
    if not filename.endswith(".md"):
        filename += ".md"
    filename = Path(filename).name
    try:
        supabase.storage.from_("wiki").remove([filename])
        return {"success": True, "deleted": filename}
    except Exception as e:
        return {"error": f"Failed to delete {filename}: {str(e)}"}


def search_wiki(query: str) -> dict:
    """Search all wiki markdown files in cloud storage for a keyword or phrase (case-insensitive)."""
    return _search_bucket_content("wiki", ".md", query)


# ─────────────────────────────────────────────
# Tool: Clippings Operations
# ─────────────────────────────────────────────
def list_clippings() -> dict:
    """List all clipping files in the clippings bucket."""
    return _list_bucket_files("clippings", extension=".md")


def read_clipping_file(filename: str) -> dict:
    """Read the content of a cloud clipping file."""
    if not filename.endswith(".md"):
        filename += ".md"
    return _read_bucket_file("clippings", filename)


def search_clippings(query: str) -> dict:
    """Search all clipping files in cloud storage for a keyword or phrase."""
    return _search_bucket_content("clippings", ".md", query)


# ─────────────────────────────────────────────
# Tool: Skills Operations
# ─────────────────────────────────────────────
def list_skills() -> dict:
    """List all skill Python scripts in the skills bucket."""
    return _list_bucket_files("skills", extension=".py")


def read_skill_file(filename: str) -> dict:
    """Read the source content of a skill python script from cloud storage."""
    if not filename.endswith(".py"):
        filename += ".py"
    return _read_bucket_file("skills", filename)


def search_skills(query: str) -> dict:
    """Search all skill scripts in cloud storage for a specific string code reference."""
    return _search_bucket_content("skills", ".py", query)


# ─────────────────────────────────────────────
# Tool: Code Execution & Web Search
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


def google_search(query: str) -> dict:
    """Perform a Google web search using SerpApi and return top results."""
    client = serpapi.Client(api_key=os.getenv("SERPAPI_KEY"))
    try:
        results = client.search(q=query, engine="google")
        return {"results": results.get("organic_results", [])}
    except Exception as e:
        return {"error": str(e or "Unknown error during search")}


def list_tools() -> dict:
    """Return a list of all active registered tools."""
    return {"tools": list(TOOL_MAP.keys())}


# ─────────────────────────────────────────────
# Dynamic Tooling Map & Dispatcher Loop
# ─────────────────────────────────────────────
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
    "read_clipping_file": lambda args: read_clipping_file(args["filename"]),
    "list_skills": lambda args: list_skills(),
    "search_skills": lambda args: search_skills(args["query"]),
    "read_skill_file": lambda args: read_skill_file(args["filename"]),
}

def dispatch_tool(name: str, args: dict) -> dict:
    if name in TOOL_MAP:
        return TOOL_MAP[name](args)
    return {"error": f"Unknown tool: {name}"}