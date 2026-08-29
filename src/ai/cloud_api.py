from __future__ import annotations

import json
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ai.base import AIProvider, AIResponse, ReviewContext, ProviderRegistry
from analyzer import Issue


class CloudAPIProvider(AIProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.provider = config.get("provider", "openai")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "gpt-4")
        self.timeout = config.get("timeout", 60)
        self.temperature = config.get("temperature", 0.1)
        self.max_tokens = config.get("max_tokens", 4096)
        self.client: Optional[httpx.AsyncClient] = None
        
        self.anthropic_model = config.get("anthropic_model", "claude-3-opus-20240229")
        self.gemini_model = config.get("gemini_model", "gemini-pro")
        
        self._setup_client()
    
    def _setup_client(self) -> None:
        headers = {"Content-Type": "application/json"}
        
        if self.provider == "openai":
            headers["Authorization"] = f"Bearer {self.api_key}"
            base_url = "https://api.openai.com/v1"
        elif self.provider == "anthropic":
            headers["x-api-key"] = self.api_key
            headers["anthropic-version"] = "2023-06-01"
            base_url = "https://api.anthropic.com/v1"
        elif self.provider == "gemini":
            base_url = "https://generativelanguage.googleapis.com/v1beta"
        else:
            raise ValueError(f"Unsupported cloud provider: {self.provider}")
        
        self.base_url = base_url
        self.headers = headers
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self.client
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_openai(self, prompt: str, system: str = "") -> str:
        client = await self._get_client()
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"}
        }
        
        response = await client.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_anthropic(self, prompt: str, system: str = "") -> str:
        client = await self._get_client()
        
        payload = {
            "model": self.anthropic_model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        
        response = await client.post(f"{self.base_url}/messages", json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data["content"][0]["text"]
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _generate_gemini(self, prompt: str, system: str = "") -> str:
        client = await self._get_client()
        
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            }
        }
        
        url = f"{self.base_url}/models/{self.gemini_model}:generateContent?key={self.api_key}"
        response = await client.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    
    async def _generate(self, prompt: str, system: str = "") -> str:
        if self.provider == "openai":
            return await self._generate_openai(prompt, system)
        elif self.provider == "anthropic":
            return await self._generate_anthropic(prompt, system)
        elif self.provider == "gemini":
            return await self._generate_gemini(prompt, system)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def review_code(self, context: ReviewContext) -> AIResponse:
        prompt = self._build_review_prompt(context)
        system = "You are an expert code reviewer. Respond only with valid JSON."
        
        try:
            result = await self._generate(prompt, system)
            return AIResponse(
                content=result,
                model=self.model if self.provider == "openai" else (self.anthropic_model if self.provider == "anthropic" else self.gemini_model),
                metadata={"provider": f"cloud-{self.provider}"}
            )
        except Exception as e:
            return AIResponse(
                content=json.dumps({"error": str(e), "issues": [], "suggestions": []}),
                model=self.model,
                metadata={"provider": f"cloud-{self.provider}", "error": str(e)}
            )
    
    async def suggest_fix(self, issue: Issue, context: ReviewContext) -> AIResponse:
        prompt = self._build_fix_prompt(issue, context)
        system = "You are an expert programmer. Respond only with valid JSON."
        
        try:
            result = await self._generate(prompt, system)
            return AIResponse(
                content=result,
                model=self.model if self.provider == "openai" else (self.anthropic_model if self.provider == "anthropic" else self.gemini_model),
                metadata={"provider": f"cloud-{self.provider}"}
            )
        except Exception as e:
            return AIResponse(
                content=json.dumps({"error": str(e), "fixed_code": "", "explanation": ""}),
                model=self.model,
                metadata={"provider": f"cloud-{self.provider}", "error": str(e)}
            )
    
    async def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            if self.provider == "openai":
                client = await self._get_client()
                response = await client.get(f"{self.base_url}/models")
                return response.status_code == 200
            elif self.provider == "anthropic":
                return bool(self.api_key)
            elif self.provider == "gemini":
                return bool(self.api_key)
        except Exception:
            return False
        return False
    
    @property
    def provider_name(self) -> str:
        return f"cloud-{self.provider}"
    
    async def close(self) -> None:
        if self.client and not self.client.is_closed:
            await self.client.aclose()


ProviderRegistry.register("cloud", CloudAPIProvider)
ProviderRegistry.register("openai", CloudAPIProvider)
ProviderRegistry.register("anthropic", CloudAPIProvider)
ProviderRegistry.register("gemini", CloudAPIProvider)