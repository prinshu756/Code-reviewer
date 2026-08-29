from __future__ import annotations

import json
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ai.base import AIProvider, AIResponse, ReviewContext, ProviderRegistry
from analyzer import Issue


class LocalLLMProvider(AIProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "codellama:7b")
        self.timeout = config.get("timeout", 120)
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 4096)
        self.client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=self.timeout)
        return self.client
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate(self, prompt: str, system: str = "") -> str:
        client = await self._get_client()
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        
        response = await client.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data.get("response", "")
    
    async def review_code(self, context: ReviewContext) -> AIResponse:
        prompt = self._build_review_prompt(context)
        system = "You are an expert code reviewer. Respond only with valid JSON."
        
        try:
            result = await self._generate(prompt, system)
            return AIResponse(
                content=result,
                model=self.model,
                metadata={"provider": "local", "base_url": self.base_url}
            )
        except Exception as e:
            return AIResponse(
                content=json.dumps({"error": str(e), "issues": [], "suggestions": []}),
                model=self.model,
                metadata={"provider": "local", "error": str(e)}
            )
    
    async def suggest_fix(self, issue: Issue, context: ReviewContext) -> AIResponse:
        prompt = self._build_fix_prompt(issue, context)
        system = "You are an expert programmer. Respond only with valid JSON."
        
        try:
            result = await self._generate(prompt, system)
            return AIResponse(
                content=result,
                model=self.model,
                metadata={"provider": "local", "base_url": self.base_url}
            )
        except Exception as e:
            return AIResponse(
                content=json.dumps({"error": str(e), "fixed_code": "", "explanation": ""}),
                model=self.model,
                metadata={"provider": "local", "error": str(e)}
            )
    
    async def is_available(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return self.model in models or f"{self.model}:latest" in models
            return False
        except Exception:
            return False
    
    @property
    def provider_name(self) -> str:
        return "local"
    
    async def close(self) -> None:
        if self.client and not self.client.is_closed:
            await self.client.aclose()


ProviderRegistry.register("local", LocalLLMProvider)
ProviderRegistry.register("ollama", LocalLLMProvider)