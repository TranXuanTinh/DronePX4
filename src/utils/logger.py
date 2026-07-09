"""
Logger — Structured logging setup for the drone inspector.
"""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_dir: str = "data/logs",
    log_file: str = "mission.log",
) -> None:
    """Configure structured logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files
        log_file: Log filename
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Format
    fmt = "%(asctime)s [%(levelname)-7s] %(name)-25s | %(message)s"
    datefmt = "%H:%M:%S"

    # Root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(console)

    # File handler
    file_handler = logging.FileHandler(log_path / log_file)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(file_handler)

    # Suppress noisy libraries
    logging.getLogger("mavsdk").setLevel(logging.WARNING)
    logging.getLogger("ultralytics").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    logging.info(f"Logging initialized: level={level}, file={log_path / log_file}")
