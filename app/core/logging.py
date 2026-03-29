"""
app/core/logging.py
-------------------
Centralized logging setup. Call configure_logging() once at startup.
"""

import logging
import warnings


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logger and silence noisy third-party loggers."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Suppress known experimental / verbose library noise
    logging.getLogger("google_genai._api_client").setLevel(logging.WARNING)

    warnings.filterwarnings(
        "ignore",
        message=r".*\[EXPERIMENTAL\].*BigQueryTool.*",
    )


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — use in every module instead of logging.getLogger."""
    return logging.getLogger(name)
