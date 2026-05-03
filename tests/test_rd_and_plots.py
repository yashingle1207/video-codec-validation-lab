"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    test_rd_and_plots.py
Purpose: Unit tests for validation plot generation and BD-rate style helpers.

Description:
    Uses tiny synthetic CSV inputs to verify plotting and RD comparison scripts
    without requiring FFmpeg, encoded media, or generated YUV files.
"""

from pathlib import Path

import pandas as pd
import pytest

from scripts import generate_rd_analysis, generate_validation_plots


def _sample_report(path: Path) -> Path:
    """Write a small validation_summary-style CSV for script tests."""
    pd.DataFrame([
        {"codec": "libx264", "crf_or_bitrate": 18, "bpp": 0.20, "psnr_y": 42.0, "ssim": 0.98, "encode_time_s": 1.0, "file_size_mb": 0.5, "pass": True},
        {"codec": "libx264", "crf_or_bitrate": 28, "bpp": 0.10, "psnr_y": 36.0, "ssim": 0.95, "encode_time_s": 0.8, "file_size_mb": 0.3, "pass": True},
        {"codec": "libx265", "crf_or_bitrate": 20, "bpp": 0.15, "psnr_y": 42.0, "ssim": 0.98, "encode_time_s": 2.0, "file_size_mb": 0.4, "pass": True},
        {"codec": "libx265", "crf_or_bitrate": 30, "bpp": 0.08, "psnr_y": 36.0, "ssim": 0.95, "encode_time_s": 1.5, "file_size_mb": 0.2, "pass": False},
    ]).to_csv(path, index=False)
    return path


def test_average_bitrate_saving_returns_negative_for_more_efficient_curve():
    """BD-rate helper should report savings when the test curve uses lower BPP."""
    ref = [(0.20, 36.0), (0.30, 40.0), (0.40, 44.0)]
    test = [(0.10, 36.0), (0.15, 40.0), (0.20, 44.0)]
    saving = generate_rd_analysis.average_bitrate_saving(test, ref)
    assert saving is not None
    assert saving < 0


def test_average_bitrate_saving_returns_none_without_overlap():
    """BD-rate helper should return None when quality ranges do not overlap."""
    assert generate_rd_analysis.average_bitrate_saving(
        [(0.10, 20.0), (0.20, 25.0)],
        [(0.30, 35.0), (0.40, 40.0)],
    ) is None


def test_generate_validation_plots_runs_on_sample_csv(tmp_path, monkeypatch):
    """Plot script should produce expected PNGs from a tiny CSV report."""
    report = _sample_report(tmp_path / "validation_summary.csv")
    monkeypatch.setattr(generate_validation_plots, "PLOTS_DIR", tmp_path / "plots")
    monkeypatch.setattr(generate_validation_plots, "DOCS_IMAGES_DIR", tmp_path / "docs_images")
    generated = generate_validation_plots.generate_plots(report)
    names = {path.name for path in generated}
    assert "rd_curve_psnr.png" in names
    assert "validation_pass_fail_summary.png" in names
    assert (tmp_path / "docs_images" / "rd_curve_psnr.png").is_file()


def test_generate_rd_analysis_writes_psnr_matrix(tmp_path, monkeypatch):
    """RD script should write PSNR curve and matrix files from sample report rows."""
    report = _sample_report(tmp_path / "validation_summary.csv")
    monkeypatch.setattr(generate_rd_analysis, "PLOTS_DIR", tmp_path / "plots")
    monkeypatch.setattr(generate_rd_analysis, "DOCS_IMAGES_DIR", tmp_path / "docs_images")
    generated = generate_rd_analysis.generate_rd_analysis(report)
    names = {path.name for path in generated}
    assert "rd_curve_psnr.png" in names
    assert "bd_rate_matrix_psnr.csv" in names
    assert "bd_rate_matrix_psnr.png" in names
    assert (tmp_path / "docs_images" / "bd_rate_matrix_psnr.png").is_file()
