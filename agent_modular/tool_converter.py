# agent_modular/tool_converter.py
from typing import List, Dict, Any

def convert_tools_to_unified(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert provider-specific tools to unified format (JSON Schema)."""
    unified = []
    for tool in tools:
        if 'function_declarations' in tool:
            # Gemini format
            for decl in tool['function_declarations']:
                unified.append({
                    'name': decl['name'],
                    'description': decl['description'],
                    'parameters': decl['parameters']
                })
        elif 'functions' in tool:
            # OpenAI format
            for func in tool['functions']:
                unified.append({
                    'name': func['name'],
                    'description': func['description'],
                    'parameters': func['parameters']
                })
        # Add other formats as needed
    return unified

def convert_tools_from_unified(unified_tools: List[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
    """Convert unified tools to provider-specific format."""
    if provider == 'gemini':
        from google.genai.types import FunctionDeclaration, Tool
        declarations = []
        for tool in unified_tools:
            declarations.append(
                FunctionDeclaration(
                    name=tool['name'],
                    description=tool['description'],
                    parameters=tool['parameters'],
                )
            )
        return [Tool(function_declarations=declarations)]
    elif provider in ['openai', 'groq']:
        # OpenAI format
        return [{
            'type': 'function',
            'function': {
                'name': tool['name'],
                'description': tool['description'],
                'parameters': tool['parameters']
            }
        } for tool in unified_tools]
    # Add other providers
    return unified_tools