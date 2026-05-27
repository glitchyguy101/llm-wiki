# agent_modular/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class UnifiedResponse:
    thinking: List[str]
    tool_calls: List[Dict[str, Any]]
    text_output: List[str]
    grounding_metadata: Optional[Dict[str, Any]] = None

class LLMProvider(ABC):
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> Any:
        """Initialize the provider client."""
        pass

    @abstractmethod
    def send_message(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], config: Dict[str, Any]) -> UnifiedResponse:
        """Send a message to the LLM and return a unified response."""
        pass

    @abstractmethod
    def format_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format chat history for the provider."""
        pass

    @abstractmethod
    def convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert tools to provider-specific format."""
        pass