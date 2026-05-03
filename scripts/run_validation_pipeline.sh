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

mkdir -p outputs/encoded outputs/decoded outputs/metrics outputs/plots outputs/reports "$REPORT_DIR"

log() {
    echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"
}

log "=== Step 1: Generate synthetic YUV clips ==="
bash scripts/generate_synthetic_clips.sh 2>&1 | tee -a "$LOG"

log "=== Step 2: Encode, verify, analyze, score, and validate ==="
python - <<'PYEOF' 2>&1 | tee -a "$LOG"
import csv
import json
import math
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

def safe_float(value):
    if value is None:
        return None
    try:
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    except Exception:
        return None

def codec_output_ext(codec):
    if codec == "libaom-av1":
        return ".mkv"
    return ".mp4"

def codec_label(codec):
    return (
        codec.replace("lib", "")
        .replace("-", "_")
        .replace(".", "_")
    )

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
        print(f"SKIP: input YUV not found: {yuv}", flush=True)
        continue

    encoder = CodecEncoder()
    evaluator = QualityEvaluator()
    config_rows = []

    for crf in cfg["crf_values"]:
        ext = codec_output_ext(codec)
        out = Path(cfg["output"]["dir"]) / f"{codec_label(codec)}_crf{crf}{ext}"
        ensure_dir(out.parent)

        failures = []
        decode_path = Path("outputs/decoded") / f"{out.stem}.yuv"
        ensure_dir(decode_path.parent)

        print(f"\n[RUN] {codec} CRF={crf} -> {out}", flush=True)

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

        encode_ok = enc.return_code == 0 and enc.output_path.is_file() and enc.file_size_bytes > 0

        if not encode_ok:
            failures.append(f"encode failed or produced empty output, return code {enc.return_code}")

        decode_ok = False
        frame_count_ok = False
        integrity_passed = False
        metadata = {}
        bitstream_summary = {}
        q = None

        if encode_ok:
            decode_ok = decoder.decode_to_yuv(
                enc.output_path,
                decode_path,
                inp["width"],
                inp["height"],
                cfg["fps"],
            )
            frame_count_ok = decoder.verify_frame_count(enc.output_path, inp["frames"])
            integrity = decoder.check_bitstream_integrity(enc.output_path)
            integrity_passed = integrity.passed

            metadata = analyzer.get_stream_metadata(enc.output_path)
            bitstream_summary = analyzer.summarize(enc.output_path)

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

            try:
                q = evaluator.compute_all(
                    yuv,
                    enc.output_path,
                    inp["width"],
                    inp["height"],
                    cfg["fps"],
                )
            except Exception as exc:
                failures.append(f"quality metric computation failed: {exc}")

        psnr_y = safe_float(getattr(q, "psnr_y_mean", None)) if q else None
        ssim = safe_float(getattr(q, "ssim_mean", None)) if q else None
        vmaf = safe_float(getattr(q, "vmaf_mean", None)) if q else None

        bpp = rd.compute_bpp(
            enc.file_size_bytes if enc.file_size_bytes else 0,
            inp["width"],
            inp["height"],
            inp["frames"],
        )

        metrics = {
            "psnr_y": psnr_y,
            "ssim": ssim,
            "vmaf": vmaf,
            "bpp": bpp,
            "encode_time_s": safe_float(enc.encode_time_s),
            "file_size_mb": enc.file_size_bytes / 1_048_576 if enc.file_size_bytes else 0.0,
        }

        threshold_key = build_threshold_key(codec, "crf", crf, inp["width"], inp["height"])
        threshold_rules = thresholds_all.get(threshold_key, {})

        threshold_pass = True
        threshold_failures = []

        if threshold_rules:
            threshold_pass, threshold_failures = evaluate_thresholds(metrics, threshold_rules)
            failures.extend(threshold_failures)

        row = {
            "config": cfg_path,
            "codec": codec,
            "mode": "crf",
            "crf_or_bitrate": crf,
            "input_yuv": str(yuv),
            "width": inp["width"],
            "height": inp["height"],
            "fps": cfg["fps"],
            "frames_expected": inp["frames"],
            "bpp": bpp,
            "psnr_y": psnr_y,
            "ssim": ssim,
            "vmaf": vmaf,
            "encode_time_s": safe_float(enc.encode_time_s),
            "file_size_mb": metrics["file_size_mb"],
            "bitrate": metadata.get("bitrate"),
            "duration": metadata.get("duration"),
            "profile": metadata.get("profile"),
            "pixel_format": metadata.get("pixel_format"),
            "gop_count": bitstream_summary.get("gop_count"),
            "gop_max": bitstream_summary.get("gop_max"),
            "encode_ok": encode_ok,
            "decode_ok": decode_ok,
            "frame_count_ok": frame_count_ok,
            "integrity_ok": integrity_passed,
            "threshold_key": threshold_key,
            "threshold_checked": bool(threshold_rules),
            "pass": len(failures) == 0 and threshold_pass,
            "failure_reason": "; ".join(failures),
            "output_path": str(enc.output_path),
            "decoded_output_path": str(decode_path),
        }

        config_rows.append(row)
        all_rows.append(row)

        psnr_print = f"{psnr_y:.2f}" if psnr_y is not None else "NA"
        ssim_print = f"{ssim:.4f}" if ssim is not None else "NA"
        vmaf_print = f"{vmaf:.2f}" if vmaf is not None else "NA"

        print(
            f"  {codec} CRF={crf:2d} PASS={row['pass']} "
            f"BPP={bpp:.4f} PSNR_Y={psnr_print} SSIM={ssim_print} VMAF={vmaf_print}",
            flush=True,
        )

        if failures:
            print(f"  Failures: {row['failure_reason']}", flush=True)

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

    print(f"\nSummary JSON -> {summary_json}", flush=True)
    print(f"Summary CSV  -> {summary_csv}", flush=True)
else:
    raise SystemExit("No validation rows generated. Check input files and config paths.")
PYEOF

log "=== Step 3: pytest ==="
python -m pytest tests/ -v --tb=short 2>&1 | tee -a "$LOG"

log "=== Validation complete. Log: $LOG ==="