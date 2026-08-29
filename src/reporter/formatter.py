from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from analyzer import Issue, CodeLocation


@dataclass
class ReviewSummary:
    total_files: int = 0
    total_issues: int = 0
    by_severity: Dict[str, int] = field(default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0})
    by_category: Dict[str, int] = field(default_factory=dict)
    by_file: Dict[str, int] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ReportFormatter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.output_format = config.get("format", "markdown")
        self.output_path = Path(config.get("path", "./reviews"))
        self.include_suggestions = config.get("include_suggestions", True)
        self.include_code_snippets = config.get("include_code_snippets", True)
        self.include_line_numbers = config.get("include_line_numbers", True)
        self.group_by = config.get("group_by", "file")
        
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
            autoescape=select_autoescape(["html", "xml"]),
        )
    
    def format(self, issues: List[Issue], files_reviewed: List[str], summary: ReviewSummary) -> str:
        if self.output_format == "json":
            return self._format_json(issues, files_reviewed, summary)
        elif self.output_format == "html":
            return self._format_html(issues, files_reviewed, summary)
        else:
            return self._format_markdown(issues, files_reviewed, summary)
    
    def save(self, content: str, file_name: str = None) -> Path:
        if file_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"review_{timestamp}.{self.output_format}"
        
        output_file = self.output_path / file_name
        output_file.write_text(content, encoding="utf-8")
        return output_file
    
    def _format_json(self, issues: List[Issue], files_reviewed: List[str], summary: ReviewSummary) -> str:
        return json.dumps({
            "summary": {
                "total_files": summary.total_files,
                "total_issues": summary.total_issues,
                "by_severity": summary.by_severity,
                "by_category": summary.by_category,
                "by_file": summary.by_file,
                "timestamp": summary.timestamp,
            },
            "files_reviewed": files_reviewed,
            "issues": [issue.to_dict() for issue in issues],
        }, indent=2)
    
    def _format_markdown(self, issues: List[Issue], files_reviewed: List[str], summary: ReviewSummary) -> str:
        lines = []
        
        lines.append("# Code Review Report")
        lines.append(f"**Generated:** {summary.timestamp}")
        lines.append(f"**Files Reviewed:** {summary.total_files}")
        lines.append(f"**Total Issues:** {summary.total_issues}")
        lines.append("")
        
        lines.append("## Summary by Severity")
        for severity in ["critical", "high", "medium", "low"]:
            count = summary.by_severity.get(severity, 0)
            if count > 0:
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[severity]
                lines.append(f"- {emoji} **{severity.capitalize()}:** {count}")
        lines.append("")
        
        lines.append("## Summary by Category")
        for category, count in sorted(summary.by_category.items()):
            lines.append(f"- **{category.replace('_', ' ').title()}:** {count}")
        lines.append("")
        
        if self.group_by == "file":
            lines.append(self._group_by_file(issues))
        elif self.group_by == "severity":
            lines.append(self._group_by_severity(issues))
        elif self.group_by == "category":
            lines.append(self._group_by_category(issues))
        
        return "\n".join(lines)
    
    def _group_by_file(self, issues: List[Issue]) -> str:
        lines = ["## Issues by File", ""]
        
        by_file: Dict[str, List[Issue]] = {}
        for issue in issues:
            file_key = issue.location.file_path
            if file_key not in by_file:
                by_file[file_key] = []
            by_file[file_key].append(issue)
        
        for file_path, file_issues in sorted(by_file.items()):
            lines.append(f"### {file_path}")
            lines.append("")
            
            for issue in sorted(file_issues, key=lambda x: (x.location.line_start, x.severity)):
                lines.append(self._format_issue(issue))
                lines.append("")
        
        return "\n".join(lines)
    
    def _group_by_severity(self, issues: List[Issue]) -> str:
        lines = ["## Issues by Severity", ""]
        
        for severity in ["critical", "high", "medium", "low"]:
            sev_issues = [i for i in issues if i.severity == severity]
            if not sev_issues:
                continue
            
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[severity]
            lines.append(f"### {emoji} {severity.capitalize()} ({len(sev_issues)})")
            lines.append("")
            
            for issue in sorted(sev_issues, key=lambda x: x.location.file_path):
                lines.append(self._format_issue(issue))
                lines.append("")
        
        return "\n".join(lines)
    
    def _group_by_category(self, issues: List[Issue]) -> str:
        lines = ["## Issues by Category", ""]
        
        by_category: Dict[str, List[Issue]] = {}
        for issue in issues:
            if issue.category not in by_category:
                by_category[issue.category] = []
            by_category[issue.category].append(issue)
        
        for category, cat_issues in sorted(by_category.items()):
            lines.append(f"### {category.replace('_', ' ').title()} ({len(cat_issues)})")
            lines.append("")
            
            for issue in sorted(cat_issues, key=lambda x: (x.severity, x.location.file_path)):
                lines.append(self._format_issue(issue))
                lines.append("")
        
        return "\n".join(lines)
    
    def _format_issue(self, issue: Issue) -> str:
        lines = []
        
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        emoji = severity_emoji.get(issue.severity, "⚪")
        
        lines.append(f"#### {emoji} {issue.title} [{issue.severity.upper()}]")
        lines.append(f"**Rule:** `{issue.rule_id}` | **Category:** {issue.category} | **Confidence:** {issue.confidence:.0%}")
        lines.append(f"**Location:** {issue.location}")
        lines.append(f"**Description:** {issue.description}")
        
        if self.include_code_snippets and issue.code_snippet:
            lines.append("")
            lines.append("**Code:**")
            lines.append(f"```")
            lines.append(issue.code_snippet)
            lines.append("```")
        
        if self.include_suggestions and issue.suggestion:
            lines.append("")
            lines.append(f"**Suggestion:** {issue.suggestion}")
        
        return "\n".join(lines)
    
    def _format_html(self, issues: List[Issue], files_reviewed: List[str], summary: ReviewSummary) -> str:
        template = self.jinja_env.get_template("report.html")
        
        grouped = self._group_issues(issues)
        
        return template.render(
            summary=summary,
            files_reviewed=files_reviewed,
            grouped_issues=grouped,
            include_suggestions=self.include_suggestions,
            include_code_snippets=self.include_code_snippets,
            include_line_numbers=self.include_line_numbers,
        )
    
    def _group_issues(self, issues: List[Issue]) -> Dict[str, List[Issue]]:
        grouped = {}
        for issue in issues:
            key = ""
            if self.group_by == "file":
                key = issue.location.file_path
            elif self.group_by == "severity":
                key = issue.severity
            elif self.group_by == "category":
                key = issue.category
            else:
                key = issue.location.file_path
            
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(issue)
        
        return grouped


class SummaryGenerator:
    @staticmethod
    def generate(issues: List[Issue], files_reviewed: List[str]) -> ReviewSummary:
        summary = ReviewSummary(
            total_files=len(files_reviewed),
            total_issues=len(issues),
        )
        
        for issue in issues:
            summary.by_severity[issue.severity] = summary.by_severity.get(issue.severity, 0) + 1
            summary.by_category[issue.category] = summary.by_category.get(issue.category, 0) + 1
            summary.by_file[issue.location.file_path] = summary.by_file.get(issue.location.file_path, 0) + 1
        
        return summary


def create_formatter(config: Dict[str, Any]) -> ReportFormatter:
    return ReportFormatter(config)


def create_summary() -> SummaryGenerator:
    return SummaryGenerator()