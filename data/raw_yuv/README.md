# Author: Yash Daniel Ingle
# Email: yashingle1207@gmail.com
# GitHub: github.com/yashingle1207
# Project: Video Codec Validation Lab
# File: README.md
# Purpose: Explain generated raw YUV fixture naming and regeneration steps.

# Raw YUV Test Sequences

This directory holds raw YUV420p sequences used as encoder inputs.
**No files are committed to the repository** - all clips are generated locally
by `scripts/generate_synthetic_clips.sh` using FFmpeg lavfi synthetic sources.

## File Naming Convention

```
<source>_<WxH>_<fps>fps_<frames>f.yuv
```

Examples:
- `test_352x288_30fps_150f.yuv` - testsrc2 pattern, 352x288, 30 fps, 150 frames
- `test_1280x720_30fps_150f.yuv` - testsrc2 pattern, 1280x720, 30 fps, 150 frames
- `test_1920x1080_30fps_100f.yuv` - mandelbrot, 1920x1080, 30 fps, 100 frames
- `black_352x288_30fps_60f.yuv` - solid black, for black-frame detection tests

## Quick Generation

```bash
bash scripts/generate_synthetic_clips.sh
```

All clips are YUV420p (4:2:0, 8-bit, planar).
