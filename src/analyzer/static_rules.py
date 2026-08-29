from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern

from analyzer.ast_parser import Issue, CodeLocation


@dataclass
class Rule:
    id: str
    name: str
    description: str
    severity: str
    category: str
    pattern: Optional[Pattern] = None
    languages: List[str] = field(default_factory=list)
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, code: str, file_path: Path) -> List[Issue]:
        if not self.enabled or not self.pattern:
            return []
        
        issues = []
        lines = code.splitlines()
        for i, line in enumerate(lines):
            for match in self.pattern.finditer(line):
                issues.append(Issue(
                    id=f"{self.id}-{file_path}-{i+1}-{match.start()}",
                    title=self.name,
                    description=self.description,
                    severity=self.severity,
                    category=self.category,
                    location=CodeLocation(
                        str(file_path), i + 1, i + 1,
                        match.start(), match.end()
                    ),
                    code_snippet=line.strip(),
                    rule_id=self.id,
                    confidence=self.metadata.get("confidence", 0.7),
                ))
        return issues


class StaticRulesEngine:
    def __init__(self):
        self.rules: List[Rule] = []
        self._register_default_rules()
    
    def _register_default_rules(self) -> None:
        self.rules = [
            Rule(
                id="hardcoded-password",
                name="Hardcoded Password",
                description="Possible hardcoded password or secret",
                severity="high",
                category="security",
                pattern=re.compile(r'(password|pwd|secret|api_key|apikey|token)\s*[=:]\s*["\'][^"\']+["\']', re.IGNORECASE),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.7},
            ),
            Rule(
                id="sql-injection",
                name="Potential SQL Injection",
                description="String formatting in SQL query",
                severity="critical",
                category="security",
                pattern=re.compile(r'(execute|query)\s*\(\s*["\'].*%.*["\']', re.IGNORECASE),
                languages=["python"],
                metadata={"confidence": 0.8},
            ),
            Rule(
                id="command-injection",
                name="Potential Command Injection",
                description="User input in shell command",
                severity="critical",
                category="security",
                pattern=re.compile(r'(subprocess|os\.system|shell=True|exec\(|spawn\()', re.IGNORECASE),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.6},
            ),
            Rule(
                id="path-traversal",
                name="Potential Path Traversal",
                description="User input in file path without validation",
                severity="high",
                category="security",
                pattern=re.compile(r'(open|read|write|path\.join)\s*\([^)]*\.\.[\\/]', re.IGNORECASE),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.6},
            ),
            Rule(
                id="xss-vulnerability",
                name="Potential XSS",
                description="Direct user input in HTML output",
                severity="high",
                category="security",
                pattern=re.compile(r'(innerHTML|outerHTML|document\.write|dangerouslySetInnerHTML)\s*=', re.IGNORECASE),
                languages=["javascript", "typescript"],
                metadata={"confidence": 0.7},
            ),
            Rule(
                id="debug-code",
                name="Debug Code Left",
                description="Debug statements in production code",
                severity="low",
                category="style",
                pattern=re.compile(r'(console\.log|print\(|debugger|pdb\.set_trace|breakpoint\(\))', re.IGNORECASE),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.9},
            ),
            Rule(
                id="todo-comment",
                name="TODO Comment",
                description="TODO/FIXME comment found",
                severity="low",
                category="best_practices",
                pattern=re.compile(r'(TODO|FIXME|HACK|XXX|BUG):', re.IGNORECASE),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.95},
            ),
            Rule(
                id="long-line",
                name="Line Too Long",
                description="Line exceeds recommended length",
                severity="low",
                category="style",
                pattern=re.compile(r'^.{120,}$'),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.9},
            ),
            Rule(
                id="bare-except",
                name="Bare Except Clause",
                description="Bare except catches all exceptions",
                severity="medium",
                category="bugs",
                pattern=re.compile(r'except\s*:', re.IGNORECASE),
                languages=["python"],
                metadata={"confidence": 0.85},
            ),
            Rule(
                id="mutable-default",
                name="Mutable Default Argument",
                description="Mutable default argument in function definition",
                severity="high",
                category="bugs",
                pattern=re.compile(r'def\s+\w+\s*\([^)]*=\s*(\[|\{|\()', re.IGNORECASE),
                languages=["python"],
                metadata={"confidence": 0.9},
            ),
            Rule(
                id="unused-variable",
                name="Unused Variable",
                description="Variable assigned but never used",
                severity="low",
                category="style",
                pattern=re.compile(r'^\s*(\w+)\s*=\s*.+?(?:\n|$)', re.MULTILINE),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.4},
            ),
            Rule(
                id="global-variable",
                name="Global Variable",
                description="Global variable declaration",
                severity="low",
                category="best_practices",
                pattern=re.compile(r'^(?:var|let|const)\s+\w+\s*=', re.MULTILINE),
                languages=["javascript", "typescript"],
                metadata={"confidence": 0.5},
            ),
            Rule(
                id="eval-usage",
                name="Eval Usage",
                description="Use of eval() function",
                severity="critical",
                category="security",
                pattern=re.compile(r'\beval\s*\('),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.95},
            ),
            Rule(
                id="insecure-random",
                name="Insecure Random",
                description="Use of non-cryptographic random for security",
                severity="medium",
                category="security",
                pattern=re.compile(r'(random\.random|Math\.random|rand\(\))'),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.6},
            ),
            Rule(
                id="weak-crypto",
                name="Weak Cryptography",
                description="Use of weak cryptographic algorithms",
                severity="high",
                category="security",
                pattern=re.compile(r'(md5|sha1|des|rc4|ecb)', re.IGNORECASE),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.8},
            ),
            Rule(
                id="hardcoded-ip",
                name="Hardcoded IP Address",
                description="Hardcoded IP address in code",
                severity="low",
                category="best_practices",
                pattern=re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
                languages=["python", "javascript", "typescript"],
                metadata={"confidence": 0.5},
            ),
        ]
    
    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)
    
    def get_rules(self, language: Optional[str] = None, category: Optional[str] = None, enabled_only: bool = True) -> List[Rule]:
        rules = self.rules
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        if language:
            rules = [r for r in rules if language in r.languages]
        if category:
            rules = [r for r in rules if r.category == category]
        return rules
    
    def analyze(self, code: str, file_path: Path, language: str) -> List[Issue]:
        all_issues = []
        for rule in self.get_rules(language=language):
            all_issues.extend(rule.matches(code, file_path))
        return all_issues


static_rules_engine = StaticRulesEngine()