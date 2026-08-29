import tempfile
from pathlib import Path

import pytest

from reporter import ReportFormatter, ReviewSummary, create_formatter, create_summary
from analyzer import Issue, CodeLocation


class TestReporter:
    @pytest.fixture
    def sample_issues(self):
        return [
            Issue(
                id="1",
                title="Critical Security Issue",
                description="SQL injection vulnerability",
                severity="critical",
                category="security",
                location=CodeLocation("test.py", 10, 10, 5, 20),
                code_snippet="cursor.execute(query % user_input)",
                suggestion="Use parameterized queries",
                confidence=0.95,
                rule_id="sql-injection",
            ),
            Issue(
                id="2",
                title="Hardcoded Password",
                description="Password in source code",
                severity="high",
                category="security",
                location=CodeLocation("test.py", 20, 20, 0, 30),
                code_snippet='password = "secret123"',
                suggestion="Use environment variables",
                confidence=0.8,
                rule_id="hardcoded-password",
            ),
            Issue(
                id="3",
                title="Unused Import",
                description="Import not used",
                severity="low",
                category="style",
                location=CodeLocation("test.py", 1, 1, 0, 15),
                code_snippet="import os",
                suggestion="Remove unused import",
                confidence=0.9,
                rule_id="unused-import",
            ),
        ]
    
    @pytest.fixture
    def config(self):
        return {
            "format": "markdown",
            "path": "./reviews",
            "include_suggestions": True,
            "include_code_snippets": True,
            "include_line_numbers": True,
            "group_by": "file",
        }
    
    def test_markdown_format(self, sample_issues, config):
        formatter = create_formatter(config)
        summary = create_summary().generate(sample_issues, ["test.py"])
        
        report = formatter.format(sample_issues, ["test.py"], summary)
        
        assert "# Code Review Report" in report
        assert "Critical Security Issue" in report
        assert "Hardcoded Password" in report
        assert "Unused Import" in report
        assert "sql-injection" in report
        assert "### test.py" in report
    
    def test_json_format(self, sample_issues, config):
        config["format"] = "json"
        formatter = create_formatter(config)
        summary = create_summary().generate(sample_issues, ["test.py"])
        
        report = formatter.format(sample_issues, ["test.py"], summary)
        
        import json
        data = json.loads(report)
        
        assert "summary" in data
        assert "issues" in data
        assert len(data["issues"]) == 3
        assert data["summary"]["total_issues"] == 3
    
    def test_html_format(self, sample_issues, config):
        config["format"] = "html"
        formatter = create_formatter(config)
        summary = create_summary().generate(sample_issues, ["test.py"])
        
        report = formatter.format(sample_issues, ["test.py"], summary)
        
        assert "<!DOCTYPE html>" in report
        assert "Code Review Report" in report
        assert "Critical Security Issue" in report
    
    def test_save_report(self, sample_issues, config):
        formatter = create_formatter(config)
        summary = create_summary().generate(sample_issues, ["test.py"])
        report = formatter.format(sample_issues, ["test.py"], summary)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config["path"] = tmpdir
            formatter = create_formatter(config)
            output_path = formatter.save(report, "test_report.md")
            
            assert output_path.exists()
            saved = output_path.read_text(encoding="utf-8")
            assert saved == report
    
    def test_summary_generation(self, sample_issues):
        summary = create_summary().generate(sample_issues, ["test.py", "other.py"])
        
        assert summary.total_files == 2
        assert summary.total_issues == 3
        assert summary.by_severity["critical"] == 1
        assert summary.by_severity["high"] == 1
        assert summary.by_severity["low"] == 1
        assert summary.by_category["security"] == 2
        assert summary.by_category["style"] == 1
        assert summary.by_file["test.py"] == 3
    
    def test_group_by_severity(self, sample_issues, config):
        config["group_by"] = "severity"
        formatter = create_formatter(config)
        summary = create_summary().generate(sample_issues, ["test.py"])
        
        report = formatter.format(sample_issues, ["test.py"], summary)
        
        assert "## Issues by Severity" in report
        assert "Critical (1)" in report
        assert "High (1)" in report
        assert "Low (1)" in report
    
    def test_group_by_category(self, sample_issues, config):
        config["group_by"] = "category"
        formatter = create_formatter(config)
        summary = create_summary().generate(sample_issues, ["test.py"])
        
        report = formatter.format(sample_issues, ["test.py"], summary)
        
        assert "## Issues by Category" in report
        assert "### Security (2)" in report
        assert "### Style (1)" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])