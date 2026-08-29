from typing import Any, Dict

from ai.base import (
    AIProvider,
    AIResponse,
    ReviewContext,
    ProviderRegistry,
)

from ai.local_llm import LocalLLMProvider
from ai.cloud_api import CloudAPIProvider
from ai.mock_api import MockAPIProvider

__all__ = [
    "AIProvider",
    "AIResponse",
    "ReviewContext",
    "ProviderRegistry",
    "LocalLLMProvider",
    "CloudAPIProvider",
    "MockAPIProvider",
    "create_provider",
    "get_available_provider",
]


async def create_provider(provider_type: str, config: Dict[str, Any]) -> AIProvider:
    return ProviderRegistry.get(provider_type, config)


async def get_available_provider(config: Dict[str, Any]) -> AIProvider:
    provider_config = config.get("ai", {})
    provider_type = provider_config.get("provider", "auto")
    
    if provider_type == "auto":
        for ptype in ["cloud", "local", "mock"]:
            try:
                provider = await create_provider(ptype, provider_config.get(ptype, {}))
                if await provider.is_available():
                    return provider
            except Exception:
                continue
        return await create_provider("mock", {})
    
    return await create_provider(provider_type, provider_config.get(provider_type, {}))