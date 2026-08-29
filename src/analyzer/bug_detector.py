from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from analyzer.ast_parser import Issue, CodeLocation, LanguageType, PythonASTAnalyzer


@dataclass
class BugPattern:
    id: str
    name: str
    description: str
    severity: str
    category: str
    languages: List[str] = field(default_factory=list)
    confidence: float = 0.8
    metadata: Dict[str, Any] = field(default_factory=dict)


class BugDetector:
    def __init__(self):
        self.patterns: List[BugPattern] = []
        self._register_patterns()
    
    def _register_patterns(self) -> None:
        self.patterns = [
            BugPattern(
                id="null-dereference",
                name="Potential Null Dereference",
                description="Variable used without null check",
                severity="high",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.7,
            ),
            BugPattern(
                id="off-by-one",
                name="Off-by-One Error",
                description="Loop boundary condition may be incorrect",
                severity="medium",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.6,
            ),
            BugPattern(
                id="infinite-loop",
                name="Potential Infinite Loop",
                description="Loop condition may never become false",
                severity="high",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.5,
            ),
            BugPattern(
                id="resource-leak",
                name="Resource Leak",
                description="File/connection not properly closed",
                severity="medium",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.7,
            ),
            BugPattern(
                id="race-condition",
                name="Potential Race Condition",
                description="Non-atomic operation on shared resource",
                severity="high",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.5,
            ),
            BugPattern(
                id="division-by-zero",
                name="Potential Division by Zero",
                description="Division without zero check",
                severity="high",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.7,
            ),
            BugPattern(
                id="index-out-of-bounds",
                name="Potential Index Out of Bounds",
                description="Array/list access without bounds check",
                severity="medium",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.6,
            ),
            BugPattern(
                id="unhandled-exception",
                name="Unhandled Exception",
                description="Code that can raise exception without try/except",
                severity="medium",
                category="bugs",
                languages=["python"],
                confidence=0.6,
            ),
            BugPattern(
                id="async-without-await",
                name="Async Function Without Await",
                description="Async function called without await",
                severity="medium",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.7,
            ),
            BugPattern(
                id="variable-shadowing",
                name="Variable Shadowing",
                description="Inner variable shadows outer variable",
                severity="low",
                category="bugs",
                languages=["python", "javascript", "typescript"],
                confidence=0.8,
            ),
        ]
    
    def detect(self, code: str, file_path: Path, language: LanguageType) -> List[Issue]:
        issues = []
        
        if language == LanguageType.PYTHON:
            issues.extend(self._detect_python_bugs(code, file_path))
        elif language in (LanguageType.JAVASCRIPT, LanguageType.TYPESCRIPT):
            issues.extend(self._detect_js_bugs(code, file_path, language))
        
        issues.extend(self._detect_generic_bugs(code, file_path, language))
        
        return issues
    
    def _detect_python_bugs(self, code: str, file_path: Path) -> List[Issue]:
        issues = []
        lines = code.splitlines()
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues
        
        for node in ast.walk(tree):
            issues.extend(self._check_division_by_zero(node, lines, file_path))
            issues.extend(self._check_index_out_of_bounds(node, lines, file_path))
            issues.extend(self._check_resource_leak(node, lines, file_path))
            issues.extend(self._check_unhandled_exception(node, lines, file_path))
            issues.extend(self._check_async_without_await(node, lines, file_path))
            issues.extend(self._check_variable_shadowing(node, lines, file_path))
        
        return issues
    
    def _check_division_by_zero(self, node: ast.AST, lines: List[str], file_path: Path) -> List[Issue]:
        issues = []
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Name):
                issues.append(Issue(
                    id=f"div-zero-{file_path}-{node.lineno}",
                    title="Potential Division by Zero",
                    description=f"Division by variable '{node.right.id}' without zero check",
                    severity="high",
                    category="bugs",
                    location=CodeLocation(str(file_path), node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                    code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                    suggestion=f"Add check: if {node.right.id} != 0:",
                    rule_id="division-by-zero",
                    confidence=0.7,
                ))
            elif isinstance(node.right, ast.Constant) and node.right.value == 0:
                issues.append(Issue(
                    id=f"div-zero-const-{file_path}-{node.lineno}",
                    title="Division by Zero",
                    description="Division by zero constant",
                    severity="critical",
                    category="bugs",
                    location=CodeLocation(str(file_path), node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                    code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                    suggestion="Fix the division operation",
                    rule_id="division-by-zero",
                    confidence=1.0,
                ))
        return issues
    
    def _check_index_out_of_bounds(self, node: ast.AST, lines: List[str], file_path: Path) -> List[Issue]:
        issues = []
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                index = node.slice.value
                if index < 0:
                    issues.append(Issue(
                        id=f"negative-index-{file_path}-{node.lineno}",
                        title="Negative Index Access",
                        description=f"Negative index {index} used for array access",
                        severity="medium",
                        category="bugs",
                        location=CodeLocation(str(file_path), node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                        code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                        suggestion="Verify negative indexing is intentional",
                        rule_id="index-out-of-bounds",
                        confidence=0.6,
                    ))
        return issues
    
    def _check_resource_leak(self, node: ast.AST, lines: List[str], file_path: Path) -> List[Issue]:
        issues = []
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                in_with = False
                for parent in ast.walk(node):
                    if isinstance(parent, ast.With):
                        in_with = True
                        break
                if not in_with:
                    issues.append(Issue(
                        id=f"resource-leak-{file_path}-{node.lineno}",
                        title="Potential Resource Leak",
                        description="File opened without using 'with' statement",
                        severity="medium",
                        category="bugs",
                        location=CodeLocation(str(file_path), node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                        code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                        suggestion="Use 'with open(...) as f:' to ensure proper closing",
                        rule_id="resource-leak",
                        confidence=0.8,
                    ))
        return issues
    
    def _check_unhandled_exception(self, node: ast.AST, lines: List[str], file_path: Path) -> List[Issue]:
        issues = []
        if isinstance(node, ast.Call):
            risky_funcs = {"json.loads", "yaml.safe_load", "pickle.loads", "open", "requests.get", "urllib.request.urlopen"}
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            
            if func_name in ("loads", "load", "get", "urlopen", "open"):
                in_try = False
                for parent in ast.walk(node):
                    if isinstance(parent, ast.Try):
                        in_try = True
                        break
                if not in_try:
                    issues.append(Issue(
                        id=f"unhandled-exc-{file_path}-{node.lineno}",
                        title="Unhandled Exception Risk",
                        description=f"Call to '{func_name}' can raise exception",
                        severity="medium",
                        category="bugs",
                        location=CodeLocation(str(file_path), node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                        code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                        suggestion=f"Wrap in try/except block",
                        rule_id="unhandled-exception",
                        confidence=0.6,
                    ))
        return issues
    
    def _check_async_without_await(self, node: ast.AST, lines: List[str], file_path: Path) -> List[Issue]:
        issues = []
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id.startswith("async_"):
                in_await = False
                parent = getattr(node, 'parent', None)
                while parent:
                    if isinstance(parent, ast.Await):
                        in_await = True
                        break
                    parent = getattr(parent, 'parent', None)
                if not in_await:
                    issues.append(Issue(
                        id=f"async-no-await-{file_path}-{node.lineno}",
                        title="Async Call Without Await",
                        description=f"Async function '{node.func.id}' called without await",
                        severity="medium",
                        category="bugs",
                        location=CodeLocation(str(file_path), node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                        code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                        suggestion="Add 'await' before the call",
                        rule_id="async-without-await",
                        confidence=0.7,
                    ))
        return issues
    
    def _check_variable_shadowing(self, node: ast.AST, lines: List[str], file_path: Path) -> List[Issue]:
        issues = []
        if isinstance(node, ast.FunctionDef):
            outer_vars = set()
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    if n.id in outer_vars:
                        issues.append(Issue(
                            id=f"var-shadow-{file_path}-{n.lineno}",
                            title="Variable Shadowing",
                            description=f"Variable '{n.id}' shadows outer scope variable",
                            severity="low",
                            category="bugs",
                            location=CodeLocation(str(file_path), n.lineno, n.lineno, n.col_offset, n.end_col_offset or n.col_offset),
                            code_snippet=lines[n.lineno - 1] if n.lineno <= len(lines) else "",
                            suggestion="Rename the inner variable",
                            rule_id="variable-shadowing",
                            confidence=0.8,
                        ))
                    outer_vars.add(n.id)
        return issues
    
    def _detect_js_bugs(self, code: str, file_path: Path, language: LanguageType) -> List[Issue]:
        issues = []
        lines = code.splitlines()
        
        patterns = [
            (r'\.forEach\s*\(\s*async\s', "async-in-foreach", "Async callback in forEach", "medium"),
            (r'==\s*null|==\s*undefined', "loose-null-check", "Loose null/undefined check", "low"),
            (r'parseInt\s*\([^)]*\)(?!\s*,\s*10)', "parseint-radix", "parseInt without radix", "low"),
            (r'new\s+Date\s*\(\s*\)', "date-constructor", "Date constructor without arguments", "low"),
            (r'\.map\s*\([^)]*\)\s*(?!\.filter|\.reduce|\.forEach)', "map-without-use", "Map result not used", "low"),
        ]
        
        for pattern, rule_id, title, severity in patterns:
            for i, line in enumerate(lines):
                for match in re.finditer(pattern, line):
                    issues.append(Issue(
                        id=f"{rule_id}-{file_path}-{i+1}",
                        title=title,
                        description=f"Potential issue: {title.lower()}",
                        severity=severity,
                        category="bugs",
                        location=CodeLocation(str(file_path), i + 1, i + 1, match.start(), match.end()),
                        code_snippet=line.strip(),
                        rule_id=rule_id,
                        confidence=0.5,
                    ))
        
        return issues
    
    def _detect_generic_bugs(self, code: str, file_path: Path, language: LanguageType) -> List[Issue]:
        issues = []
        lines = code.splitlines()
        
        for i, line in enumerate(lines):
            if re.search(r'while\s*\(\s*true\s*\)', line) and 'break' not in code[code.find(line):code.find(line)+500]:
                issues.append(Issue(
                    id=f"infinite-loop-{file_path}-{i+1}",
                    title="Potential Infinite Loop",
                    description="While true loop without apparent break condition",
                    severity="high",
                    category="bugs",
                    location=CodeLocation(str(file_path), i + 1, i + 1, 0, len(line)),
                    code_snippet=line.strip(),
                    suggestion="Ensure loop has a break condition",
                    rule_id="infinite-loop",
                    confidence=0.5,
                ))
            
            if re.search(r'for\s*\(\s*;\s*;\s*\)', line):
                issues.append(Issue(
                    id=f"empty-for-{file_path}-{i+1}",
                    title="Empty For Loop",
                    description="For loop with no initialization, condition, or increment",
                    severity="medium",
                    category="bugs",
                    location=CodeLocation(str(file_path), i + 1, i + 1, 0, len(line)),
                    code_snippet=line.strip(),
                    suggestion="Verify loop logic is correct",
                    rule_id="empty-for-loop",
                    confidence=0.6,
                ))
        
        return issues


bug_detector = BugDetector()