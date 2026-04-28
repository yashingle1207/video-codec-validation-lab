# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: experiment_log.md
# Purpose: Track validation runs, observations, anomalies, and follow-up actions.

# Experiment Log

Record of validation runs, observations, and anomalies.

---

## Template Entry

```
### YYYY-MM-DD - <Experiment Title>

**Input:** <YUV file, resolution, fps, frame count>
**Codec / Config:** <codec, preset, CRF or bitrate, GOP>
**Machine:** <CPU, OS, FFmpeg version>

| CRF | BPP    | PSNR_Y (dB) | VMAF  | Encode Time (s) |
|-----|--------|-------------|-------|-----------------|
|     |        |             |       |                 |

**Observations:**
- ...

**Issues / Anomalies:**
- ...

**Next Steps:**
- ...
```

---

## 2026-04-28 - Initial H.264 CRF Sweep (352x288, testsrc2)

**Input:** `test_352x288_30fps_150f.yuv`, 352x288, 30 fps, 150 frames
**Codec / Config:** libx264, preset medium, CRF 18-45, GOP 30
**Machine:** Populated after first run

| CRF | BPP    | PSNR_Y (dB) | VMAF  | Encode Time (s) |
|-----|--------|-------------|-------|-----------------|
| 18  | TBD    | TBD         | TBD   | TBD             |
| 23  | TBD    | TBD         | TBD   | TBD             |
| 28  | TBD    | TBD         | TBD   | TBD             |
| 33  | TBD    | TBD         | TBD   | TBD             |
| 38  | TBD    | TBD         | TBD   | TBD             |
| 45  | TBD    | TBD         | TBD   | TBD             |

**Observations:**
- Placeholder - run `scripts/run_validation_pipeline.sh` to populate.

---

## 2026-04-28 - Initial HEVC CRF Sweep (352x288, testsrc2)

**Input:** `test_352x288_30fps_150f.yuv`, 352x288, 30 fps, 150 frames
**Codec / Config:** libx265, preset medium, CRF 20-42, GOP 30

| CRF | BPP    | PSNR_Y (dB) | VMAF  | Encode Time (s) |
|-----|--------|-------------|-------|-----------------|
| 20  | TBD    | TBD         | TBD   | TBD             |
| 24  | TBD    | TBD         | TBD   | TBD             |
| 28  | TBD    | TBD         | TBD   | TBD             |
| 32  | TBD    | TBD         | TBD   | TBD             |
| 36  | TBD    | TBD         | TBD   | TBD             |
| 42  | TBD    | TBD         | TBD   | TBD             |

**Observations:**
- Placeholder - run `scripts/run_validation_pipeline.sh` to populate.
