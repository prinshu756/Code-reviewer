from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from config import get_config


def setup_logger(name: str = "code-reviewer", level: Optional[str] = None) -> logging.Logger:
    config = get_config()
    log_level = level or config.logging.level
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(config.logging.format)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    log_file = Path(config.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "code-reviewer") -> logging.Logger:
    return logging.getLogger(name)


class ProgressLogger:
    def __init__(self, logger: logging.Logger, total: int, prefix: str = "Progress"):
        self.logger = logger
        self.total = total
        self.current = 0
        self.prefix = prefix
    
    def update(self, increment: int = 1, message: str = "") -> None:
        self.current += increment
        percent = (self.current / self.total * 100) if self.total > 0 else 0
        self.logger.info(f"{self.prefix}: {self.current}/{self.total} ({percent:.1f}%) {message}")
    
    def finish(self, message: str = "Complete") -> None:
        self.logger.info(f"{self.prefix}: {self.total}/{self.total} (100%) {message}")