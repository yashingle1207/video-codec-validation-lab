"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    pipeline_utils.py
Purpose: Shared infrastructure utilities for logging, directories, YAML configs,
         and pass/fail validation rules used by the pipeline.

Description:
    Provides stateless helpers consumed across the pipeline: get_logger() for
    consistent module logs, ensure_dir() for idempotent directory creation,
    load_config() / load_thresholds() for safe YAML ingestion, and validation
    helpers that turn metric dictionaries into deterministic pass/fail results.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import yaml


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """Return a module-level logger wired to stdout with a consistent format.

    Attaches a StreamHandler only once, so calling get_logger multiple times
    for the same name is safe and idempotent.

    Args:
        name: Logger name, typically ``__name__`` from the calling module.
        level: Logging verbosity.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def ensure_dir(path: str | Path) -> Path:
    """Create a directory and all parents if needed.

    Args:
        path: Directory path to create.

    Returns:
        pathlib.Path: Directory path as a Path object.

    Raises:
        OSError: If the directory cannot be created.
    """
    p = Path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Cannot create directory '{p}': {exc}") from exc
    return p


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Load and parse a YAML configuration file into a dictionary.

    Args:
        config_path: Path to a YAML file.

    Returns:
        dict[str, Any]: Parsed top-level YAML mapping.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a YAML mapping.
    """
    p = Path(config_path)
    if not p.is_file():
        raise FileNotFoundError(f"Config file not found: '{p}'")

    try:
        with p.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse YAML '{p}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a YAML mapping at root of '{p}', got {type(data).__name__}"
        )
    return data


def load_thresholds(thresholds_path: str | Path, key: str) -> dict[str, Any]:
    """Load a named scenario block from ``validation_thresholds.yaml``.

    Args:
        thresholds_path: Path to the thresholds YAML file.
        key: Top-level scenario key.

    Returns:
        dict[str, Any]: Threshold values for the scenario.

    Raises:
        KeyError: If the scenario key is not present.
    """
    data = load_config(thresholds_path)
    if key not in data:
        raise KeyError(
            f"Threshold key '{key}' not found in '{thresholds_path}'. "
            f"Available keys: {list(data.keys())}"
        )
    return data[key]


def evaluate_thresholds(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Evaluate scalar metrics against ``min_`` and ``max_`` threshold rules.

    Threshold keys use ``min_<metric>`` or ``max_<metric>`` naming. For example,
    ``min_psnr_y`` checks ``metrics["psnr_y"] >= threshold`` and
    ``max_encode_time_s`` checks ``metrics["encode_time_s"] <= threshold``.

    Args:
        metrics: Observed metric values from one validation run.
        thresholds: Threshold mapping loaded from the config file.

    Returns:
        tuple[bool, list[str]]: Pass flag and failure reasons.
    """
    failures: list[str] = []
    for key, expected in thresholds.items():
        if key.startswith("min_"):
            metric_name = key[4:]
            actual = metrics.get(metric_name)
            if actual is None or actual != actual or actual < expected:
                failures.append(f"{metric_name}={actual} below minimum {expected}")
        elif key.startswith("max_"):
            metric_name = key[4:]
            actual = metrics.get(metric_name)
            if actual is None or actual != actual or actual > expected:
                failures.append(f"{metric_name}={actual} above maximum {expected}")
    return len(failures) == 0, failures


def build_threshold_key(codec: str, mode: str, value: int, width: int, height: int) -> str:
    """Build the conventional validation threshold key for one encode point.

    Args:
        codec: FFmpeg codec name such as ``libx264`` or ``libx265``.
        mode: Encoding mode, typically ``crf`` or ``cbr``.
        value: CRF value or bitrate in kbps.
        width: Frame width in pixels.
        height: Frame height in pixels.

    Returns:
        str: Key such as ``h264_crf23_352x288``.
    """
    codec_prefix = {
        "libx264": "h264",
        "libx265": "hevc",
        "libaom-av1": "av1",
        "libvpx-vp9": "vp9",
    }.get(codec, codec.replace("lib", "").replace("-", "_"))
    value_part = f"{mode}_{value}k" if mode == "cbr" else f"{mode}{value}"
    return f"{codec_prefix}_{value_part}_{width}x{height}"
