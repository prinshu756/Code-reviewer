import tempfile
from pathlib import Path
from click.testing import CliRunner

import pytest

from cli import cli


class TestCLI:
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    @pytest.fixture
    def sample_code(self):
        return '''
def bad_function(items=[]):
    eval("print('hello')")
    password = "secret123"
    return items

def good_function(items=None):
    if items is None:
        items = []
    return items
'''
    
    def test_config_init(self, runner):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.yaml"
            result = runner.invoke(cli, ["config-init", "--output", str(config_path)])
            assert result.exit_code == 0
            assert config_path.exists()
    
    def test_config_show(self, runner):
        result = runner.invoke(cli, ["config-show"])
        assert result.exit_code == 0
        assert "ai" in result.output
    
    def test_providers_command(self, runner):
        result = runner.invoke(cli, ["providers"])
        assert result.exit_code == 0
        assert "mock" in result.output
        assert "local" in result.output
        assert "openai" in result.output
    
    def test_test_command(self, runner):
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 0
        assert "Self-tests passed" in result.output
    
    def test_review_command(self, runner, sample_code):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(sample_code)
            temp_path = Path(f.name)
        
        try:
            result = runner.invoke(cli, ["review", str(temp_path)])
            assert result.exit_code == 0
            assert "Found" in result.output
        finally:
            temp_path.unlink()
    
    def test_review_with_format(self, runner, sample_code):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(sample_code)
            temp_path = Path(f.name)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            try:
                result = runner.invoke(cli, ["review", str(temp_path), "--format", "json", "--output", str(output_path)])
                assert result.exit_code == 0
                assert output_path.exists()
            finally:
                temp_path.unlink()
    
    def test_fix_command_dry_run(self, runner, sample_code):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(sample_code)
            temp_path = Path(f.name)
        
        try:
            result = runner.invoke(cli, ["fix", str(temp_path), "--dry-run"])
            assert result.exit_code == 0
        finally:
            temp_path.unlink()
    
    def test_review_nonexistent_path(self, runner):
        result = runner.invoke(cli, ["review", "/nonexistent/path"])
        assert result.exit_code != 0
    
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "AI Code Reviewer" in result.output
        assert "review" in result.output
        assert "fix" in result.output
        assert "config" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])