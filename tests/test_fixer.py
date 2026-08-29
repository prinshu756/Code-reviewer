import tempfile
from pathlib import Path

import pytest

from fixer import AutoFixer, Fix, FixSuggester, auto_fixer, fix_suggester
from analyzer import Issue, CodeLocation


class TestAutoFixer:
    @pytest.fixture
    def fixer(self):
        return AutoFixer({
            "safe_only": True,
            "confidence_threshold": 0.8,
            "create_backup": False,
            "auto_fix_categories": ["style", "simple_bug", "unused_import"],
        })
    
    def test_can_fix_high_confidence(self, fixer):
        issue = Issue(
            id="test-1",
            title="Test",
            description="Test",
            severity="low",
            category="style",
            location=CodeLocation("test.py", 1, 1, 0, 10),
            confidence=0.9,
            rule_id="trailing-whitespace",
        )
        assert fixer.can_fix(issue) is True
    
    def test_can_fix_low_confidence(self, fixer):
        issue = Issue(
            id="test-1",
            title="Test",
            description="Test",
            severity="low",
            category="style",
            location=CodeLocation("test.py", 1, 1, 0, 10),
            confidence=0.5,
            rule_id="trailing-whitespace",
        )
        assert fixer.can_fix(issue) is False
    
    def test_can_fix_wrong_category(self, fixer):
        issue = Issue(
            id="test-1",
            title="Test",
            description="Test",
            severity="high",
            category="security",
            location=CodeLocation("test.py", 1, 1, 0, 10),
            confidence=0.9,
            rule_id="sql-injection",
        )
        assert fixer.can_fix(issue) is False
    
    def test_fix_trailing_whitespace(self, fixer):
        code = "def func():  \n    pass\n"
        issue = Issue(
            id="test-1",
            title="Trailing Whitespace",
            description="Trailing whitespace",
            severity="low",
            category="style",
            location=CodeLocation("test.py", 1, 1, 0, 14),
            confidence=0.9,
            rule_id="trailing-whitespace",
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            fix = fixer.generate_fix(issue, code, path)
            assert fix is not None
            # Check that trailing whitespace is removed
            assert "func():  " not in fix.fixed_code
            assert "func():" in fix.fixed_code
        finally:
            path.unlink()
    
    def test_fix_bare_except(self, fixer):
        code = "try:\n    pass\nexcept:\n    pass\n"
        issue = Issue(
            id="test-1",
            title="Bare Except",
            description="Bare except clause",
            severity="medium",
            category="bugs",
            location=CodeLocation("test.py", 3, 3, 0, 7),
            confidence=0.9,
            rule_id="bare-except",
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            fix = fixer.generate_fix(issue, code, path)
            assert fix is not None
            assert "except Exception:" in fix.fixed_code
        finally:
            path.unlink()
    
    def test_apply_fix(self, fixer):
        code = "def func():  \n    pass\n"
        issue = Issue(
            id="test-1",
            title="Trailing Whitespace",
            description="Trailing whitespace",
            severity="low",
            category="style",
            location=CodeLocation("test.py", 1, 1, 0, 14),
            confidence=0.9,
            rule_id="trailing-whitespace",
        )
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            path = Path(f.name)
        
        try:
            fix = fixer.generate_fix(issue, code, path)
            assert fix is not None
            
            result = fixer.apply_fix(fix, path)
            assert result is True
            assert fix.applied is True
            
            new_code = path.read_text()
            assert "func():  " not in new_code
            assert "func():" in new_code
        finally:
            path.unlink()


class TestFixSuggester:
    def test_suggest_fix_mutable_default(self):
        issue = Issue(
            id="test-1",
            title="Mutable Default Argument",
            description="Mutable default",
            severity="high",
            category="bugs",
            location=CodeLocation("test.py", 1, 1, 0, 20),
            confidence=0.9,
            rule_id="mutable-default-argument",
        )
        code = "def func(items=[]):\n    return items"
        
        suggestion = fix_suggester.suggest_fix(issue, code)
        assert suggestion is not None
        assert "None" in suggestion
    
    def test_get_suggestions(self):
        issue = Issue(
            id="test-1",
            title="Mutable Default Argument",
            description="Mutable default",
            severity="high",
            category="bugs",
            location=CodeLocation("test.py", 1, 1, 0, 20),
            confidence=0.9,
            rule_id="mutable-default-argument",
        )
        
        suggestions = fix_suggester.get_suggestions(issue)
        assert len(suggestions) > 0
        assert any("None" in s for s in suggestions)
    
    def test_unknown_rule(self):
        issue = Issue(
            id="test-1",
            title="Unknown",
            description="Unknown rule",
            severity="low",
            category="style",
            location=CodeLocation("test.py", 1, 1, 0, 10),
            confidence=0.5,
            rule_id="unknown-rule",
        )
        
        suggestions = fix_suggester.get_suggestions(issue)
        assert len(suggestions) == 1
        assert suggestions[0] == "Review and fix manually"


class TestFixDataclass:
    def test_fix_creation(self):
        fix = Fix(
            issue_id="test-1",
            original_code="code",
            fixed_code="fixed code",
            description="Test fix",
            confidence=0.9,
        )
        
        assert fix.issue_id == "test-1"
        assert fix.applied is False
        assert fix.error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])