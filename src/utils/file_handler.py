from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import List, Optional, Set

from analyzer import LanguageType, detect_language
from config import get_config


def find_files(
    path: Path,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    languages: Optional[List[str]] = None,
) -> List[Path]:
    if include_patterns is None:
        config = get_config()
        include_patterns = config.analysis.include_patterns
    
    if exclude_patterns is None:
        config = get_config()
        exclude_patterns = config.analysis.exclude_patterns
    
    if languages is None:
        config = get_config()
        languages = config.analysis.languages
    
    files = []
    
    if path.is_file():
        if _should_include(path, include_patterns, exclude_patterns, languages):
            files.append(path)
        return files
    
    for root, dirs, filenames in os.walk(path):
        root_path = Path(root)
        
        dirs[:] = [d for d in dirs if not _should_exclude_dir(root_path / d, exclude_patterns)]
        
        for filename in filenames:
            file_path = root_path / filename
            if _should_include(file_path, include_patterns, exclude_patterns, languages):
                files.append(file_path)
    
    return sorted(files)


def _should_include(
    file_path: Path,
    include_patterns: List[str],
    exclude_patterns: List[str],
    languages: List[str],
) -> bool:
    rel_path = file_path
    
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(str(rel_path), pattern) or fnmatch.fnmatch(file_path.name, pattern):
            return False
    
    for pattern in include_patterns:
        if fnmatch.fnmatch(str(rel_path), pattern) or fnmatch.fnmatch(file_path.name, pattern):
            lang = detect_language(file_path)
            if lang and lang.value in languages:
                return True
            if not lang and any(file_path.suffix.lower() == f".{l}" for l in languages):
                return True
    
    return False


def _should_exclude_dir(dir_path: Path, exclude_patterns: List[str]) -> bool:
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(str(dir_path), pattern) or fnmatch.fnmatch(dir_path.name, pattern):
            return True
    return False


def read_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="latin-1")


def write_file(file_path: Path, content: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def get_file_language(file_path: Path) -> Optional[LanguageType]:
    return detect_language(file_path)


def is_binary_file(file_path: Path) -> bool:
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except Exception:
        return True