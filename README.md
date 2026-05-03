# Video Codec Validation Lab

Yash Daniel Ingle | yashingle1207@gmail.com | github.com/yashingle1207 | LinkedIn

## Overview

C++/Python video codec validation lab for H.264/AVC, HEVC, and AV1 with FFmpeg, ffprobe, bitstream analysis, PSNR/SSIM metrics, YUV validation, and regression reports.

This project uses FFmpeg and ffprobe to encode raw YUV inputs, verify decoded output, inspect bitstream metadata, compute objective quality metrics, apply pass/fail thresholds, and write machine-readable reports.

The project is designed as a lightweight portfolio system for video compression and silicon validation software roles. It focuses on repeatable validation, clear failure reasons, and clean engineering structure rather than checked-in media assets.

## Why This Project

Video encoder validation is more than checking whether a file plays. A practical validation flow needs to confirm functional correctness, bitstream structure, frame-count consistency, decode integrity, objective quality, rate-control behavior, and regression thresholds.

This project demonstrates those concepts with:

- C++ raw YUV420p frame validation.
- Python automation for encode, decode, metrics, and reporting.
- FFmpeg/ffprobe command construction and JSON parsing.
- H.264/AVC, HEVC/H.265, and AV1 codec coverage.
- PSNR, SSIM, and optional VMAF quality measurement.
- Rate-distortion and BD-rate analysis support.

## Architecture

```text
RAW YUV -> Encoder -> Bitstream -> Decoder/Verifier -> Bitstream Analyzer -> Quality Evaluator -> Validation Rules -> RD Analyzer -> Report
```

Core modules:

```text
codec_encoder.py         FFmpeg CRF/CBR encode wrapper
bitstream_decoder.py     Decode verification and ffprobe integrity checks
bitstream_analyzer.py    ffprobe metadata, frame type, GOP, PTS, and bitrate analysis
quality_evaluator.py     PSNR, SSIM, and VMAF metric evaluation
rd_curve_analyzer.py     BPP, RD plots, and BD-rate calculations
pipeline_utils.py        Config loading, logging, directories, and pass/fail rules
yuv_frame_validator.cpp  C++ YUV420p frame statistics and SHA-256 validator
```

## Features

- H.264/AVC, HEVC/H.265, VP9, and AV1 encoder wrapper support.
- CRF and CBR workflows, including two-pass CBR for VP9/AV1.
- Synthetic FFmpeg lavfi clips so large media files are not committed.
- C++ YUV420p validator for frame statistics, SHA-256 fingerprints, black frames, frozen frames, clipping, and truncation.
- ffprobe metadata extraction for codec, profile, pixel format, resolution, duration, bitrate, frame count, keyframes, and GOP behavior.
- PSNR, SSIM, and VMAF quality metrics. VMAF is optional and depends on FFmpeg being built with libvmaf.
- YAML pass/fail thresholds and JSON/CSV report output.
- Validation plots for RD curves, CRF/quality trends, encode time, file size, pass/fail summary, and BD-rate style comparison.
- Lightweight pytest suite with mocked FFmpeg/ffprobe calls for CI-friendly regression testing.

## Requirements

Python packages are listed in `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

External tools:

- `ffmpeg` and `ffprobe` must be installed and available on `PATH`.
- `g++` is required to build the C++ YUV validator.
- `make` is convenient but may require MinGW/MSYS2/Git Bash on Windows.
- On Windows, use Git Bash/MSYS2/WSL for `.sh` scripts, or run the Python modules directly.

## Quick Start

```bash
git clone <YOUR_GITHUB_REPO_URL>
cd video-codec-validation-lab
python -m pip install -r requirements.txt
make build
make generate
make run
```

If `make` is unavailable on Windows, build directly:

```bash
g++ -std=c++14 -O2 -Wall -Wextra -o build/yuv_frame_validator.exe src/yuv_frame_validator.cpp
```

## Project Structure

```text
video-codec-validation-lab/
|-- .gitignore
|-- Makefile
|-- README.md
|-- requirements.txt
|-- src/
|   |-- __init__.py
|   |-- codec_encoder.py
|   |-- bitstream_decoder.py
|   |-- quality_evaluator.py
|   |-- yuv_frame_validator.cpp
|   |-- bitstream_analyzer.py
|   |-- rd_curve_analyzer.py
|   `-- pipeline_utils.py
|-- tests/
|   |-- __init__.py
|   |-- conftest.py
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
|   |-- experiment_log.md
|   `-- images/
|       `-- .gitkeep
|-- data/
|   `-- raw_yuv/
|       `-- README.md
`-- outputs/
    |-- encoded/.gitkeep
    |-- decoded/.gitkeep
    |-- metrics/.gitkeep
    |-- plots/.gitkeep
    `-- reports/.gitkeep
```


