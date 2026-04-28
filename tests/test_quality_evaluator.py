"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    test_quality_evaluator.py
Purpose: Unit tests for PSNR, SSIM, VMAF parsing and BPP calculations.

Description:
    Tests parse small synthetic metric logs and JSON payloads directly, avoiding
    FFmpeg execution while still validating the logic used by quality reports.
"""

import json

import pytest

from src.quality_evaluator import QualityEvaluator, QualityResult
from src.rd_curve_analyzer import RDCurveAnalyzer


def test_parse_vmaf_modern_json(tmp_path):
    """VMAF parser should read libvmaf pooled_metrics JSON."""
    path = tmp_path / "vmaf.json"
    path.write_text(json.dumps({
        "pooled_metrics": {"vmaf": {"mean": 91.5, "min": 80.0, "max": 98.0}},
        "frames": [{"metrics": {"vmaf": 90.0}}, {"metrics": {"vmaf": 93.0}}],
    }), encoding="utf-8")
    evaluator = QualityEvaluator(metrics_output_dir=tmp_path)
    result = evaluator._parse_vmaf_json(path)
    assert result["vmaf_mean"] == 91.5
    assert result["frame_count"] == 2


def test_parse_psnr_log_averages_luma_values(tmp_path):
    """PSNR parser should average per-frame Y-plane values."""
    path = tmp_path / "psnr.log"
    path.write_text(
        "n:1 mse_y:1 psnr_y:40.0 psnr_u:42.0 psnr_v:44.0\n"
        "n:2 mse_y:1 psnr_y:42.0 psnr_u:44.0 psnr_v:46.0\n",
        encoding="utf-8",
    )
    evaluator = QualityEvaluator(metrics_output_dir=tmp_path)
    result = evaluator._parse_psnr_log(path, "")
    assert result["psnr_y"] == 41.0
    assert result["frame_count"] == 2


def test_parse_ssim_log_averages_all_values(tmp_path):
    """SSIM parser should average per-frame All scores."""
    path = tmp_path / "ssim.log"
    path.write_text(
        "n:1 Y:0.95 U:0.96 V:0.97 All:0.95\n"
        "n:2 Y:0.97 U:0.98 V:0.99 All:0.97\n",
        encoding="utf-8",
    )
    evaluator = QualityEvaluator(metrics_output_dir=tmp_path)
    result = evaluator._parse_ssim_log(path, "")
    assert result["ssim_avg"] == pytest.approx(0.96)
    assert result["frame_count"] == 2


def test_compute_bpp_uses_bits_per_pixel_formula(tmp_path):
    """RDCurveAnalyzer should compute bytes-to-bits normalized by total pixels."""
    analyzer = RDCurveAnalyzer(plots_output_dir=tmp_path)
    assert analyzer.compute_bpp(100, width=10, height=10, frame_count=2) == 4.0


def test_quality_result_dataclass_holds_metric_summary(tmp_path):
    """QualityResult should preserve metric fields used by reports."""
    result = QualityResult(
        vmaf_mean=90.0,
        vmaf_min=80.0,
        psnr_y_mean=40.0,
        ssim_mean=0.95,
        frame_count=60,
        metrics_json_path=tmp_path / "vmaf.json",
    )
    assert result.vmaf_mean == 90.0
    assert result.psnr_y_mean == 40.0
