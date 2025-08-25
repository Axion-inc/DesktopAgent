"""
Logging utilities for Desktop Agent
Provides consistent logging configuration across the application
"""

import logging
import sys
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance with consistent configuration"""
    logger_name = name or __name__
    logger = logging.getLogger(logger_name)

    if not logger.handlers:
        # Configure logger if not already configured
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def setup_logging(level: str = 'INFO') -> None:
    """Setup logging configuration for the entire application"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
