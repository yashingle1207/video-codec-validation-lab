
````markdown
# Video Codec Validation Lab

## Overview

C++/Python video codec validation lab for H.264/AVC, HEVC, and AV1 with FFmpeg, ffprobe, bitstream analysis, PSNR/SSIM metrics, YUV validation, and regression reports.

This project uses FFmpeg and ffprobe to encode raw YUV inputs, verify decoded output, inspect bitstream metadata, compute objective quality metrics, apply pass/fail thresholds, and write machine-readable reports.

The project is designed as a lightweight portfolio system for video compression and silicon validation software roles. It focuses on repeatable validation, clear failure reasons, codec behavior visibility, and clean engineering structure rather than checked-in large media assets.

## Why This Project

Video encoder validation is more than checking whether a file plays. A practical validation flow needs to confirm functional correctness, bitstream structure, frame-count consistency, decode integrity, objective quality, rate-control behavior, and regression thresholds.

This project demonstrates those concepts with:

- C++ raw YUV420p frame validation.
- Python automation for encode, decode, metrics, and reporting.
- FFmpeg/ffprobe command construction and JSON parsing.
- H.264/AVC, HEVC/H.265, and AV1 codec coverage.
- PSNR, SSIM, and optional VMAF quality measurement.
- Bitstream metadata inspection, GOP analysis, and bitrate sanity checks.
- Rate-distortion and BD-rate analysis support.

## Architecture

```text
RAW YUV
  -> Encoder
  -> Bitstream
  -> Decoder/Verifier
  -> Bitstream Analyzer
  -> Quality Evaluator
  -> Validation Rules
  -> RD Analyzer
  -> Report
````

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

* H.264/AVC, HEVC/H.265, VP9, and AV1 encoder wrapper support.
* CRF and CBR workflows, including two-pass CBR for VP9/AV1.
* Synthetic FFmpeg lavfi clips so large media files are not committed.
* C++ YUV420p validator for frame statistics, SHA-256 fingerprints, black frames, frozen frames, clipping, and truncation.
* ffprobe metadata extraction for codec, profile, pixel format, resolution, duration, bitrate, frame count, keyframes, and GOP behavior.
* PSNR, SSIM, and VMAF quality metrics. VMAF is optional and depends on FFmpeg being built with libvmaf.
* YAML pass/fail thresholds and JSON/CSV report output.
* Lightweight pytest suite with mocked FFmpeg/ffprobe calls for CI-friendly regression testing.

## Requirements

Python packages are listed in `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

External tools:

* `ffmpeg` and `ffprobe` must be installed and available on `PATH`.
* `g++` is required to build the C++ YUV validator.
* `make` is convenient but may require MinGW/MSYS2/Git Bash on Windows.
* On Windows, use Git Bash/MSYS2/WSL for `.sh` scripts, or run the Python modules directly.

## Quick Start

```bash
git clone https://github.com/yashingle1207/video-codec-validation-lab.git
cd video-codec-validation-lab
python -m pip install -r requirements.txt
make build
make generate
make run
```

If `make` is unavailable on Windows, build directly:

```bash
mkdir build
g++ -std=c++14 -O2 -Wall -Wextra -o build/yuv_frame_validator.exe src/yuv_frame_validator.cpp
```

Run tests:

```bash
python -m pytest -v
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

## Running the Validation Pipeline

Generate deterministic synthetic clips:

```bash
bash scripts/generate_synthetic_clips.sh
```

Run the full validation flow:

```bash
bash scripts/run_validation_pipeline.sh
```

The pipeline writes:

```text
outputs/encoded/    encoded bitstreams
outputs/decoded/    decoded YUV outputs
outputs/metrics/    PSNR/SSIM/VMAF logs
outputs/plots/      generated RD/quality plots
outputs/reports/    JSON and CSV validation reports
```

Generated outputs are ignored by git except for `.gitkeep` placeholders.

## Running Tests

```bash
python -m pytest -v
```

The unit tests are intentionally lightweight. They mock FFmpeg and ffprobe subprocess calls where possible, so the core parsing and validation logic can be checked without large media files.

## Results Preview

The validation pipeline generates JSON/CSV reports and plot-ready metrics under `outputs/`.

### Validation Summary

| Codec      | Mode | CRF/Bitrate |       BPP | PSNR-Y (dB) |      SSIM |      VMAF | Encode Time (s) | Pass/Fail |
| ---------- | ---- | ----------: | --------: | ----------: | --------: | --------: | --------------: | --------- |
| H.264/AVC  | CRF  |   generated | generated |   generated | generated | generated |       generated | generated |
| HEVC/H.265 | CRF  |   generated | generated |   generated | generated | generated |       generated | generated |
| AV1/libaom | CRF  |   generated | generated |   generated | generated | generated |       generated | generated |

Values are generated after running:

```bash
bash scripts/run_validation_pipeline.sh
```

## Generated Reports

The pipeline produces machine-readable reports such as:

```text
outputs/reports/validation_summary.json
outputs/reports/validation_summary.csv
outputs/reports/h264_crf_sweep_results.json
outputs/reports/hevc_crf_sweep_results.json
outputs/reports/av1_crf_sweep_results.json
```

Each report row includes:

```text
codec
mode
CRF or bitrate
BPP
PSNR-Y
SSIM
VMAF if available
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

## Visual Results

Generated plot images can be saved into `docs/images/` after running experiments. Suggested filenames:

```text
docs/images/rd_curve_vmaf.png
docs/images/psnr_comparison.png
docs/images/ssim_comparison.png
docs/images/bpp_comparison.png
docs/images/gop_frame_type_histogram.png
docs/images/validation_pass_fail_summary.png
```

Do not commit large generated media files. Only commit small documentation images if they help explain results.

## Rate-Distortion and BD-Rate Analysis

Rate-distortion curves compare quality against bitrate or bits-per-pixel. A better encoder reaches the same PSNR, SSIM, or VMAF score at lower BPP.

BD-rate summarizes the average bitrate difference between two RD curves over their overlapping quality range. Negative BD-rate means the test codec is more efficient than the reference codec.

This project includes RD support through:

```text
rd_curve_analyzer.py
```

It supports:

* BPP calculation.
* RD curve plotting.
* Multi-codec curve comparison.
* BD-rate calculation using polynomial integration.

## Validation Methodology

The pass/fail rules live in:

```text
config/validation_thresholds.yaml
```

The pipeline applies checks for:

* Encode success.
* Decode success.
* Frame-count consistency.
* Bitstream integrity.
* Metadata sanity.
* PSNR-Y minimum thresholds.
* SSIM sanity where available.
* VMAF thresholds when libvmaf is available.
* Encode-time limits.
* File-size or bitrate sanity.

Each report row includes a `pass` field and a `failure_reason` field so regressions are easy to diagnose.

## Codec Notes

H.264/AVC is the compatibility baseline and usually encodes quickly.

HEVC/H.265 improves compression efficiency at higher computational complexity.

AV1 targets stronger compression efficiency and royalty-free deployment, but software encoding can be slow and quality validation becomes especially important.

## Limitations / Future Work

* Hardware encoder integration is not included; this project uses FFmpeg software encoders.
* VMAF depends on the local FFmpeg build including libvmaf.
* Larger natural-content clips would improve real-world codec coverage.
* CI integration can be added after choosing a target OS/toolchain.
* The CBR ladder config is present for future pipeline expansion.
* Future versions can add automatically generated PNG plots from `validation_summary.csv`.


```
those PNG files are already present in `docs/images/`.
```
