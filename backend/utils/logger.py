"""
Logging utilities
"""

import logging
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config import settings


def setup_logger(name: str, log_file: str = None) -> logging.Logger:
    """
    Setup a logger with file and console handlers.

    Args:
        name: Logger name
        log_file: Optional log file path (relative to LOGS_DIR)

    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # Evitar duplicar handlers
    if logger.handlers:
        return logger

    # Formato
    formatter = logging.Formatter(settings.LOG_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    if log_file:
        file_path = settings.LOGS_DIR / log_file
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
