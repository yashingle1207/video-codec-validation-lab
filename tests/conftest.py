"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    conftest.py
Purpose: Session-scoped pytest fixtures that generate synthetic YUV420p test clips
         via FFmpeg lavfi so no external video data is required.

Description:
    Provides two session-scoped YUV clip fixtures shared across all test modules:
    synthetic_yuv (testsrc2 colourful pattern) and black_yuv (solid black, used
    for anomaly detection tests).  Clips are generated once per pytest session
    into a temporary directory and reused, keeping test runs fast.
"""

import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Clip constants - used in every test module
# ---------------------------------------------------------------------------

# Resolution: 352x288 (CIF) - small enough for fast CI, large enough for metrics.
WIDTH  = 352
HEIGHT = 288
FPS    = 30.0
# 60 frames = 2 seconds at 30 fps - enough for GOP and quality tests.
FRAMES = 60

# YUV420p frame size in bytes: W*H (luma) + W*H/4 (Cb) + W*H/4 (Cr) = 1.5 x W x H
FRAME_BYTES = WIDTH * HEIGHT * 3 // 2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tmp_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return a session-scoped temporary directory shared by all tests.

    Returns:
        :class:`pathlib.Path` to the temporary directory.
    """
    return tmp_path_factory.mktemp("vel_test")


@pytest.fixture(scope="session")
def synthetic_yuv(tmp_dir: Path) -> Path:
    """Generate a testsrc2 YUV420p clip for the entire test session.

    ``testsrc2`` is a colourful synthetic test pattern with colour bars and
    moving elements - useful for verifying encoder activity and quality metrics.

    Returns:
        :class:`pathlib.Path` to the generated ``.yuv`` file.

    Skips:
        If FFmpeg is not available or lavfi support is missing.
    """
    yuv_path = tmp_dir / f"test_{WIDTH}x{HEIGHT}_{FRAMES}f.yuv"
    if yuv_path.is_file() and yuv_path.stat().st_size > 0:
        return yuv_path  # already generated in a previous test module

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        # testsrc2 generates a synthetic colour test pattern.
        "-i", f"testsrc2=size={WIDTH}x{HEIGHT}:rate={int(FPS)}",
        "-frames:v", str(FRAMES),
        "-pix_fmt", "yuv420p",  # 4:2:0 planar 8-bit - standard YUV format
        "-f", "rawvideo",
        str(yuv_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not yuv_path.is_file():
        pytest.skip(
            f"FFmpeg lavfi unavailable or failed; skipping this test. "
            f"stderr: {result.stderr[-400:]}"
        )
    return yuv_path


@pytest.fixture(scope="session")
def black_yuv(tmp_dir: Path) -> Path:
    """Generate a solid-black YUV420p clip for black-frame and frozen-frame tests.

    Every frame in this clip has Y=16 (black in studio-swing YUV), U=128, V=128.
    Used to verify that the yuv_frame_validator correctly detects black_frame
    and frozen_frame flags.

    Returns:
        :class:`pathlib.Path` to the generated ``.yuv`` file.

    Skips:
        If FFmpeg is not available.
    """
    yuv_path = tmp_dir / f"black_{WIDTH}x{HEIGHT}_{FRAMES}f.yuv"
    if yuv_path.is_file() and yuv_path.stat().st_size > 0:
        return yuv_path

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        # color=c=black generates a fully black frame sequence.
        "-i", f"color=c=black:size={WIDTH}x{HEIGHT}:rate={int(FPS)}",
        "-frames:v", str(FRAMES),
        "-pix_fmt", "yuv420p",
        "-f", "rawvideo",
        str(yuv_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not yuv_path.is_file():
        pytest.skip(
            f"FFmpeg lavfi unavailable; skipping black-clip tests. "
            f"stderr: {result.stderr[-400:]}"
        )
    return yuv_path
