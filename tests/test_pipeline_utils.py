"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    test_pipeline_utils.py
Purpose: Unit tests for config loading, directory creation, and validation rules.

Description:
    These focused tests validate the small shared utilities that make pipeline
    runs deterministic: YAML parsing, path creation, threshold lookup, and
    pass/fail rule evaluation.
"""

import pytest

from src.pipeline_utils import (
    build_threshold_key,
    ensure_dir,
    evaluate_thresholds,
    load_config,
    load_thresholds,
)


def test_load_config_reads_yaml_mapping(tmp_path):
    """load_config should parse a valid YAML mapping."""
    path = tmp_path / "config.yaml"
    path.write_text("codec: libx264\ncrf_values: [23]\n", encoding="utf-8")
    assert load_config(path)["codec"] == "libx264"


def test_load_config_rejects_non_mapping_yaml(tmp_path):
    """load_config should reject top-level YAML lists."""
    path = tmp_path / "bad.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Expected a YAML mapping"):
        load_config(path)


def test_ensure_dir_creates_nested_path(tmp_path):
    """ensure_dir should create missing parent directories."""
    target = tmp_path / "a" / "b"
    assert ensure_dir(target).is_dir()


def test_load_thresholds_returns_named_block(tmp_path):
    """load_thresholds should return one named scenario block."""
    path = tmp_path / "thresholds.yaml"
    path.write_text("h264_crf23_352x288:\n  min_psnr_y: 36.0\n", encoding="utf-8")
    assert load_thresholds(path, "h264_crf23_352x288")["min_psnr_y"] == 36.0


def test_evaluate_thresholds_pass_and_fail_cases():
    """evaluate_thresholds should produce clear pass/fail reasons."""
    passed, failures = evaluate_thresholds(
        {"psnr_y": 40.0, "encode_time_s": 3.0},
        {"min_psnr_y": 36.0, "max_encode_time_s": 10.0},
    )
    assert passed is True
    assert failures == []

    passed, failures = evaluate_thresholds(
        {"psnr_y": 30.0, "encode_time_s": 12.0},
        {"min_psnr_y": 36.0, "max_encode_time_s": 10.0},
    )
    assert passed is False
    assert len(failures) == 2


def test_build_threshold_key_matches_config_convention():
    """Threshold key builder should match validation_thresholds.yaml naming."""
    assert build_threshold_key("libx264", "crf", 23, 352, 288) == "h264_crf23_352x288"
    assert build_threshold_key("libx265", "cbr", 800, 1280, 720) == "hevc_cbr_800k_1280x720"
