# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: validation_methodology.md
# Purpose: Document the block-level and system-level validation strategy.

# Validation Methodology

## Overview

This project applies a two-level validation strategy common in silicon and
encoder bring-up: **block-level validation** verifies correctness of isolated
components (frame statistics, bitstream syntax), while **system-level validation**
confirms end-to-end encode/decode quality and interoperability.

---

## Block-Level Validation

Block-level tests exercise individual subsystems in isolation.

### 1. Frame-Level Pixel Validation (`yuv_frame_validator.cpp`)

The C++ frame validator reads raw YUV420p data directly and computes:

- **Y-plane statistics** (mean, min, max, variance) - detects content anomalies
  such as blown-out highlights, crushed blacks, or encoding artefacts.
- **SHA-256 frame hash** - detects frozen frames (encoder stuck outputting the
  same reconstructed frame), which manifest in hardware as PLL lock failures or
  DMA stalls.
- **Black frame detection** (Y mean < 5) - identifies dropped output or
  display pipeline failures during bring-up.
- **Clipping detection** (Y max == 255 AND Y min == 0 simultaneously) - flags
  encoder tone-mapping or quantisation issues.

### 2. Bitstream Structural Analysis (`bitstream_analyzer.py`)

Uses `ffprobe` to parse encoded bitstreams without full decoding:

- **Frame type distribution** (I/P/B counts) - verifies that the encoder inserts
  keyframes at the configured GOP interval.
- **GOP length validation** - checks that no GOP exceeds the configured maximum,
  which would violate random access guarantees in adaptive streaming.
- **PTS continuity** - confirms monotonically increasing presentation timestamps;
  PTS discontinuities indicate mux errors or encoder timing bugs.
- **Per-window bitrate** - rolling bitrate measurement detects rate-control
  instability (spikes, sustained underflows).

---

## System-Level Validation

System-level tests run a complete encode -> decode -> metrics pipeline.

### 1. Encode Correctness

- Verifies that the encoder exits cleanly (return code 0).
- Confirms the output file is created and non-empty.
- Checks encode time is within expected bounds for the given preset.

### 2. Decode Integrity (`bitstream_decoder.py`)

- Decodes the encoded bitstream back to raw YUV using `ffmpeg`.
- Counts decoded frames with `ffprobe` packet counting.
- Runs `ffprobe -err_detect explode` to surface any bitstream errors that a
  hardware decoder would reject.

### 3. Perceptual Quality Metrics (`quality_evaluator.py`)

Full-reference metrics compare the decoded output against the original:

| Metric | Tool       | Use Case                                |
|--------|------------|-----------------------------------------|
| PSNR   | FFmpeg     | Low-level fidelity; fast; scale-aware   |
| SSIM   | FFmpeg     | Structural similarity; perceptual proxy |
| VMAF   | libvmaf    | Netflix perceptual model; Netflix standard |

PSNR thresholds are validated against known-good encode parameters.
VMAF requires FFmpeg compiled with `--enable-libvmaf`.

### 4. Rate-Distortion Analysis (`rd_curve_analyzer.py`)

- Sweeps across a range of CRF values to generate an RD curve.
- Computes bits-per-pixel (BPP) normalised for resolution and frame count.
- Computes BD-rate to compare two codecs over their overlapping quality range.
- Generates plots for visual inspection and documentation.

---

## Validation Thresholds

Pass/fail thresholds are stored in `config/validation_thresholds.yaml` and
applied automatically in `run_validation_pipeline.sh`.  Each scenario defines:

- `min_psnr_y` / `max_psnr_y` - dB bounds on luma PSNR.
- `min_vmaf` - minimum acceptable VMAF score.
- `max_encode_time_s` - wall-clock encode budget.
- `max_file_size_mb` - bitstream size guard.

Threshold tuning follows the principle of testing at known-good operating points
first (CRF 18-23) to establish a quality ceiling, then progressively degrading
quality to find the minimum acceptable operating point.
