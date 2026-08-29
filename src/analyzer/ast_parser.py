from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from tree_sitter import Language, Parser, Node


class LanguageType(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


@dataclass
class CodeLocation:
    file_path: str
    line_start: int
    line_end: int
    column_start: int
    column_end: int
    
    def __str__(self) -> str:
        return f"{self.file_path}:{self.line_start}:{self.column_start}"


@dataclass
class Issue:
    id: str
    title: str
    description: str
    severity: str
    category: str
    location: CodeLocation
    code_snippet: str = ""
    suggestion: str = ""
    confidence: float = 1.0
    rule_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "location": str(self.location),
            "code_snippet": self.code_snippet,
            "suggestion": self.suggestion,
            "confidence": self.confidence,
            "rule_id": self.rule_id,
            "metadata": self.metadata,
        }


class BaseAnalyzer:
    def __init__(self, language: LanguageType):
        self.language = language
        self.parser = self._create_parser()
    
    def _create_parser(self) -> Parser:
        parser = Parser()
        if self.language == LanguageType.PYTHON:
            # Python uses built-in ast module, tree-sitter is optional
            try:
                import tree_sitter_python as tspython
                PY_LANGUAGE = Language(tspython.language())
                parser.language = PY_LANGUAGE
            except ImportError:
                pass
        elif self.language in (LanguageType.JAVASCRIPT, LanguageType.TYPESCRIPT):
            try:
                if self.language == LanguageType.JAVASCRIPT:
                    import tree_sitter_javascript as tsjs
                    JS_LANGUAGE = Language(tsjs.language())
                else:
                    import tree_sitter_typescript as tsts
                    TS_LANGUAGE = Language(tsts.language_typescript())
                parser.language = JS_LANGUAGE if self.language == LanguageType.JAVASCRIPT else TS_LANGUAGE
            except ImportError:
                pass
        return parser
    
    def parse(self, code: str) -> Node:
        return self.parser.parse(bytes(code, "utf8")).root_node
    
    def analyze(self, code: str, file_path: str) -> List[Issue]:
        raise NotImplementedError


