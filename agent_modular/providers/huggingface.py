# agent_modular/providers/huggingface.py
from huggingface_hub import InferenceClient
from typing import List, Dict, Any
from .base import LLMProvider, UnifiedResponse

class HuggingFaceProvider(LLMProvider):
    def __init__(self):
        self.client = None

    def initialize(self, config: Dict[str, Any]) -> Any:
        api_key = config.get('api_key')
        if not api_key:
            raise ValueError("HUGGINGFACE_API_KEY required")
        self.client = InferenceClient(api_key=api_key)
        return self.client

    def send_message(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], config: Dict[str, Any]) -> UnifiedResponse:
        if not self.client:
            self.initialize(config)
        
        # Format messages for HuggingFace
        hf_messages = self.format_chat_history(messages)
        
        # HuggingFace inference API may not support tools directly, so for now, assume text-only
        # This is a placeholder; actual implementation would depend on the model
        
        prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in hf_messages])
        
        response = self.client.conversational(
            {
                "inputs": {
                    "past_user_inputs": [],
                    "generated_responses": [],
                    "text": prompt
                },
                "parameters": {
                    "max_length": 512,
                    "temperature": config.get('temperature', 0.1)
                }
            }
        )
        
        # Parse response (simplified)
        text_output = [response['generated_text']]
        
        return UnifiedResponse(
            thinking=[],
            tool_calls=[],  # Not supported yet
            text_output=text_output
        )

    def format_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Simple formatting
        return history

    def convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Not supported yet
        return []