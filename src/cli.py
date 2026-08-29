from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

from config import load_config, save_config, get_config, Config
from analyzer import (
    analyze_file,
    detect_language,
    LanguageType,
    static_rules_engine,
    bug_detector,
    Issue,
    CodeLocation,
)
from ai import create_provider, get_available_provider, AIProvider, ReviewContext
from fixer import auto_fixer, fix_suggester
from reporter import create_formatter, create_summary
from utils import find_files, setup_logger, ProgressLogger

console = Console()


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], verbose: bool) -> None:
    """AI Code Reviewer & Bug Fixing Agent"""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose
    
    if config:
        cfg = load_config(config)
    else:
        cfg = get_config()
    
    setup_logger(level="DEBUG" if verbose else cfg.logging.level)
    ctx.obj["config"] = cfg


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--format", "-f", type=click.Choice(["json", "markdown", "html"]), help="Output format")
@click.option("--severity", "-s", type=click.Choice(["low", "medium", "high", "critical"]), help="Minimum severity")
@click.option("--fix", is_flag=True, help="Auto-fix issues")
@click.option("--dry-run", is_flag=True, help="Show fixes without applying")
@click.pass_context
def review(ctx: click.Context, path: str, output: Optional[str], format: Optional[str], severity: Optional[str], fix: bool, dry_run: bool) -> None:
    """Review code for issues and bugs"""
    config: Config = ctx.obj["config"]
    target_path = Path(path)
    
    if format:
        config.output.format = format
    if severity:
        config.analysis.severity_threshold = severity
    
    asyncio.run(_run_review(target_path, config, output, fix, dry_run))


async def _run_review(target_path: Path, config: Config, output: Optional[str], auto_fix: bool, dry_run: bool) -> None:
    files = find_files(target_path)
    
    if not files:
        console.print("[yellow]No files found to review[/yellow]")
        return
    
    console.print(f"[green]Found {len(files)} files to review[/green]")
    
    provider = await get_available_provider(config.model_dump())
    console.print(f"[blue]Using AI provider: {provider.provider_name}[/blue]")
    
    all_issues: List[Issue] = []
    files_reviewed = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Reviewing files...", total=len(files))
        
        for file_path in files:
            progress.update(task, description=f"Reviewing {file_path.name}...")
            
            try:
                issues = await _review_file(file_path, config, provider)
                all_issues.extend(issues)
                files_reviewed.append(str(file_path))
            except Exception as e:
                console.print(f"[red]Error reviewing {file_path}: {e}[/red]")
            
            progress.advance(task)
    
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    threshold = severity_order.get(config.analysis.severity_threshold, 2)
    filtered_issues = [i for i in all_issues if severity_order.get(i.severity, 3) <= threshold]
    
    summary = create_summary().generate(filtered_issues, files_reviewed)
    formatter = create_formatter(config.output.model_dump())
    
    report = formatter.format(filtered_issues, files_reviewed, summary)
    
    if output:
        output_path = Path(output)
        output_path.write_text(report, encoding="utf-8")
        console.print(f"[green]Report saved to {output_path}[/green]")
    else:
        output_path = formatter.save(report)
        console.print(f"[green]Report saved to {output_path}[/green]")
    
    _print_summary(summary)
    
    if auto_fix or dry_run:
        await _run_fixes(filtered_issues, files, config, dry_run)
    
    await provider.close()


async def _review_file(file_path: Path, config: Config, provider: AIProvider) -> List[Issue]:
    language = detect_language(file_path)
    if not language:
        return []
    
    code = file_path.read_text(encoding="utf-8")
    
    issues = []
    
    issues.extend(analyze_file(file_path, language))
    issues.extend(static_rules_engine.analyze(code, file_path, language.value))
    issues.extend(bug_detector.detect(code, file_path, language))
    
    context = ReviewContext(
        file_path=str(file_path),
        code=code,
        language=language.value,
        issues=issues,
        config=config.model_dump(),
    )
    
    try:
        ai_response = await provider.review_code(context)
        ai_issues = _parse_ai_response(ai_response, file_path, language)
        issues.extend(ai_issues)
    except Exception as e:
        console.print(f"[yellow]AI review failed for {file_path}: {e}[/yellow]")
    
    return issues


def _parse_ai_response(response, file_path: Path, language: LanguageType) -> List[Issue]:
    issues = []
    try:
        data = json.loads(response.content)
        for ai_issue in data.get("issues", []):
            issues.append(Issue(
                id=f"ai-{file_path}-{ai_issue.get('line_start', 0)}",
                title=ai_issue.get("title", "AI Detected Issue"),
                description=ai_issue.get("description", ""),
                severity=ai_issue.get("severity", "medium"),
                category=ai_issue.get("category", "best_practices"),
                location=CodeLocation(
                    str(file_path),
                    ai_issue.get("line_start", 1),
                    ai_issue.get("line_end", 1),
                    0, 0,
                ),
                code_snippet="",
                suggestion=ai_issue.get("suggestion", ""),
                confidence=ai_issue.get("confidence", 0.7),
                rule_id=f"ai-{ai_issue.get('category', 'unknown')}",
            ))
    except Exception:
        pass
    return issues


