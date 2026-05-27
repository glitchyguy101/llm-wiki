# agent_modular/agent.py
import asyncio
import json
from typing import AsyncGenerator, Dict, Any, List
from dotenv import load_dotenv
from config import load_config
from providers import get_provider_class
from tool_converter import convert_tools_from_unified
from tools import UNIFIED_TOOL_DECLARATIONS, dispatch_tool
import google.genai as genai

load_dotenv()

async def run_agent(task: str, history: List[Dict[str, Any]]) -> AsyncGenerator[Dict[str, Any], None]:
    config = load_config()
    provider_class = get_provider_class(config['provider'])
    provider = provider_class()
    provider.initialize(config)
    
    # Convert tools to provider format
    tools = convert_tools_from_unified(UNIFIED_TOOL_DECLARATIONS, config['provider'])
    
    # Format initial history
    messages = provider.format_chat_history(history + [{'role': 'user', 'content': task}])
    
    max_iterations = config['max_iterations']
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        yield {"type": "thinking", "content": f"🤔 Thinking... (step {iteration})"}
        
        # Send message to provider
        response = provider.send_message(messages, tools, config)
        
        # Yield text output
        for text in response.text_output:
            yield {"type": "thinking", "content": text}
        
        # Handle tool calls
        if response.tool_calls:
            tool_results = []
            for tool_call in response.tool_calls:
                name = tool_call['name']
                args = tool_call['arguments']
                
                yield {
                    "type": "tool_call",
                    "content": f"🔧 Calling tool: **{name}**",
                    "tool": name,
                    "args": args,
                }
                
                result = dispatch_tool(name, args)
                
                yield {
                    "type": "tool_result",
                    "content": f"✅ Tool `{name}` result received.",
                    "tool": name,
                    "result": result,
                }
                
                # Format tool result for next message
                if config['provider'] == 'gemini':
                    tool_results.append(
                        genai.types.Part.from_function_response(
                            name=name,
                            response={"result": result}
                        )
                    )
                # Add other provider formats as needed
            
            # Add tool results to messages for next iteration
            messages.append({'role': 'model', 'parts': tool_results})
        else:
            # No more tool calls, final answer
            yield {"type": "answer", "content": "\n".join(response.text_output)}
            return
    
    yield {"type": "answer", "content": "Max steps reached. Check the wiki for details!"}
