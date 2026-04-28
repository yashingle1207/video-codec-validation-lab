#!/usr/bin/env bash
# =============================================================================
# Author:  Yash Daniel Ingle
# Email:   yashingle1207@gmail.com
# GitHub:  github.com/yashingle1207
# Project: Video Codec Validation Lab
# Script:  run_validation_pipeline.sh
# Purpose: Run encoding, decode verification, bitstream analysis, metrics, rules, and reports.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

REPORT_DIR="outputs/reports"
LOG="$REPORT_DIR/validation_pipeline_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$REPORT_DIR"

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

log "=== Step 1: Generate synthetic YUV clips ==="
bash scripts/generate_synthetic_clips.sh 2>&1 | tee -a "$LOG"

log "=== Step 2: Encode, verify, analyze, score, and validate ==="
python - <<'PYEOF' 2>&1 | tee -a "$LOG"
import csv
import json
from pathlib import Path

from src.bitstream_analyzer import BitstreamAnalyzer
from src.bitstream_decoder import DecodeVerifier
from src.codec_encoder import CodecEncoder
from src.pipeline_utils import (
    build_threshold_key,
    ensure_dir,
    evaluate_thresholds,
    load_config,
)
from src.quality_evaluator import QualityEvaluator
from src.rd_curve_analyzer import RDCurveAnalyzer

CONFIGS = [
    ("config/h264_avc_crf_sweep.yaml", "libx264"),
    ("config/h265_hevc_crf_sweep.yaml", "libx265"),
    ("config/av1_libaom_crf_sweep.yaml", "libaom-av1"),
]

thresholds_all = load_config("config/validation_thresholds.yaml")
rd = RDCurveAnalyzer()
analyzer = BitstreamAnalyzer()
decoder = DecodeVerifier()
all_rows = []

for cfg_path, codec in CONFIGS:
    cfg = load_config(cfg_path)
    inp = cfg["input"]
    yuv = Path(inp["yuv"])
    if not yuv.is_file():
        print(f"SKIP: {yuv} not found", flush=True)
        continue

    encoder = CodecEncoder()
    evaluator = QualityEvaluator()
    config_rows = []

    for crf in cfg["crf_values"]:
        out = Path(cfg["output"]["dir"]) / f"{codec.replace('lib', '')}_crf{crf}.mp4"
        enc = encoder.encode_crf(
            input_yuv=yuv,
            codec=codec,
            crf=crf,
            gop=cfg["gop"],
            preset=cfg.get("preset", "medium"),
            width=inp["width"],
            height=inp["height"],
            fps=cfg["fps"],
            output_path=out,
        )

        failures = []
        decode_path = Path("outputs/decoded") / f"{out.stem}.yuv"
        decode_ok = enc.return_code == 0 and decoder.decode_to_yuv(
            enc.output_path, decode_path, inp["width"], inp["height"], cfg["fps"]
        )
        frame_count_ok = enc.return_code == 0 and decoder.verify_frame_count(
            enc.output_path, inp["frames"]
        )
        integrity = decoder.check_bitstream_integrity(enc.output_path)
        metadata = analyzer.get_stream_metadata(enc.output_path)
        bitstream_summary = analyzer.summarize(enc.output_path)

        if enc.return_code != 0:
            failures.append(f"encode failed with return code {enc.return_code}")
        if not decode_ok:
            failures.append("decode verification failed")
        if not frame_count_ok:
            failures.append("frame count verification failed")
        if not integrity.passed:
            failures.extend(integrity.errors)
        if metadata.get("issues"):
            failures.extend(metadata["issues"])
        if bitstream_summary.get("issues"):
            failures.extend(bitstream_summary["issues"])

        q = evaluator.compute_all(yuv, enc.output_path, inp["width"], inp["height"], cfg["fps"])
        bpp = rd.compute_bpp(enc.file_size_bytes, inp["width"], inp["height"], inp["frames"])
        metrics = {
            "psnr_y": q.psnr_y_mean,
            "ssim": q.ssim_mean,
            "vmaf": q.vmaf_mean,
            "bpp": bpp,
            "encode_time_s": enc.encode_time_s,
            "file_size_mb": enc.file_size_bytes / 1_048_576 if enc.file_size_bytes else 0.0,
        }

        threshold_key = build_threshold_key(codec, "crf", crf, inp["width"], inp["height"])
        threshold_rules = thresholds_all.get(threshold_key, {})
        threshold_pass, threshold_failures = evaluate_thresholds(metrics, threshold_rules)
        failures.extend(threshold_failures)

        row = {
            "config": cfg_path,
            "codec": codec,
            "mode": "crf",
            "crf_or_bitrate": crf,
            "bpp": bpp,
            "psnr_y": q.psnr_y_mean,
            "ssim": q.ssim_mean,
            "vmaf": q.vmaf_mean,
            "encode_time_s": enc.encode_time_s,
            "bitrate": metadata.get("bitrate"),
            "duration": metadata.get("duration"),
            "profile": metadata.get("profile"),
            "pixel_format": metadata.get("pixel_format"),
            "gop_count": bitstream_summary.get("gop_count"),
            "gop_max": bitstream_summary.get("gop_max"),
            "decode_ok": decode_ok,
            "frame_count_ok": frame_count_ok,
            "integrity_ok": integrity.passed,
            "threshold_key": threshold_key,
            "threshold_checked": bool(threshold_rules),
            "pass": len(failures) == 0 and threshold_pass,
            "failure_reason": "; ".join(failures),
            "output_path": str(enc.output_path),
        }
        config_rows.append(row)
        all_rows.append(row)
        print(
            f"  {codec} CRF={crf:2d} PASS={row['pass']} "
            f"BPP={bpp:.4f} PSNR_Y={q.psnr_y_mean:.2f} SSIM={q.ssim_mean:.4f}",
            flush=True,
        )

    if config_rows:
        report = Path(cfg["output"]["report"])
        ensure_dir(report.parent)
        report.write_text(json.dumps(config_rows, indent=2), encoding="utf-8")
        print(f"  JSON report -> {report}", flush=True)

if all_rows:
    summary_json = Path("outputs/reports/validation_summary.json")
    summary_csv = Path("outputs/reports/validation_summary.csv")
    summary_json.write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
    with summary_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Summary JSON -> {summary_json}", flush=True)
    print(f"Summary CSV  -> {summary_csv}", flush=True)
PYEOF

log "=== Step 3: pytest ==="
python -m pytest tests/ -v --tb=short 2>&1 | tee -a "$LOG"

log "=== Validation complete. Log: $LOG ==="