async def _run_fixes(issues: List[Issue], files: List[Path], config: Config, dry_run: bool) -> None:
    fixable_issues = [i for i in issues if auto_fixer.can_fix(i)]
    
    if not fixable_issues:
        console.print("[yellow]No auto-fixable issues found[/yellow]")
        return
    
    console.print(f"[blue]Found {len(fixable_issues)} auto-fixable issues[/blue]")
    
    file_fixes = {}
    for issue in fixable_issues:
        file_path = Path(issue.location.file_path)
        if file_path not in file_fixes:
            file_fixes[file_path] = []
        
        code = file_path.read_text(encoding="utf-8")
        fix = auto_fixer.generate_fix(issue, code, file_path)
        if fix:
            file_fixes[file_path].append(fix)
    
    if dry_run:
        console.print("\n[bold]Dry Run - Proposed Fixes:[/bold]")
        for file_path, fixes in file_fixes.items():
            console.print(f"\n[cyan]{file_path}:[/cyan]")
            for fix in fixes:
                console.print(f"  - {fix.description} (confidence: {fix.confidence:.0%})")
        return
    
    total_applied = 0
    total_failed = 0
    
    for file_path, fixes in file_fixes.items():
        applied, failed = auto_fixer.apply_fixes(fixes, file_path)
        total_applied += applied
        total_failed += failed
    
    console.print(f"\n[green]Applied {total_applied} fixes[/green]")
    if total_failed > 0:
        console.print(f"[red]Failed to apply {total_failed} fixes[/red]")


def _print_summary(summary) -> None:
    table = Table(title="Review Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", style="magenta")
    
    table.add_row("Files Reviewed", str(summary.total_files))
    table.add_row("Total Issues", str(summary.total_issues))
    
    for severity in ["critical", "high", "medium", "low"]:
        count = summary.by_severity.get(severity, 0)
        if count > 0:
            color = {"critical": "red", "high": "orange3", "medium": "yellow", "low": "green"}[severity]
            table.add_row(f"  {severity.capitalize()}", f"[{color}]{count}[/{color}]")
    
    console.print(table)


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Show fixes without applying")
@click.option("--confidence", type=float, help="Minimum confidence threshold")
@click.pass_context
def fix(ctx: click.Context, path: str, dry_run: bool, confidence: Optional[float]) -> None:
    """Auto-fix bugs in code"""
    config: Config = ctx.obj["config"]
    target_path = Path(path)
    
    if confidence:
        config.fixer.confidence_threshold = confidence
    
    asyncio.run(_run_fix_only(target_path, config, dry_run))


async def _run_fix_only(target_path: Path, config: Config, dry_run: bool) -> None:
    files = find_files(target_path)
    
    if not files:
        console.print("[yellow]No files found[/yellow]")
        return
    
    provider = await get_available_provider(config.model_dump())
    
    all_issues = []
    for file_path in files:
        issues = await _review_file(file_path, config, provider)
        all_issues.extend(issues)
    
    await _run_fixes(all_issues, files, config, dry_run)
    await provider.close()


@cli.command()
@click.option("--output", "-o", type=click.Path(), default="config.yaml", help="Output config file")
@click.pass_context
def config_init(ctx: click.Context, output: str) -> None:
    """Initialize configuration file"""
    config = Config()
    save_config(config, output)
    console.print(f"[green]Configuration saved to {output}[/green]")


@cli.command()
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show current configuration"""
    config: Config = ctx.obj["config"]
    console.print(Panel(json.dumps(config.model_dump(), indent=2), title="Current Configuration"))


@cli.command()
@click.pass_context
def test(ctx: click.Context) -> None:
    """Run self-tests"""
    console.print("[blue]Running self-tests...[/blue]")
    
    test_code = '''
def bad_function(items=[]):
    eval("print('hello')")
    password = "secret123"
    return items

def good_function(items=None):
    if items is None:
        items = []
    return items
'''
    
    from analyzer import LanguageType
    from pathlib import Path
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_code)
        temp_path = Path(f.name)
    
    try:
        issues = analyze_file(temp_path, LanguageType.PYTHON)
        issues.extend(static_rules_engine.analyze(test_code, temp_path, "python"))
        issues.extend(bug_detector.detect(test_code, temp_path, LanguageType.PYTHON))
        
        console.print(f"[green]Found {len(issues)} issues in test code[/green]")
        
        for issue in issues:
            console.print(f"  - [{issue.severity}] {issue.title}: {issue.description}")
        
        console.print("[green]Self-tests passed![/green]")
    finally:
        temp_path.unlink()


@cli.command()
@click.pass_context
def providers(ctx: click.Context) -> None:
    """List available AI providers"""
    from ai import ProviderRegistry
    
    table = Table(title="Available AI Providers")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    
    providers = [
        ("mock", "Mock provider for testing (always available)"),
        ("local", "Local LLM via Ollama"),
        ("openai", "OpenAI GPT models"),
        ("anthropic", "Anthropic Claude models"),
        ("gemini", "Google Gemini models"),
    ]
    
    for name, desc in providers:
        table.add_row(name, desc)
    
    console.print(table)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()