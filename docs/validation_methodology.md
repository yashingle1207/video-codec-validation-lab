# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: validation_methodology.md
# Purpose: Document the validation workflow implemented in this project.

# Validation Methodology

This document describes the validation approach implemented by the project. It is
methodology documentation, not a claim that specific codec experiments have already
been measured.

## Validation Levels

The project separates validation into two layers:

- Block-level checks for individual components such as raw frame validation and
  bitstream parsing.
- System-level checks for the full encode, decode, quality, and reporting flow.

## Block-Level Validation

### Raw YUV Frame Validation

Implemented in:

```text
src/yuv_frame_validator.cpp
```

The C++ validator checks raw YUV420p frame data directly.

Implemented checks:

- Expected frame-size calculation for YUV420p.
- Short-read detection for truncated input.
- Y-plane mean, min, max, and variance.
- U/V chroma mean.
- SHA-256 fingerprint per frame.
- Black-frame detection.
- Frozen-frame detection using repeated hashes.
- Clipped-frame detection using luma min/max range.

### Bitstream Structure Validation

Implemented in:

```text
src/bitstream_analyzer.py
```

The analyzer uses ffprobe JSON output to inspect encoded video streams.

Implemented checks and extracted fields:

- Codec name.
- Profile.
- Pixel format.
- Resolution.
- Duration.
- Bitrate.
- Frame count.
- Frame type distribution.
- GOP structure.
- PTS continuity.
- Rolling bitrate behavior.

## System-Level Validation

The pipeline connects the individual validators into an end-to-end flow.

Implemented stages:

1. Load codec sweep configuration.
2. Encode raw YUV input with FFmpeg.
3. Decode encoded output back to YUV.
4. Verify decoded frame count.
5. Run ffprobe bitstream integrity checks.
6. Extract stream metadata and GOP information.
7. Compute PSNR, SSIM, and optional VMAF.
8. Compute BPP for rate-distortion analysis.
9. Apply YAML-defined thresholds.
10. Write JSON/CSV validation reports.

## Threshold Validation

Thresholds are configured in:

```text
config/validation_thresholds.yaml
```

The utility layer supports threshold keys such as:

```text
min_psnr_y
max_psnr_y
min_vmaf
max_vmaf
max_encode_time_s
max_file_size_mb
```

Each failed rule produces a human-readable failure reason for the report.

## Report Output

The pipeline writes report rows containing:

- Codec and mode.
- CRF or bitrate setting.
- BPP.
- PSNR-Y.
- SSIM.
- VMAF when available.
- Encode time.
- Bitrate and duration.
- Profile and pixel format.
- GOP summary.
- Decode status.
- Frame-count status.
- Threshold key.
- Pass/fail result.
- Failure reason.

Generated reports are written under `outputs/reports/` and are intentionally
ignored by git so the repository stays lightweight.
