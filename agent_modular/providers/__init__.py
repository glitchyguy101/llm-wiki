from .base import LLMProvider, UnifiedResponse
from .gemini import GeminiProvider
from .openai import OpenAIProvider
from .huggingface import HuggingFaceProvider
from .ollama import OllamaProvider

def get_provider_class(provider_name: str):
    providers = {
        'gemini': GeminiProvider,
        'openai': OpenAIProvider,
        'groq': OpenAIProvider,       # Groq uses OpenAI-compatible API
        'huggingface': HuggingFaceProvider,
        'ollama': OllamaProvider,     # Local LLM via Ollama
    }
    return providers.get(provider_name, GeminiProvider)

__all__ = [
    'LLMProvider', 'UnifiedResponse',
    'GeminiProvider', 'OpenAIProvider',
    'HuggingFaceProvider', 'OllamaProvider',
    'get_provider_class',
]