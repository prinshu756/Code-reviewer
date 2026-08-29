from __future__ import annotations

import ast
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from analyzer import Issue, CodeLocation


@dataclass
class Fix:
    issue_id: str
    original_code: str
    fixed_code: str
    description: str
    confidence: float
    applied: bool = False
    error: Optional[str] = None


class AutoFixer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.safe_only = config.get("safe_only", True)
        self.confidence_threshold = config.get("confidence_threshold", 0.85)
        self.create_backup = config.get("create_backup", True)
        self.auto_fix_categories = set(config.get("auto_fix_categories", ["style", "simple_bug", "unused_import"]))
    
    def can_fix(self, issue: Issue) -> bool:
        if self.safe_only and issue.confidence < self.confidence_threshold:
            return False
        if issue.category not in self.auto_fix_categories:
            return False
        return True
    
    def generate_fix(self, issue: Issue, code: str, file_path: Path) -> Optional[Fix]:
        fixers = {
            "mutable-default-argument": self._fix_mutable_default,
            "empty-function": self._fix_empty_function,
            "unused-import": self._fix_unused_import,
            "bare-except": self._fix_bare_except,
            "hardcoded-secret": self._fix_hardcoded_secret,
            "debug-code": self._fix_debug_code,
            "trailing-whitespace": self._fix_trailing_whitespace,
            "missing-docstring": self._fix_missing_docstring,
        }
        
        fixer = fixers.get(issue.rule_id)
        if fixer:
            try:
                fixed_code = fixer(code, issue, file_path)
                if fixed_code != code:
                    return Fix(
                        issue_id=issue.id,
                        original_code=code,
                        fixed_code=fixed_code,
                        description=f"Auto-fix for {issue.title}",
                        confidence=issue.confidence,
                    )
            except Exception as e:
                return Fix(
                    issue_id=issue.id,
                    original_code=code,
                    fixed_code=code,
                    description=f"Fix failed: {str(e)}",
                    confidence=0.0,
                    error=str(e),
                )
        return None
    
    def _fix_mutable_default(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            line = lines[line_idx]
            new_line = re.sub(r'(\w+)\s*=\s*\[\s*\]', r'\1=None', line)
            new_line = re.sub(r'(\w+)\s*=\s*\{\s*\}', r'\1=None', new_line)
            
            if new_line != line:
                indent = len(line) - len(line.lstrip())
                body_line = " " * (indent + 4) + "if " + new_line.split("=")[0].strip() + " is None:\n"
                body_line += " " * (indent + 4) + new_line.split("=")[0].strip() + " = []\n"
                
                lines[line_idx] = new_line
                lines.insert(line_idx + 1, body_line)
        
        return "\n".join(lines)
    
    def _fix_empty_function(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            line = lines[line_idx]
            indent = len(line) - len(line.lstrip())
            lines[line_idx] = line + "\n" + " " * (indent + 4) + "# TODO: Implement this function\n" + " " * (indent + 4) + "pass"
        
        return "\n".join(lines)
    
    def _fix_unused_import(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            lines.pop(line_idx)
        
        return "\n".join(lines)
    
    def _fix_bare_except(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            line = lines[line_idx]
            lines[line_idx] = line.replace("except:", "except Exception:")
        
        return "\n".join(lines)
    
    def _fix_hardcoded_secret(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            line = lines[line_idx]
            match = re.search(r'(\w+)\s*=\s*["\']([^"\']+)["\']', line)
            if match:
                var_name = match.group(1)
                lines[line_idx] = f"{var_name} = os.environ.get('{var_name.upper()}')"
                if "import os" not in code:
                    lines.insert(0, "import os")
        
        return "\n".join(lines)
    
    def _fix_debug_code(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            lines.pop(line_idx)
        
        return "\n".join(lines)
    
    def _fix_trailing_whitespace(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            lines[line_idx] = lines[line_idx].rstrip()
        
        return "\n".join(lines)
    
    def _fix_missing_docstring(self, code: str, issue: Issue, file_path: Path) -> str:
        lines = code.splitlines()
        line_idx = issue.location.line_start - 1
        
        if line_idx < len(lines):
            line = lines[line_idx]
            indent = len(line) - len(line.lstrip())
            docstring = ' ' * (indent + 4) + '"""TODO: Add docstring"""'
            lines.insert(line_idx + 1, docstring)
        
        return "\n".join(lines)
    
    def apply_fix(self, fix: Fix, file_path: Path) -> bool:
        try:
            if self.create_backup:
                backup_path = file_path.with_suffix(file_path.suffix + ".bak")
                shutil.copy2(file_path, backup_path)
            
            file_path.write_text(fix.fixed_code, encoding="utf-8")
            fix.applied = True
            return True
        except Exception as e:
            fix.error = str(e)
            return False
    
    def apply_fixes(self, fixes: List[Fix], file_path: Path) -> Tuple[int, int]:
        applied = 0
        failed = 0
        
        for fix in fixes:
            if self.apply_fix(fix, file_path):
                applied += 1
            else:
                failed += 1
        
        return applied, failed


class FixSuggester:
    def __init__(self):
        self.fix_templates = {
            "mutable-default-argument": {
                "pattern": r'(\w+)\s*=\s*\[\s*\]',
                "replacement": r'\1=None',
                "addition": "if {var} is None:\n    {var} = []",
                "description": "Replace mutable default with None pattern",
            },
            "bare-except": {
                "pattern": r'except\s*:',
                "replacement": "except Exception:",
                "description": "Specify exception type",
            },
            "hardcoded-secret": {
                "pattern": r'(\w+)\s*=\s*["\']([^"\']+)["\']',
                "replacement": r'\1 = os.environ.get("\2".upper())',
                "description": "Move secret to environment variable",
            },
            "sql-injection": {
                "pattern": r'cursor\.execute\s*\(\s*["\'](.*)%s(.*)["\']',
                "replacement": 'cursor.execute("\\1%\\2", (param,))',
                "description": "Use parameterized queries",
            },
            "command-injection": {
                "pattern": r'subprocess\.(run|call|Popen)\s*\(\s*["\']([^"\']+)["\']',
                "replacement": r'subprocess.\1(["\2".split()])',
                "description": "Use list form instead of shell string",
            },
        }
    
    def suggest_fix(self, issue: Issue, code: str) -> Optional[str]:
        template = self.fix_templates.get(issue.rule_id)
        if not template:
            return None
        
        try:
            fixed = re.sub(template["pattern"], template["replacement"], code)
            if fixed != code:
                return fixed
        except Exception:
            pass
        
        return None
    
    def get_suggestions(self, issue: Issue) -> List[str]:
        suggestions = {
            "mutable-default-argument": [
                "Use None as default value and create mutable object inside function",
                "Example: def func(items=None): if items is None: items = []"
            ],
            "bare-except": [
                "Catch specific exceptions instead of bare except",
                "Example: except ValueError: or except (ValueError, TypeError):"
            ],
            "hardcoded-secret": [
                "Move secrets to environment variables",
                "Use a secrets manager for production",
                "Never commit secrets to version control"
            ],
            "sql-injection": [
                "Use parameterized queries/prepared statements",
                "Never use string formatting for SQL queries",
                "Use ORM with built-in protection"
            ],
            "command-injection": [
                "Avoid shell=True in subprocess",
                "Use list arguments instead of string commands",
                "Validate and sanitize user input"
            ],
            "xss-vulnerability": [
                "Use framework's built-in escaping",
                "Use textContent instead of innerHTML",
                "Implement Content Security Policy"
            ],
            "debug-code": [
                "Remove debug statements before production",
                "Use proper logging instead of print/console.log",
                "Use debugger statements for development only"
            ],
            "empty-function": [
                "Implement the function logic",
                "Remove the function if not needed",
                "Add proper docstring"
            ],
            "high-cyclomatic-complexity": [
                "Break function into smaller functions",
                "Use early returns to reduce nesting",
                "Consider using strategy pattern"
            ],
            "large-class": [
                "Split class into smaller classes",
                "Use composition over inheritance",
                "Apply Single Responsibility Principle"
            ],
        }
        
        return suggestions.get(issue.rule_id, ["Review and fix manually"])


auto_fixer = AutoFixer({})
fix_suggester = FixSuggester()