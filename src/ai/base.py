from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from analyzer import Issue, CodeLocation


@dataclass
class AIResponse:
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewContext:
    file_path: str
    code: str
    language: str
    issues: List[Issue] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = config.get("model", "unknown")
    
    @abstractmethod
    async def review_code(self, context: ReviewContext) -> AIResponse:
        pass
    
    @abstractmethod
    async def suggest_fix(self, issue: Issue, context: ReviewContext) -> AIResponse:
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass
    
    def _build_review_prompt(self, context: ReviewContext) -> str:
        issues_summary = ""
        if context.issues:
            issues_summary = "\n\nExisting Issues Found:\n"
            for issue in context.issues[:10]:
                issues_summary += f"- [{issue.severity.upper()}] {issue.title}: {issue.description} (Line {issue.location.line_start})\n"
        
        return f"""You are an expert code reviewer. Analyze the following {context.language} code for:
1. Security vulnerabilities
2. Bugs and logic errors
3. Performance issues
4. Code style and best practices
5. Maintainability concerns

File: {context.file_path}
Language: {context.language}
{issues_summary}

Code:
```{context.language}
{context.code}
```

Provide a detailed review in JSON format with the following structure:
{{
  "summary": "Brief overall assessment",
  "issues": [
    {{
      "title": "Issue title",
      "description": "Detailed description",
      "severity": "low|medium|high|critical",
      "category": "security|bugs|performance|style|complexity|best_practices",
      "line_start": 10,
      "line_end": 15,
      "suggestion": "How to fix",
      "confidence": 0.9
    }}
  ],
  "suggestions": [
    "General improvement suggestions"
  ]
}}"""
    
    def _build_fix_prompt(self, issue: Issue, context: ReviewContext) -> str:
        return f"""You are an expert programmer. Fix the following issue in the code.

File: {context.file_path}
Language: {context.language}

Issue: {issue.title}
Description: {issue.description}
Severity: {issue.severity}
Location: Lines {issue.location.line_start}-{issue.location.line_end}

Code Context:
```{context.language}
{context.code}
```

Provide the fixed code in JSON format:
{{
  "fixed_code": "The complete fixed code",
  "explanation": "What was changed and why",
  "confidence": 0.9
}}"""


class ProviderRegistry:
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, provider_class: type) -> None:
        cls._providers[name] = provider_class
    
    @classmethod
    def get(cls, name: str, config: Dict[str, Any]) -> AIProvider:
        if name not in cls._providers:
            raise ValueError(f"Unknown provider: {name}")
        return cls._providers[name](config)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        return list(cls._providers.keys())