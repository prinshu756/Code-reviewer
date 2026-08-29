import tempfile
from pathlib import Path

import pytest

from analyzer import (
    analyze_file,
    detect_language,
    LanguageType,
    static_rules_engine,
    bug_detector,
    Issue,
    CodeLocation,
)


class TestLanguageDetection:
    def test_python_detection(self):
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            path = Path(f.name)
        try:
            assert detect_language(path) == LanguageType.PYTHON
        finally:
            path.unlink()
    
    def test_javascript_detection(self):
        with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as f:
            path = Path(f.name)
        try:
            assert detect_language(path) == LanguageType.JAVASCRIPT
        finally:
            path.unlink()
    
    def test_typescript_detection(self):
        with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
            path = Path(f.name)
        try:
            assert detect_language(path) == LanguageType.TYPESCRIPT
        finally:
            path.unlink()


class TestPythonASTAnalyzer:
    def test_empty_function(self):
        code = """
def empty_func():
    pass
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = analyze_file(path, LanguageType.PYTHON)
            empty_func_issues = [i for i in issues if i.rule_id == "empty-function"]
            assert len(empty_func_issues) == 1
            assert empty_func_issues[0].severity == "low"
        finally:
            path.unlink()
    
    def test_mutable_default_argument(self):
        code = """
def bad_func(items=[]):
    return items
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = analyze_file(path, LanguageType.PYTHON)
            mutable_issues = [i for i in issues if i.rule_id == "mutable-default-argument"]
            assert len(mutable_issues) == 1
            assert mutable_issues[0].severity == "high"
        finally:
            path.unlink()
    
    def test_dangerous_eval(self):
        code = """
def dangerous():
    eval("print('hello')")
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = analyze_file(path, LanguageType.PYTHON)
            eval_issues = [i for i in issues if i.rule_id == "dangerous-eval-exec"]
            assert len(eval_issues) == 1
            assert eval_issues[0].severity == "critical"
        finally:
            path.unlink()
    
    def test_high_complexity(self):
        code = """
def complex_func(x):
    if x > 0:
        if x > 1:
            if x > 2:
                if x > 3:
                    if x > 4:
                        if x > 5:
                            if x > 6:
                                if x > 7:
                                    if x > 8:
                                        if x > 9:
                                            return x
    return 0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = analyze_file(path, LanguageType.PYTHON)
            complexity_issues = [i for i in issues if i.rule_id == "high-cyclomatic-complexity"]
            assert len(complexity_issues) == 1
            assert complexity_issues[0].metadata["complexity"] > 10
        finally:
            path.unlink()


class TestStaticRulesEngine:
    def test_hardcoded_password(self):
        code = 'password = "secret123"'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = static_rules_engine.analyze(code, path, "python")
            pwd_issues = [i for i in issues if i.rule_id == "hardcoded-password"]
            assert len(pwd_issues) == 1
            assert pwd_issues[0].severity == "high"
        finally:
            path.unlink()
    
    def test_sql_injection(self):
        code = 'cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = static_rules_engine.analyze(code, path, "python")
            sql_issues = [i for i in issues if i.rule_id == "sql-injection"]
            assert len(sql_issues) == 1
            assert sql_issues[0].severity == "critical"
        finally:
            path.unlink()
    
    def test_debug_code(self):
        code = 'print("debug")'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = static_rules_engine.analyze(code, path, "python")
            debug_issues = [i for i in issues if i.rule_id == "debug-code"]
            assert len(debug_issues) == 1
            assert debug_issues[0].severity == "low"
        finally:
            path.unlink()
    
    def test_todo_comment(self):
        code = "# TODO: fix this later"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = static_rules_engine.analyze(code, path, "python")
            todo_issues = [i for i in issues if i.rule_id == "todo-comment"]
            assert len(todo_issues) == 1
            assert todo_issues[0].severity == "low"
        finally:
            path.unlink()


class TestBugDetector:
    def test_division_by_zero(self):
        code = """
def divide(a, b):
    return a / b
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = bug_detector.detect(code, path, LanguageType.PYTHON)
            div_issues = [i for i in issues if i.rule_id == "division-by-zero"]
            assert len(div_issues) == 1
            assert div_issues[0].severity == "high"
        finally:
            path.unlink()
    
    def test_resource_leak(self):
        code = """
def read_file():
    f = open("test.txt")
    return f.read()
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = bug_detector.detect(code, path, LanguageType.PYTHON)
            leak_issues = [i for i in issues if i.rule_id == "resource-leak"]
            assert len(leak_issues) == 1
            assert leak_issues[0].severity == "medium"
        finally:
            path.unlink()
    
    def test_infinite_loop_js(self):
        code = "while (true) { doSomething(); }"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            issues = bug_detector.detect(code, path, LanguageType.JAVASCRIPT)
            loop_issues = [i for i in issues if i.rule_id == "infinite-loop"]
            assert len(loop_issues) >= 1
        finally:
            path.unlink()


class TestIssueDataclass:
    def test_issue_to_dict(self):
        issue = Issue(
            id="test-1",
            title="Test Issue",
            description="Test description",
            severity="high",
            category="security",
            location=CodeLocation("test.py", 10, 10, 5, 15),
            code_snippet="test code",
            suggestion="Fix it",
            confidence=0.9,
            rule_id="test-rule",
        )
        
        d = issue.to_dict()
        assert d["id"] == "test-1"
        assert d["title"] == "Test Issue"
        assert d["severity"] == "high"
        assert d["location"] == "test.py:10:5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])