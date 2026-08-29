import os
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocalLLMConfig(BaseModel):
    enabled: bool = True
    model: str = "codellama:7b"
    base_url: str = "http://localhost:11434"
    timeout: int = 120
    temperature: float = 0.1
    max_tokens: int = 4096


class CloudAPIConfig(BaseModel):
    enabled: bool = True
    provider: str = "openai"
    api_key: str = ""
    model: str = "gpt-4"
    timeout: int = 60
    temperature: float = 0.1
    max_tokens: int = 4096
    anthropic_model: str = "claude-3-opus-20240229"
    gemini_model: str = "gemini-pro"


class AIConfig(BaseModel):
    provider: str = "auto"
    local: LocalLLMConfig = Field(default_factory=LocalLLMConfig)
    cloud: CloudAPIConfig = Field(default_factory=CloudAPIConfig)


class ComplexityConfig(BaseModel):
    max_cyclomatic: int = 10
    max_cognitive: int = 15
    max_nesting: int = 4
    max_function_length: int = 50
    max_class_length: int = 200


class RulesConfig(BaseModel):
    security: bool = True
    complexity: bool = True
    style: bool = True
    bugs: bool = True
    performance: bool = True
    best_practices: bool = True


class AnalysisConfig(BaseModel):
    languages: list[str] = Field(default_factory=lambda: ["python", "javascript", "typescript"])
    severity_threshold: str = "medium"
    rules: RulesConfig = Field(default_factory=RulesConfig)
    complexity: ComplexityConfig = Field(default_factory=ComplexityConfig)
    include_patterns: list[str] = Field(default_factory=lambda: [
        "**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx"
    ])
    exclude_patterns: list[str] = Field(default_factory=lambda: [
        "**/__pycache__/**", "**/node_modules/**", "**/.git/**",
        "**/venv/**", "**/dist/**", "**/build/**",
        "**/*.min.js", "**/*.min.css"
    ])


class OutputConfig(BaseModel):
    format: str = "markdown"
    path: str = "./reviews"
    include_suggestions: bool = True
    include_code_snippets: bool = True
    include_line_numbers: bool = True
    group_by: str = "file"


class FixerConfig(BaseModel):
    auto_apply: bool = False
    safe_only: bool = True
    confidence_threshold: float = 0.85
    create_backup: bool = True
    auto_fix_categories: list[str] = Field(default_factory=lambda: [
        "style", "simple_bug", "unused_import"
    ])


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "./logs/code-reviewer.log"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config(BaseModel):
    ai: AIConfig = Field(default_factory=AIConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    fixer: FixerConfig = Field(default_factory=FixerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    log_level: str = "INFO"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def load_config(config_path: Optional[str] = None) -> Config:
    config = Config()
    
    if config_path:
        path = Path(config_path)
    else:
        path = Path("config.yaml")
        if not path.exists():
            path = Path("config/default.yaml")
    
    if path.exists():
        with open(path, "r") as f:
            data = yaml.safe_load(f)
            if data:
                config = Config(**data)
    
    settings = get_settings()
    if settings.openai_api_key:
        config.ai.cloud.api_key = settings.openai_api_key
    if settings.anthropic_api_key:
        config.ai.cloud.api_key = settings.anthropic_api_key
    if settings.gemini_api_key:
        config.ai.cloud.api_key = settings.gemini_api_key
    if settings.ollama_base_url:
        config.ai.local.base_url = settings.ollama_base_url
    if settings.log_level:
        config.logging.level = settings.log_level
    
    return config


def save_config(config: Config, config_path: str = "config.yaml") -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()