## Generated Test Clips

The pipeline uses deterministic FFmpeg lavfi sources so the repository stays lightweight while still exercising meaningful validation cases:

```text
test_352x288_30fps_150f.yuv       smoke-test codec sweep input
test_1280x720_30fps_150f.yuv      practical HD comparison input
test_1920x1080_30fps_100f.yuv     high-detail stress input
black_352x288_30fps_60f.yuv       black/frozen-frame corner case
white_352x288_30fps_60f.yuv       clipping/saturation corner case
```

## Running the Validation Pipeline

Generate deterministic synthetic clips:

```bash
bash scripts/generate_synthetic_clips.sh
```

Run the full validation flow:

```bash
bash scripts/run_validation_pipeline.sh
```

The pipeline writes encoded bitstreams, decoded YUV files, metric logs, reports, and plots under `outputs/`. Generated media and reports are ignored by git except for `.gitkeep` placeholders; small README-ready PNGs can be copied into `docs/images/`.

## Running Tests

```bash
python -m pytest -v
```

The unit tests are intentionally lightweight. They mock FFmpeg and ffprobe subprocess calls where possible, so the core parsing and validation logic can be checked without large media files.


## Validation Plots

The plotting scripts turn `outputs/reports/validation_summary.csv` into visual evidence for review:

```text
rd_curve_psnr.png
crf_vs_psnr.png
crf_vs_bpp.png
encode_time_comparison.png
file_size_comparison.png
validation_pass_fail_summary.png
bd_rate_matrix_psnr.png
```

VMAF plots are generated only when the local FFmpeg build includes libvmaf. SSIM plots are generated when SSIM values are present in the report.

## Experiment Results

Values are generated after running the pipeline.

| Codec | Mode | CRF/Bitrate | BPP | PSNR-Y (dB) | SSIM | VMAF | Encode Time (s) | Pass/Fail |
|---|---|---:|---:|---:|---:|---:|---:|---|
| H.264/AVC | CRF | generated | generated | generated | generated | generated | generated | generated |
| HEVC/H.265 | CRF | generated | generated | generated | generated | generated | generated | generated |
| AV1/libaom | CRF | generated | generated | generated | generated | generated | generated | generated |

## Rate-Distortion and BD-Rate Analysis

Rate-distortion curves compare quality against bitrate or bits-per-pixel. A better encoder reaches the same PSNR, SSIM, or VMAF score at lower BPP.

BD-rate summarizes the average bitrate difference between two RD curves over their overlapping quality range. Negative BD-rate means the test codec is more efficient than the reference codec.

## Validation Methodology

The pass/fail rules live in `config/validation_thresholds.yaml`. The pipeline applies decode success, frame-count consistency, bitstream integrity, metadata sanity, quality thresholds, encode-time limits, and size/BPP sanity checks where configured.

Each report row includes codec settings, bitrate/BPP, PSNR-Y, SSIM, VMAF when available, decode status, threshold key, pass/fail state, and failure reasons.

## Codec Notes

H.264/AVC is the compatibility baseline and usually encodes quickly. HEVC/H.265 improves compression efficiency at higher complexity. AV1 targets stronger compression efficiency and royalty-free deployment, but software encoding can be slow and VMAF/quality validation becomes especially important.

## Limitations / Future Work

- Hardware encoder integration is not included; this project uses FFmpeg software encoders.
- VMAF depends on the local FFmpeg build including libvmaf.
- Larger natural-content clips would improve real-world codec coverage.
- CI integration can be added after choosing a target OS/toolchain.
- The CBR ladder config is present for future pipeline expansion.

## License

MIT License - Yash Daniel Ingle
