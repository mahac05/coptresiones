# tests/test_models.py
# -*- coding: utf-8 -*-
"""Тесты для core/models.py."""

import pytest
from core.models import JobResult, ConversionRequest, CompressionRequest


class TestJobResult:
    """Тесты для JobResult."""

    def test_default_is_success(self):
        r = JobResult()
        assert r.ok is True
        assert r.status == "success"
        assert r.error_code == ""
        assert r.error_message == ""

    def test_success_factory(self):
        r = JobResult.success(output_file="/tmp/out.m4a", duration_ms=1234)
        assert r.ok is True
        assert r.output_file == "/tmp/out.m4a"
        assert r.duration_ms == 1234

    def test_error_factory(self):
        r = JobResult.error("ffmpeg_error", "exit code 1", duration_ms=500)
        assert r.ok is False
        assert r.status == "error"
        assert r.error_code == "ffmpeg_error"
        assert r.error_message == "exit code 1"
        assert r.duration_ms == 500

    def test_cancelled_factory(self):
        r = JobResult.cancelled(duration_ms=100)
        assert r.ok is False
        assert r.status == "cancelled"
        assert r.error_code == "cancelled"

    def test_timeout_factory(self):
        r = JobResult.timeout(duration_ms=60000)
        assert r.ok is False
        assert r.status == "timeout"
        assert r.error_code == "timeout"

    def test_ok_property_false_for_non_success(self):
        for status in ["error", "cancelled", "timeout"]:
            r = JobResult(status=status)
            assert r.ok is False


class TestConversionRequest:
    """Тесты для ConversionRequest."""

    def test_defaults(self):
        req = ConversionRequest(input_file="in.mp4", output_file="out.m4a")
        assert req.output_format == "m4a"
        assert req.bitrate == "192k"

    def test_custom_values(self):
        req = ConversionRequest(
            input_file="video.mp4",
            output_file="audio.mp3",
            output_format="mp3",
            bitrate="320k",
        )
        assert req.output_format == "mp3"
        assert req.bitrate == "320k"


class TestCompressionRequest:
    """Тесты для CompressionRequest."""

    def test_defaults(self):
        req = CompressionRequest(input_file="in.mp4", output_file="out.mp4")
        assert req.crf == 23
        assert req.preset == "medium"
        assert req.audio_bitrate == "128k"

    def test_custom_values(self):
        req = CompressionRequest(
            input_file="in.mp4",
            output_file="out.mp4",
            crf=18,
            preset="slow",
            audio_bitrate="192k",
        )
        assert req.crf == 18
        assert req.preset == "slow"
        assert req.audio_bitrate == "192k"
