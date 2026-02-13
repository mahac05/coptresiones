# tests/test_validators.py
# -*- coding: utf-8 -*-
"""Тесты для core/validators.py."""

import os
import tempfile
import pytest
from core.validators import validate_input_file, validate_output_format, build_output_path


class TestValidateInputFile:
    """Тесты для validate_input_file."""

    def test_empty_path(self):
        valid, msg = validate_input_file("")
        assert valid is False
        assert "не указан" in msg

    def test_whitespace_path(self):
        valid, msg = validate_input_file("   ")
        assert valid is False
        assert "не указан" in msg

    def test_nonexistent_path(self):
        valid, msg = validate_input_file("/nonexistent/path/video.mp4")
        assert valid is False
        assert "не найден" in msg

    def test_directory_path(self, tmp_path):
        valid, msg = validate_input_file(str(tmp_path))
        assert valid is False
        assert "не является файлом" in msg

    def test_valid_file(self, tmp_path):
        f = tmp_path / "test.mp4"
        f.write_text("fake video data")
        valid, msg = validate_input_file(str(f))
        assert valid is True
        assert msg == ""


class TestValidateOutputFormat:
    """Тесты для validate_output_format."""

    def test_empty_format(self):
        valid, msg = validate_output_format("")
        assert valid is False
        assert "не указан" in msg

    def test_invalid_format(self):
        valid, msg = validate_output_format("xyz")
        assert valid is False
        assert "Неподдерживаемый" in msg

    def test_valid_formats(self):
        for fmt in ["m4a", "mp3", "wav", "flac", "ogg", "aac"]:
            valid, msg = validate_output_format(fmt)
            assert valid is True, f"Expected {fmt} to be valid"
            assert msg == ""


class TestBuildOutputPath:
    """Тесты для build_output_path."""

    def test_same_folder(self):
        result = build_output_path(
            input_file="/videos/my_video.mp4",
            output_folder="",
            extension="m4a",
        )
        assert result == os.path.join("/videos", "my_video.m4a")

    def test_custom_folder(self):
        result = build_output_path(
            input_file="/videos/my_video.mp4",
            output_folder="/output",
            extension="mp3",
        )
        assert result == os.path.join("/output", "my_video.mp3")

    def test_with_suffix(self):
        result = build_output_path(
            input_file="/videos/clip.mp4",
            output_folder="",
            extension="mp4",
            suffix="_сжатое",
        )
        assert result == os.path.join("/videos", "clip_сжатое.mp4")
