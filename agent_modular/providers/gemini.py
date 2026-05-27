# agent_modular/providers/gemini.py
import google.genai as genai
from google.genai.types import FunctionDeclaration, Tool, GenerateContentConfig
from typing import List, Dict, Any
from .base import LLMProvider, UnifiedResponse

class GeminiProvider(LLMProvider):
    def __init__(self):
        self.client = None
        self.chat = None

    def initialize(self, config: Dict[str, Any]) -> Any:
        api_key = config.get('api_key')
        if not api_key:
            raise ValueError("GEMINI_API_KEY required")
        self.client = genai.Client(api_key=api_key)
        return self.client

    def send_message(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], config: Dict[str, Any]) -> UnifiedResponse:
        if not self.client:
            self.initialize(config)
        
        # Format messages for Gemini
        chat_history = self.format_chat_history(messages)
        
        # Convert tools
        gemini_tools = self.convert_tools(tools)
        
        # Create chat session if not exists
        if not self.chat:
            self.chat = self.client.chats.create(
                model=config.get('model', 'gemini-2.5-flash-lite'),
                config=GenerateContentConfig(
                    system_instruction=config.get('system_prompt', ''),
                    tools=gemini_tools,
                    temperature=config.get('temperature', 0.1),
                ),
                history=chat_history[:-1] if len(chat_history) > 1 else []  # Exclude the last message as it's the new input
            )
        
        # Send the last message
        if not chat_history:
            last_message = ''
        else:
            parts = chat_history[-1]['parts']
            if parts and isinstance(parts[0], dict) and 'text' in parts[0]:
                last_message = parts[0]['text']
            elif parts:
                last_message = parts
            else:
                last_message = ''
                
        response = self.chat.send_message(last_message)
        
        # Parse response
        return self._parse_response(response)

    def format_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in history:
            role = msg['role']
            if role == 'assistant':
                role = 'model'
            
            if 'content' in msg:
                parts = [{'text': msg['content']}] if isinstance(msg['content'], str) else msg['content']
            elif 'parts' in msg:
                parts = msg['parts']
            else:
                parts = []
                
            formatted.append({
                'role': role,
                'parts': parts
            })
        return formatted

    def convert_tools(self, tools: List[Any]) -> List[Any]:
        # Tools are already converted by tool_converter.py in agent.py
        return tools

    def _parse_response(self, response) -> UnifiedResponse:
        thinking = []
        tool_calls = []
        text_output = []
        
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    tool_calls.append({
                        'name': part.function_call.name,
                        'arguments': dict(part.function_call.args)
                    })
                elif hasattr(part, 'text') and part.text:
                    text_output.append(part.text)
        
        return UnifiedResponse(
            thinking=thinking,
            tool_calls=tool_calls,
            text_output=text_output,
            grounding_metadata=response.candidates[0].grounding_metadata if response.candidates and response.candidates[0].grounding_metadata else None
        )