"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    test_bitstream_decoder.py
Purpose: Unit tests for FFmpeg decode verification and ffprobe integrity checks.

Description:
    These tests mock subprocess calls and filesystem side effects to validate
    DecodeVerifier success and failure behavior without requiring FFmpeg or
    encoded media files.
"""

from unittest.mock import patch

from src.bitstream_decoder import DecodeVerifier


class _Completed:
    """Fake subprocess result for decode and probe tests."""

    def __init__(self, returncode=0, stdout="{}", stderr=""):
        """Store subprocess-like fields.

        Args:
            returncode: Process exit code.
            stdout: Captured stdout text.
            stderr: Captured stderr text.
        """
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_decode_to_yuv_success_creates_output(tmp_path):
    """decode_to_yuv should return True when FFmpeg succeeds and output exists."""
    verifier = DecodeVerifier()
    encoded = tmp_path / "in.mp4"
    encoded.write_bytes(b"video")
    decoded = tmp_path / "decoded" / "out.yuv"

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        """Write a fake decoded file and return success.

        Args:
            cmd: FFmpeg command argument list.
            capture_output: Ignored compatibility argument.
            text: Ignored compatibility argument.
            timeout: Ignored compatibility argument.

        Returns:
            _Completed: Successful fake process result.
        """
        decoded.write_bytes(b"raw")
        return _Completed()

    with patch("src.bitstream_decoder.subprocess.run", side_effect=fake_run):
        assert verifier.decode_to_yuv(encoded, decoded, 352, 288, 30.0) is True


def test_verify_frame_count_success(tmp_path):
    """verify_frame_count should parse nb_read_packets and compare it."""
    verifier = DecodeVerifier()
    encoded = tmp_path / "in.mp4"
    encoded.write_bytes(b"video")
    stdout = '{"streams": [{"nb_read_packets": "60"}]}'

    with patch("src.bitstream_decoder.subprocess.run", return_value=_Completed(stdout=stdout)):
        assert verifier.verify_frame_count(encoded, 60) is True


def test_check_bitstream_integrity_reports_missing_file(tmp_path):
    """Missing encoded files should produce a failed IntegrityReport."""
    verifier = DecodeVerifier()
    report = verifier.check_bitstream_integrity(tmp_path / "missing.mp4")
    assert report.passed is False
    assert "File not found" in report.errors[0]
