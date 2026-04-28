"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    test_codec_encoder.py
Purpose: Unit tests for codec_encoder.py command construction and result handling.

Description:
    Tests mock subprocess execution so the encoder wrapper can be validated
    without requiring FFmpeg or large media files. Coverage focuses on codec
    validation, CRF/CBR command flags, output directory creation, and result
    dataclass fields.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.codec_encoder import CodecEncoder, EncodeResult


class _Completed:
    """Small stand-in for subprocess.CompletedProcess used by encoder tests."""

    returncode = 0
    stderr = "ok"


def _fake_run_creates_output(cmd, capture_output=True, text=True, timeout=None):
    """Create the requested output file and return a successful process object.

    Args:
        cmd: FFmpeg command argument list.
        capture_output: Ignored compatibility argument.
        text: Ignored compatibility argument.
        timeout: Ignored compatibility argument.

    Returns:
        _Completed: Successful fake process result.
    """
    out = Path(cmd[-1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(b"encoded")
    return _Completed()


class TestCodecEncoderCommands:
    """Command construction and validation tests for CodecEncoder."""

    def test_h264_crf_command_contains_expected_flags(self, tmp_path):
        """H.264 CRF should include raw YUV input flags, preset, CRF, and GOP."""
        encoder = CodecEncoder()
        out = tmp_path / "encoded" / "h264.mp4"
        with patch("src.codec_encoder.subprocess.run", side_effect=_fake_run_creates_output) as run:
            result = encoder.encode_crf(
                input_yuv=tmp_path / "in.yuv",
                codec="libx264",
                crf=23,
                gop=30,
                preset="fast",
                width=352,
                height=288,
                fps=30,
                output_path=out,
            )

        cmd = run.call_args.args[0]
        assert ["-f", "rawvideo"] == cmd[1:3]
        assert "-pix_fmt" in cmd and "yuv420p" in cmd
        assert "-c:v" in cmd and "libx264" in cmd
        assert "-crf" in cmd and "23" in cmd
        assert "-g" in cmd and "30" in cmd
        assert isinstance(result, EncodeResult)
        assert result.file_size_bytes == len(b"encoded")

    def test_h264_cbr_command_contains_rate_control_flags(self, tmp_path):
        """H.264 CBR should include target bitrate, maxrate, and buffer size."""
        encoder = CodecEncoder()
        out = tmp_path / "h264_cbr.mp4"
        with patch("src.codec_encoder.subprocess.run", side_effect=_fake_run_creates_output) as run:
            result = encoder.encode_cbr(
                input_yuv=tmp_path / "in.yuv",
                codec="libx264",
                bitrate_kbps=500,
                gop=60,
                width=352,
                height=288,
                fps=30,
                output_path=out,
                preset="ultrafast",
            )

        cmd = run.call_args.args[0]
        assert "-b:v" in cmd and "500k" in cmd
        assert "-maxrate" in cmd and "750k" in cmd
        assert "-bufsize" in cmd and "1000k" in cmd
        assert result.mode == "cbr"
        assert result.crf_or_bitrate == 500

    def test_unsupported_codec_raises_value_error(self, tmp_path):
        """Unknown codec names should fail before subprocess execution."""
        encoder = CodecEncoder()
        with pytest.raises(ValueError, match="Unsupported codec"):
            encoder.encode_crf(
                input_yuv=tmp_path / "in.yuv",
                codec="libnotreal",
                crf=23,
                gop=30,
                preset="medium",
                width=352,
                height=288,
                fps=30,
                output_path=tmp_path / "out.mp4",
            )
