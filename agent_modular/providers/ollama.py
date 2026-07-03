# agent_modular/providers/ollama.py
"""
Ollama provider for local LLM inference.
Wraps the Ollama HTTP API to match the LLMProvider interface.
Falls back to Gemini if Ollama is unreachable.
"""

import os
import json
import requests
from typing import List, Dict, Any, Optional
from .base import LLMProvider, UnifiedResponse


OLLAMA_DEFAULT_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "llama3.2:latest"


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url: str = OLLAMA_DEFAULT_URL
        self.model: str = OLLAMA_DEFAULT_MODEL
        self.is_available: bool = False
        self._fallback_provider: Optional[LLMProvider] = None

    def initialize(self, config: Dict[str, Any]) -> Any:
        self.base_url = config.get("ollama_base_url", os.getenv("OLLAMA_BASE_URL", OLLAMA_DEFAULT_URL))
        self.model = config.get("model", os.getenv("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL))

        # Check if Ollama is reachable
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            self.is_available = resp.status_code == 200
        except Exception:
            self.is_available = False

        if not self.is_available:
            print(f"[Ollama] Not reachable at {self.base_url}, will fallback to Gemini")
            self._init_fallback(config)

        return self

    def _init_fallback(self, config: Dict[str, Any]) -> None:
        """Initialize Gemini as fallback when Ollama is unavailable."""
        try:
            from .gemini import GeminiProvider
            self._fallback_provider = GeminiProvider()
            fallback_config = {**config, "provider": "gemini"}

            # Get Gemini API key
            api_key = os.getenv("GEMINI_API_KEY", "")
            if api_key:
                fallback_config["api_key"] = api_key
                self._fallback_provider.initialize(fallback_config)
            else:
                self._fallback_provider = None
                print("[Ollama] No GEMINI_API_KEY for fallback either")
        except Exception:
            self._fallback_provider = None

    def send_message(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> UnifiedResponse:
        # Use fallback if Ollama isn't available
        if not self.is_available and self._fallback_provider:
            return self._fallback_provider.send_message(messages, tools, config)

        if not self.is_available:
            return UnifiedResponse(
                thinking=[],
                tool_calls=[],
                text_output=["Error: Ollama is not available and no fallback configured."],
            )

        # Format messages for Ollama
        ollama_messages = self._format_messages(messages)

        # Format tools for Ollama (uses OpenAI-compatible format)
        ollama_tools = self._format_tools(tools)

        # Build request payload
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": config.get("temperature", 0.1),
            },
        }

        # Add system prompt
        system_prompt = config.get("system_prompt", "")
        if system_prompt:
            payload["messages"].insert(0, {"role": "system", "content": system_prompt})

        # Add tools if available
        if ollama_tools:
            payload["tools"] = ollama_tools

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            return self._parse_response(result)

        except requests.exceptions.ConnectionError:
            self.is_available = False
            if self._fallback_provider:
                return self._fallback_provider.send_message(messages, tools, config)
            return UnifiedResponse(
                thinking=[],
                tool_calls=[],
                text_output=["Error: Lost connection to Ollama server."],
            )
        except Exception as e:
            return UnifiedResponse(
                thinking=[],
                tool_calls=[],
                text_output=[f"Ollama API error: {str(e)}"],
            )

    def format_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in history:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"

            content = msg.get("content", "")
            if isinstance(content, list):
                # Handle parts format
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                content = "\n".join(text_parts)

            formatted.append({"role": role, "content": content})
        return formatted

    def convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert tools to Ollama format (OpenAI-compatible)."""
        return self._format_tools(tools)

    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert internal message format to Ollama format."""
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"

            # Handle different content formats
            if "content" in msg:
                content = msg["content"]
                if isinstance(content, str):
                    formatted.append({"role": role, "content": content})
                elif isinstance(content, list):
                    text = " ".join(
                        p.get("text", str(p)) if isinstance(p, dict) else str(p)
                        for p in content
                    )
                    formatted.append({"role": role, "content": text})
            elif "parts" in msg:
                parts = msg["parts"]
                text_parts = []
                for p in parts:
                    if isinstance(p, dict) and "text" in p:
                        text_parts.append(p["text"])
                    elif isinstance(p, str):
                        text_parts.append(p)
                if text_parts:
                    formatted.append({"role": role, "content": " ".join(text_parts)})
        return formatted

    @staticmethod
    def _format_tools(tools: List[Any]) -> List[Dict[str, Any]]:
        """Convert tool declarations to Ollama's OpenAI-compatible format."""
        ollama_tools = []
        for tool in tools:
            # If already in OpenAI format
            if isinstance(tool, dict) and "type" in tool and tool["type"] == "function":
                ollama_tools.append(tool)
            # If it's a Gemini Tool object, extract declarations
            elif hasattr(tool, "function_declarations"):
                for decl in tool.function_declarations:
                    ollama_tools.append({
                        "type": "function",
                        "function": {
                            "name": decl.name,
                            "description": decl.description or "",
                            "parameters": _extract_params(decl),
                        },
                    })
            # If it's a raw dict declaration
            elif isinstance(tool, dict) and "name" in tool:
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    },
                })
        return ollama_tools

    def _parse_response(self, result: Dict[str, Any]) -> UnifiedResponse:
        """Parse Ollama API response into UnifiedResponse."""
        thinking = []
        tool_calls = []
        text_output = []

        message = result.get("message", {})
        content = message.get("content", "")
        if content:
            text_output.append(content)

        # Parse tool calls
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            arguments = func.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            if name:
                tool_calls.append({"name": name, "arguments": arguments})

        return UnifiedResponse(
            thinking=thinking,
            tool_calls=tool_calls,
            text_output=text_output,
        )


def _extract_params(decl: Any) -> Dict[str, Any]:
    """Safely extract parameters from a Gemini FunctionDeclaration."""
    try:
        if hasattr(decl, "parameters") and decl.parameters:
            # Convert proto-like object to dict
            params = decl.parameters
            if hasattr(params, "to_dict"):
                return params.to_dict()
            elif isinstance(params, dict):
                return params
    except Exception:
        pass
    return {"type": "object", "properties": {}}
