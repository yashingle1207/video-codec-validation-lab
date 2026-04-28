"""
Author:  Yash Daniel Ingle
Email:   yashingle1207@gmail.com
GitHub:  github.com/yashingle1207
Project: Video Codec Validation Lab
File:    test_yuv_frame_validator.py
Purpose: Lightweight tests for the C++ YUV validator source and build contract.

Description:
    Tests inspect the validator source and Makefile path expectations so the
    suite remains portable even when a compiled binary is not available.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cpp_validator_source_exists():
    """The C++ YUV validator source should exist at the professional path."""
    assert (ROOT / "src" / "yuv_frame_validator.cpp").is_file()


def test_makefile_builds_expected_validator_source():
    """Makefile should reference yuv_frame_validator.cpp and build/ output."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "src/yuv_frame_validator.cpp" in text
    assert "build/yuv_frame_validator" in text


def test_cpp_source_documents_yuv420_frame_size_and_sha256():
    """Source should explain YUV420p frame-size math and SHA-256 validation."""
    text = (ROOT / "src" / "yuv_frame_validator.cpp").read_text(encoding="utf-8")
    assert "YUV420p" in text
    assert "1.5 bytes per pixel" in text
    assert "SHA-256" in text
    assert "short read" in text