class PythonASTAnalyzer(BaseAnalyzer):
    def __init__(self):
        super().__init__(LanguageType.PYTHON)
    
    def analyze(self, code: str, file_path: str) -> List[Issue]:
        issues = []
        try:
            tree = ast.parse(code)
            issues.extend(self._check_ast(tree, code, file_path))
        except SyntaxError as e:
            issues.append(Issue(
                id=f"syntax-error-{file_path}-{e.lineno}",
                title="Syntax Error",
                description=str(e),
                severity="critical",
                category="syntax",
                location=CodeLocation(file_path, e.lineno or 1, e.lineno or 1, e.offset or 0, e.offset or 0),
                code_snippet=code.splitlines()[e.lineno - 1] if e.lineno and e.lineno <= len(code.splitlines()) else "",
                rule_id="syntax-error",
            ))
        return issues
    
    def _check_ast(self, tree: ast.AST, code: str, file_path: str) -> List[Issue]:
        issues = []
        lines = code.splitlines()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                issues.extend(self._check_function(node, lines, file_path))
            elif isinstance(node, ast.ClassDef):
                issues.extend(self._check_class(node, lines, file_path))
            elif isinstance(node, ast.Call):
                issues.extend(self._check_call(node, lines, file_path))
            elif isinstance(node, ast.Import):
                issues.extend(self._check_import(node, lines, file_path))
            elif isinstance(node, ast.ImportFrom):
                issues.extend(self._check_import_from(node, lines, file_path))
        
        return issues
    
    def _check_function(self, node: ast.FunctionDef, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            issues.append(Issue(
                id=f"empty-function-{file_path}-{node.lineno}",
                title="Empty Function",
                description=f"Function '{node.name}' is empty (only contains pass)",
                severity="low",
                category="style",
                location=CodeLocation(file_path, node.lineno, node.end_lineno or node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                suggestion=f"Remove the function or implement its logic",
                rule_id="empty-function",
            ))
        
        if node.args.defaults:
            for i, default in enumerate(node.args.defaults):
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append(Issue(
                        id=f"mutable-default-{file_path}-{node.lineno}-{i}",
                        title="Mutable Default Argument",
                        description=f"Function '{node.name}' uses a mutable default argument",
                        severity="high",
                        category="bugs",
                        location=CodeLocation(file_path, node.lineno, node.end_lineno or node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                        code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                        suggestion="Use None as default and create mutable object inside function",
                        rule_id="mutable-default-argument",
                        confidence=0.95,
                    ))
        
        complexity = self._calculate_cyclomatic_complexity(node)
        if complexity > 10:
            issues.append(Issue(
                id=f"high-complexity-{file_path}-{node.lineno}",
                title="High Cyclomatic Complexity",
                description=f"Function '{node.name}' has cyclomatic complexity of {complexity}",
                severity="medium",
                category="complexity",
                location=CodeLocation(file_path, node.lineno, node.end_lineno or node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                suggestion="Consider breaking this function into smaller functions",
                rule_id="high-cyclomatic-complexity",
                metadata={"complexity": complexity},
            ))
        
        return issues
    
    def _check_class(self, node: ast.ClassDef, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        
        method_count = sum(1 for n in node.body if isinstance(n, ast.FunctionDef))
        if method_count > 20:
            issues.append(Issue(
                id=f"large-class-{file_path}-{node.lineno}",
                title="Large Class",
                description=f"Class '{node.name}' has {method_count} methods",
                severity="medium",
                category="complexity",
                location=CodeLocation(file_path, node.lineno, node.end_lineno or node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                suggestion="Consider splitting this class into smaller classes",
                rule_id="large-class",
                metadata={"method_count": method_count},
            ))
        
        return issues
    
    def _check_call(self, node: ast.Call, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ("eval", "exec"):
                issues.append(Issue(
                    id=f"dangerous-call-{file_path}-{node.lineno}",
                    title="Dangerous Function Call",
                    description=f"Use of '{func_name}' can execute arbitrary code",
                    severity="critical",
                    category="security",
                    location=CodeLocation(file_path, node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                    code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                    suggestion=f"Avoid using {func_name}; use safer alternatives",
                    rule_id="dangerous-eval-exec",
                    confidence=0.95,
                ))
            elif func_name == "pickle.loads":
                issues.append(Issue(
                    id=f"pickle-loads-{file_path}-{node.lineno}",
                    title="Unsafe Pickle Loads",
                    description="pickle.loads can execute arbitrary code during deserialization",
                    severity="high",
                    category="security",
                    location=CodeLocation(file_path, node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                    code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                    suggestion="Use json.loads or other safe serialization formats",
                    rule_id="unsafe-pickle-loads",
                    confidence=0.9,
                ))
        
        return issues
    
    def _check_import(self, node: ast.Import, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        for alias in node.names:
            if alias.name in ("os", "sys", "subprocess", "pickle", "marshal"):
                issues.append(Issue(
                    id=f"risky-import-{file_path}-{node.lineno}-{alias.name}",
                    title="Potentially Risky Import",
                    description=f"Importing '{alias.name}' can be risky if not used carefully",
                    severity="low",
                    category="security",
                    location=CodeLocation(file_path, node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                    code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                    suggestion=f"Ensure {alias.name} is used securely",
                    rule_id="risky-import",
                    confidence=0.3,
                ))
        return issues
    
    def _check_import_from(self, node: ast.ImportFrom, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        if node.module == "pickle" and any(alias.name == "loads" for alias in node.names):
            issues.append(Issue(
                id=f"pickle-import-{file_path}-{node.lineno}",
                title="Unsafe Pickle Import",
                description="Importing pickle.loads can lead to arbitrary code execution",
                severity="high",
                category="security",
                location=CodeLocation(file_path, node.lineno, node.lineno, node.col_offset, node.end_col_offset or node.col_offset),
                code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else "",
                suggestion="Use json or other safe serialization",
                rule_id="unsafe-pickle-import",
                confidence=0.9,
            ))
        return issues
    
    def _calculate_cyclomatic_complexity(self, node: ast.FunctionDef) -> int:
        complexity = 1
        for n in ast.walk(node):
            if isinstance(n, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.Assert)):
                complexity += 1
            elif isinstance(n, ast.BoolOp):
                complexity += len(n.values) - 1
        return complexity


class JavaScriptAnalyzer(BaseAnalyzer):
    def __init__(self):
        super().__init__(LanguageType.JAVASCRIPT)
    
    def analyze(self, code: str, file_path: str) -> List[Issue]:
        issues = []
        tree = self.parse(code)
        issues.extend(self._traverse(tree, code, file_path))
        return issues
    
    def _traverse(self, node: Node, code: str, file_path: str) -> List[Issue]:
        issues = []
        lines = code.splitlines()
        
        if node.type == "function_declaration" or node.type == "function_expression":
            issues.extend(self._check_function(node, lines, file_path))
        elif node.type == "call_expression":
            issues.extend(self._check_call(node, lines, file_path))
        elif node.type == "variable_declarator":
            issues.extend(self._check_variable(node, lines, file_path))
        
        for child in node.children:
            issues.extend(self._traverse(child, code, file_path))
        
        return issues
    
    def _check_function(self, node: Node, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        name_node = node.child_by_field_name("name")
        func_name = name_node.text.decode() if name_node else "anonymous"
        
        params = node.child_by_field_name("parameters")
        if params:
            param_count = len([c for c in params.children if c.type == "identifier"])
            if param_count > 5:
                issues.append(Issue(
                    id=f"too-many-params-{file_path}-{node.start_point[0]}",
                    title="Too Many Parameters",
                    description=f"Function '{func_name}' has {param_count} parameters",
                    severity="medium",
                    category="complexity",
                    location=CodeLocation(file_path, node.start_point[0] + 1, node.end_point[0] + 1, node.start_point[1], node.end_point[1]),
                    code_snippet=lines[node.start_point[0]] if node.start_point[0] < len(lines) else "",
                    suggestion="Consider using an options object or splitting the function",
                    rule_id="too-many-parameters",
                    metadata={"param_count": param_count},
                ))
        
        return issues
    
    def _check_call(self, node: Node, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        func = node.child_by_field_name("function")
        if func and func.type == "identifier":
            func_name = func.text.decode()
            if func_name in ("eval", "Function", "setTimeout", "setInterval"):
                if func_name == "eval":
                    severity = "critical"
                else:
                    severity = "high"
                issues.append(Issue(
                    id=f"dangerous-js-call-{file_path}-{node.start_point[0]}",
                    title=f"Dangerous JavaScript Call: {func_name}",
                    description=f"Use of '{func_name}' can execute arbitrary code",
                    severity=severity,
                    category="security",
                    location=CodeLocation(file_path, node.start_point[0] + 1, node.end_point[0] + 1, node.start_point[1], node.end_point[1]),
                    code_snippet=lines[node.start_point[0]] if node.start_point[0] < len(lines) else "",
                    suggestion=f"Avoid using {func_name}; use safer alternatives",
                    rule_id=f"dangerous-{func_name.lower()}",
                    confidence=0.9,
                ))
        return issues
    
    def _check_variable(self, node: Node, lines: List[str], file_path: str) -> List[Issue]:
        issues = []
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        
        if name_node and value_node:
            var_name = name_node.text.decode()
            if var_name.upper() == var_name and var_name.isupper() and value_node.type in ("string", "template_string"):
                issues.append(Issue(
                    id=f"hardcoded-secret-{file_path}-{node.start_point[0]}",
                    title="Potential Hardcoded Secret",
                    description=f"Constant '{var_name}' may contain a hardcoded secret",
                    severity="high",
                    category="security",
                    location=CodeLocation(file_path, node.start_point[0] + 1, node.end_point[0] + 1, node.start_point[1], node.end_point[1]),
                    code_snippet=lines[node.start_point[0]] if node.start_point[0] < len(lines) else "",
                    suggestion="Use environment variables for secrets",
                    rule_id="hardcoded-secret",
                    confidence=0.6,
                ))
        return issues


class TypeScriptAnalyzer(JavaScriptAnalyzer):
    def __init__(self):
        super().__init__()
        self.language = LanguageType.TYPESCRIPT
        try:
            import tree_sitter_typescript as tsts
            TS_LANGUAGE = Language(tsts.language_typescript())
            self.parser.language = TS_LANGUAGE
        except ImportError:
            pass


def get_analyzer(language: LanguageType) -> BaseAnalyzer:
    if language == LanguageType.PYTHON:
        return PythonASTAnalyzer()
    elif language == LanguageType.JAVASCRIPT:
        return JavaScriptAnalyzer()
    elif language == LanguageType.TYPESCRIPT:
        return TypeScriptAnalyzer()
    raise ValueError(f"Unsupported language: {language}")


def analyze_file(file_path: Path, language: LanguageType) -> List[Issue]:
    code = file_path.read_text(encoding="utf-8")
    analyzer = get_analyzer(language)
    return analyzer.analyze(code, str(file_path))


def detect_language(file_path: Path) -> Optional[LanguageType]:
    suffix = file_path.suffix.lower()
    if suffix == ".py":
        return LanguageType.PYTHON
    elif suffix in (".js", ".jsx"):
        return LanguageType.JAVASCRIPT
    elif suffix in (".ts", ".tsx"):
        return LanguageType.TYPESCRIPT
    return None