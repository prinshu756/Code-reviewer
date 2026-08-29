from __future__ import annotations

import json
import random
import asyncio
from typing import Any, Dict, List, Optional

from ai.base import AIProvider, AIResponse, ReviewContext, ProviderRegistry
from analyzer import Issue, CodeLocation


class MockAPIProvider(AIProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.delay = config.get("delay", 0.1)
        self.error_rate = config.get("error_rate", 0.0)
        self.model = config.get("model", "mock-model")
    
    async def _simulate_delay(self) -> None:
        await asyncio.sleep(self.delay)
    
    def _should_error(self) -> bool:
        return random.random() < self.error_rate
    
    def _analyze_code_patterns(self, code: str, language: str) -> List[Dict[str, Any]]:
        issues = []
        lines = code.splitlines()
        
        patterns = [
            (r'eval\s*\(', "Use of eval()", "critical", "security", 0.95),
            (r'exec\s*\(', "Use of exec()", "critical", "security", 0.95),
            (r'pickle\.loads', "Unsafe pickle.loads", "high", "security", 0.9),
            (r'password\s*=', "Possible hardcoded password", "high", "security", 0.7),
            (r'api[_-]?key\s*=', "Possible hardcoded API key", "high", "security", 0.7),
            (r'secret\s*=', "Possible hardcoded secret", "high", "security", 0.7),
            (r'TODO|FIXME|HACK', "TODO/FIXME comment", "low", "best_practices", 0.95),
            (r'console\.log|print\(', "Debug statement", "low", "style", 0.9),
            (r'except\s*:', "Bare except clause", "medium", "bugs", 0.85),
            (r'=\s*\[\s*\]', "Mutable default argument (list)", "high", "bugs", 0.8),
            (r'=\s*\{\s*\}', "Mutable default argument (dict)", "high", "bugs", 0.8),
            (r'while\s+True:', "Potential infinite loop", "medium", "bugs", 0.5),
            (r'/.*\.js', "Possible XSS", "medium", "security", 0.4),
            (r'innerHTML\s*=', "Direct innerHTML assignment", "high", "security", 0.8),
        ]
        
        for i, line in enumerate(lines):
            for pattern, title, severity, category, confidence in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "title": title,
                        "description": f"Found pattern matching: {pattern}",
                        "severity": severity,
                        "category": category,
                        "line_start": i + 1,
                        "line_end": i + 1,
                        "suggestion": f"Review and fix: {title}",
                        "confidence": confidence,
                    })
        
        if language == "python":
            try:
                import ast
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                            issues.append({
                                "title": "Empty Function",
                                "description": f"Function '{node.name}' is empty",
                                "severity": "low",
                                "category": "style",
                                "line_start": node.lineno,
                                "line_end": node.end_lineno or node.lineno,
                                "suggestion": "Remove or implement the function",
                                "confidence": 0.9,
                            })
            except SyntaxError:
                pass
        
        return issues[:15]
    
    def _generate_fix(self, issue: Issue, code: str, language: str) -> Dict[str, Any]:
        fixes = {
            "Use of eval()": ("# eval() removed - use safe alternative\nresult = safe_eval(user_input)", "Replaced eval() with safe alternative"),
            "Use of exec()": ("# exec() removed - use safe alternative\nresult = safe_exec(user_input)", "Replaced exec() with safe alternative"),
            "Unsafe pickle.loads": ("import json\n# Use json instead\ndata = json.loads(user_input)", "Replaced pickle with json"),
            "Possible hardcoded password": ("import os\npassword = os.environ.get('PASSWORD')", "Moved password to environment variable"),
            "Possible hardcoded API key": ("import os\napi_key = os.environ.get('API_KEY')", "Moved API key to environment variable"),
            "Possible hardcoded secret": ("import os\nsecret = os.environ.get('SECRET')", "Moved secret to environment variable"),
            "Bare except clause": ("try:\n    risky_operation()\nexcept SpecificException as e:\n    handle_error(e)", "Added specific exception handling"),
            "Mutable default argument (list)": ("def func(param=None):\n    if param is None:\n        param = []", "Changed mutable default to None"),
            "Mutable default argument (dict)": ("def func(param=None):\n    if param is None:\n        param = {}\n", "Changed mutable default to None"),
            "Empty Function": (f"def {issue.title.lower().replace(' ', '_')}():\n    # TODO: Implement\n    pass", "Added placeholder implementation"),
        }
        
        fixed_code, explanation = fixes.get(issue.title, (code, "No automatic fix available"))
        
        return {
            "fixed_code": fixed_code,
            "explanation": explanation,
            "confidence": 0.7,
        }
    
    async def review_code(self, context: ReviewContext) -> AIResponse:
        await self._simulate_delay()
        
        if self._should_error():
            return AIResponse(
                content=json.dumps({"error": "Mock API simulated error", "issues": [], "suggestions": []}),
                model=self.model,
                metadata={"provider": "mock", "error": "simulated"}
            )
        
        issues = self._analyze_code_patterns(context.code, context.language)
        
        summary = f"Mock review of {context.file_path}: Found {len(issues)} issues"
        
        suggestions = [
            "Consider adding type hints",
            "Add unit tests for critical functions",
            "Review error handling",
            "Consider using a linter",
        ]
        
        return AIResponse(
            content=json.dumps({
                "summary": summary,
                "issues": issues,
                "suggestions": suggestions,
            }),
            model=self.model,
            metadata={"provider": "mock"}
        )
    
    async def suggest_fix(self, issue: Issue, context: ReviewContext) -> AIResponse:
        await self._simulate_delay()
        
        if self._should_error():
            return AIResponse(
                content=json.dumps({"error": "Mock API simulated error", "fixed_code": "", "explanation": ""}),
                model=self.model,
                metadata={"provider": "mock", "error": "simulated"}
            )
        
        fix = self._generate_fix(issue, context.code, context.language)
        
        return AIResponse(
            content=json.dumps(fix),
            model=self.model,
            metadata={"provider": "mock"}
        )
    
    async def is_available(self) -> bool:
        return True
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    async def close(self) -> None:
        pass


import re
ProviderRegistry.register("mock", MockAPIProvider)