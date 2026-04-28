
# Video Codec Validation Lab

**Author:** Yash Daniel Ingle  
**Email:** yashingle1207@gmail.com  
**GitHub:** github.com/yashingle1207  
**Project:** Video Codec Validation Lab

## Overview

Video Codec Validation Lab is a C++/Python project for validating video codec behavior across **H.264/AVC, HEVC/H.265, VP9, and AV1**.

The project models a practical video compression validation workflow: generating deterministic YUV inputs, encoding them with multiple codec settings, verifying decoded output, inspecting bitstream metadata, measuring objective quality, applying regression thresholds, and producing machine-readable validation reports.

This project was built to demonstrate software validation skills relevant to video compression subsystems: correctness checking, metadata inspection, quality measurement, failure reporting, and repeatable regression testing.

## Validation Focus

This project covers both block-level and system-level validation concepts.

Block-level validation:

- Raw YUV420p frame validation in C++.
- Frame count and frame-size checks.
- Truncation detection for malformed raw YUV input.
- Per-frame luma/chroma statistics.
- SHA-256 frame fingerprints.
- Black-frame, frozen-frame, and clipping detection.

System-level validation:

- Codec encoding using FFmpeg.
- Decode verification of encoded outputs.
- ffprobe-based bitstream metadata analysis.
- GOP and frame-type inspection.
- PSNR, SSIM, and optional VMAF quality evaluation.
- YAML-defined pass/fail thresholds.
- JSON/CSV regression reports.

## Architecture

```text
RAW YUV
  -> Codec Encoder
  -> Encoded Bitstream
  -> Decode Verifier
  -> Bitstream Analyzer
  -> Quality Evaluator
  -> Validation Rules
  -> RD Analyzer
  -> Report
```

## Core Modules

```text
codec_encoder.py         FFmpeg CRF/CBR encode wrapper
bitstream_decoder.py     Decode verification and ffprobe integrity checks
bitstream_analyzer.py    ffprobe metadata, frame type, GOP, PTS, and bitrate analysis
quality_evaluator.py     PSNR, SSIM, and VMAF metric evaluation
rd_curve_analyzer.py     BPP, RD plots, and BD-rate calculations
pipeline_utils.py        Config loading, directory setup, logging, and pass/fail rules
yuv_frame_validator.cpp  C++ YUV420p frame statistics and SHA-256 validator
```

## What I Built

- A Python validation pipeline for codec experiments across H.264/AVC, HEVC/H.265, VP9, and AV1.
- A C++ YUV420p frame validator for low-level raw frame inspection.
- FFmpeg-based encoding workflows for CRF and CBR codec settings.
- ffprobe-based bitstream inspection for codec, profile, pixel format, resolution, bitrate, duration, frame count, keyframes, and GOP behavior.
- Decode verification logic for checking encoded output correctness.
- Objective quality evaluation using PSNR, SSIM, and optional VMAF.
- Rate-distortion utilities for BPP, RD curves, and BD-rate analysis.
- YAML configuration files for codec sweeps and validation thresholds.
- JSON/CSV report generation for regression tracking.
- Lightweight pytest coverage using mocked FFmpeg/ffprobe calls for fast validation of command construction, parsing logic, threshold handling, and failure cases.

## C++ YUV Frame Validator

The C++ validator reads raw YUV420p frames directly and validates frame-level behavior.

Implemented checks include:

- Expected YUV420p frame-size calculation.
- Short-read detection for truncated input.
- Per-frame Y-plane mean, min, max, and variance.
- U/V chroma mean calculation.
- SHA-256 hash generation for each frame.
- Frozen-frame detection using repeated hashes.
- Black-frame detection using luma statistics.
- Clipped-frame detection using luma min/max range.


## Bitstream Analysis

The bitstream analyzer uses ffprobe JSON output to inspect encoded streams without manually parsing codec syntax.

It extracts and validates:

