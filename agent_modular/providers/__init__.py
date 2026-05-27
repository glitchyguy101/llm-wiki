from .base import LLMProvider, UnifiedResponse
from .gemini import GeminiProvider
from .openai import OpenAIProvider
from .huggingface import HuggingFaceProvider

def get_provider_class(provider_name: str):
    providers = {
        'gemini': GeminiProvider,
        'openai': OpenAIProvider,
        'groq': OpenAIProvider,  # Groq uses OpenAI-compatible API
        'huggingface': HuggingFaceProvider
    }
    return providers.get(provider_name, GeminiProvider)

__all__ = ['LLMProvider', 'UnifiedResponse', 'GeminiProvider', 'OpenAIProvider', 'HuggingFaceProvider', 'get_provider_class']