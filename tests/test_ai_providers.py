import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai import (
    MockAPIProvider,
    LocalLLMProvider,
    CloudAPIProvider,
    ProviderRegistry,
    AIResponse,
    ReviewContext,
)
from analyzer import Issue, CodeLocation, LanguageType


class TestMockAPIProvider:
    @pytest.fixture
    def mock_provider(self):
        return MockAPIProvider({"delay": 0.01, "error_rate": 0.0})
    
    @pytest.fixture
    def context(self):
        return ReviewContext(
            file_path="test.py",
            code='password = "secret123"\neval("bad")',
            language="python",
            issues=[],
            config={},
        )
    
    @pytest.mark.asyncio
    async def test_review_code(self, mock_provider, context):
        response = await mock_provider.review_code(context)
        assert isinstance(response, AIResponse)
        assert response.model == "mock-model"
        
        data = eval(response.content) if isinstance(response.content, str) else response.content
        assert "issues" in data
        assert "summary" in data
        assert "suggestions" in data
    
    @pytest.mark.asyncio
    async def test_suggest_fix(self, mock_provider, context):
        issue = Issue(
            id="test-1",
            title="Hardcoded Secret",
            description="Secret found",
            severity="high",
            category="security",
            location=CodeLocation("test.py", 1, 1, 0, 20),
            rule_id="hardcoded-secret",
        )
        
        response = await mock_provider.suggest_fix(issue, context)
        assert isinstance(response, AIResponse)
        
        data = eval(response.content) if isinstance(response.content, str) else response.content
        assert "fixed_code" in data
        assert "explanation" in data
    
    @pytest.mark.asyncio
    async def test_is_available(self, mock_provider):
        assert await mock_provider.is_available() is True
    
    def test_provider_name(self, mock_provider):
        assert mock_provider.provider_name == "mock"


class TestLocalLLMProvider:
    @pytest.fixture
    def local_provider(self):
        return LocalLLMProvider({
            "base_url": "http://localhost:11434",
            "model": "codellama:7b",
            "timeout": 5,
        })
    
    def test_provider_name(self, local_provider):
        assert local_provider.provider_name == "local"
    
    def test_config(self, local_provider):
        assert local_provider.base_url == "http://localhost:11434"
        assert local_provider.model == "codellama:7b"


class TestCloudAPIProvider:
    @pytest.fixture
    def openai_provider(self):
        return CloudAPIProvider({
            "provider": "openai",
            "api_key": "test-key",
            "model": "gpt-4",
        })
    
    def test_provider_name(self, openai_provider):
        assert openai_provider.provider_name == "cloud-openai"
    
    def test_unsupported_provider(self):
        with pytest.raises(ValueError):
            CloudAPIProvider({"provider": "unsupported", "api_key": "test"})


class TestProviderRegistry:
    def test_register_and_get(self):
        class TestProvider:
            provider_name = "test"
            
            def __init__(self, config):
                pass
            
            async def review_code(self, context):
                pass
            
            async def suggest_fix(self, issue, context):
                pass
            
            async def is_available(self):
                return True
        
        ProviderRegistry.register("test", TestProvider)
        provider = ProviderRegistry.get("test", {})
        assert isinstance(provider, TestProvider)
    
    def test_list_providers(self):
        providers = ProviderRegistry.list_providers()
        assert "mock" in providers
        assert "local" in providers
        assert "openai" in providers
    
    def test_unknown_provider(self):
        with pytest.raises(ValueError):
            ProviderRegistry.get("unknown", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])