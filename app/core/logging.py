"""Logging utilities."""
from __future__ import annotations

import logging.config
from pathlib import Path


def configure_logging() -> None:
    """Configure logging from the YAML configuration file if present."""
    config_path = Path(__file__).resolve().parent / "../.." / "configs" / "logging.yaml"
    if config_path.exists():
        import yaml  # type: ignore[import-untyped]

        with config_path.open("r", encoding="utf-8") as config_file:
            logging.config.dictConfig(yaml.safe_load(config_file))
    else:
        logging.basicConfig(level=logging.INFO)