- Codec name.
- Profile.
- Pixel format.
- Width and height.
- Duration.
- Bitrate.
- Frame count.
- Frame types.
- GOP structure.
- PTS continuity.
- Rolling bitrate behavior.

This supports validation of encoded stream structure, random-access behavior, and rate-control stability.

## Quality Evaluation

The quality evaluator compares encoded output against the original raw YUV input.

Supported metrics:

- PSNR.
- SSIM.
- VMAF when FFmpeg is built with libvmaf.

The pipeline records quality metrics per encode configuration and uses them for regression checks against validation thresholds.

## Validation Rules

Validation thresholds are stored in:

```text
config/validation_thresholds.yaml
```

The pipeline applies pass/fail checks for:

- Encode success.
- Decode success.
- Frame-count consistency.
- Bitstream integrity.
- Metadata sanity.
- PSNR thresholds.
- SSIM sanity.
- VMAF thresholds when available.
- Encode-time limits.
- File-size and bitrate sanity.

Each validation result includes a pass/fail field and a failure reason for debugging regressions.

## Reports

The pipeline writes machine-readable validation reports under:

```text
outputs/reports/
```

Report fields include:

```text
codec
mode
CRF or bitrate
BPP
PSNR-Y
SSIM
VMAF
encode time
bitrate
duration
profile
pixel format
GOP count
decode status
frame-count status
threshold key
pass/fail result
failure reason
```

## Project Structure

```text
video-codec-validation-lab/
|-- .gitignore
|-- Makefile
|-- README.md
|-- requirements.txt
|-- src/
|   |-- codec_encoder.py
|   |-- bitstream_decoder.py
|   |-- quality_evaluator.py
|   |-- yuv_frame_validator.cpp
|   |-- bitstream_analyzer.py
|   |-- rd_curve_analyzer.py
|   `-- pipeline_utils.py
|-- tests/
|   |-- test_codec_encoder.py
|   |-- test_bitstream_decoder.py
|   |-- test_quality_evaluator.py
|   |-- test_yuv_frame_validator.py
|   |-- test_bitstream_analyzer.py
|   `-- test_pipeline_utils.py
|-- config/
|   |-- h264_avc_crf_sweep.yaml
|   |-- h265_hevc_crf_sweep.yaml
|   |-- h265_hevc_cbr_ladder.yaml
|   |-- av1_libaom_crf_sweep.yaml
|   `-- validation_thresholds.yaml
|-- scripts/
|   |-- generate_synthetic_clips.sh
|   |-- run_validation_pipeline.sh
|   `-- yuv_sequence_scaler.py
|-- docs/
|   |-- codec_notes.md
|   |-- validation_methodology.md
|   |-- metrics_reference.md
|   `-- experiment_log.md
|-- data/
|   `-- raw_yuv/
`-- outputs/
    |-- encoded/
    |-- decoded/
    |-- metrics/
    |-- plots/
    `-- reports/
```

## Codec Coverage

**H.264/AVC**  
Used as the compatibility baseline for codec validation and quality comparison.

**HEVC/H.265**  
Used to evaluate higher compression efficiency and more complex encoder behavior.

**AV1**  
Used to validate modern open video compression behavior with stronger rate-distortion tradeoffs.

**VP9**  
Supported by the encoder wrapper for additional web-video codec coverage.

## Testing

The test suite focuses on validation logic rather than large media assets.

Covered areas include:

- Encoder command construction.
- Decode verifier success and failure behavior.
- ffprobe JSON parsing.
- Bitstream metadata extraction.
- GOP/frame-type parsing.
- PSNR/SSIM/VMAF parsing.
- BPP calculation.
- YAML config loading.
- Pass/fail threshold evaluation.
- C++ validator source/build contract.


## Limitations

- This project uses FFmpeg software encoders rather than hardware codec IP.
- VMAF availability depends on the local FFmpeg build.
- Larger natural-content clips would improve real-world coverage.
- Hardware simulator, FPGA, emulation, and silicon bring-up hooks are outside the current scope.

