# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: experiment_log.md
# Purpose: Track completed validation runs without committing generated media or fake results.

# Experiment Log

This file is intentionally kept as a lightweight experiment journal.

Generated media, metrics, and reports are not committed to the repository. Actual
run outputs are written by the pipeline under `outputs/`, which is ignored by git
except for `.gitkeep` placeholders.

## Current Status

No measured experiment results are checked into this repo.

The validation code, configs, tests, and report schema are included. Actual codec
numbers such as BPP, PSNR, SSIM, VMAF, encode time, and pass/fail status should be
recorded here only after running the pipeline on a specific machine and toolchain.

## Entry Template

```text
### YYYY-MM-DD - <Experiment Title>

Input:
- Clip:
- Resolution:
- FPS:
- Frame count:

Codec configuration:
- Codec:
- Mode:
- CRF or bitrate:
- GOP:
- Preset:

Environment:
- CPU:
- OS:
- FFmpeg version:
- libvmaf available: yes/no

Results:
| Codec | Mode | CRF/Bitrate | BPP | PSNR-Y (dB) | SSIM | VMAF | Encode Time (s) | Pass |
|---|---|---:|---:|---:|---:|---:|---:|---|

Observations:
- 

Failures / anomalies:
- 

Follow-up:
- 
```
