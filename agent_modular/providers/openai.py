# agent_modular/providers/openai.py
import openai
import json
from typing import List, Dict, Any
from .base import LLMProvider, UnifiedResponse

class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.client = None

    def initialize(self, config: Dict[str, Any]) -> Any:
        api_key = config.get('api_key')
        base_url = None
        if config['provider'] == 'groq':
            base_url = "https://api.groq.com/openai/v1"
        if not api_key:
            raise ValueError(f"{config['provider'].upper()}_API_KEY required")
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        return self.client

    def send_message(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], config: Dict[str, Any]) -> UnifiedResponse:
        if not self.client:
            self.initialize(config)
        
        # Format messages for OpenAI
        openai_messages = self.format_chat_history(messages)
        
        # Convert tools
        openai_tools = self.convert_tools(tools)
        
        response = self.client.chat.completions.create(
            model=config.get('model', 'gpt-4-turbo'),
            messages=openai_messages,
            tools=openai_tools,
            temperature=config.get('temperature', 0.1),
            max_tokens=4096
        )
        
        # Parse response
        return self._parse_response(response)

    def format_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in history:
            role = msg['role']
            if role == 'model':
                role = 'assistant'
            formatted.append({
                'role': role,
                'content': msg['content']
            })
        return formatted

    def convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                'type': 'function',
                'function': {
                    'name': tool['name'],
                    'description': tool['description'],
                    'parameters': tool['parameters']
                }
            })
        return openai_tools

    def _parse_response(self, response) -> UnifiedResponse:
        thinking = []
        tool_calls = []
        text_output = []
        
        choice = response.choices[0]
        message = choice.message
        
        if message.content:
            text_output.append(message.content)
        
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append({
                    'name': tool_call.function.name,
                    'arguments': json.loads(tool_call.function.arguments)
                })
        
        return UnifiedResponse(
            thinking=thinking,
            tool_calls=tool_calls,
            text_output=text_output
        )