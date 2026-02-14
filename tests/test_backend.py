# tests/test_backend.py
# -*- coding: utf-8 -*-
"""
Тесты для чистых функций построения ffmpeg-команд.
Не требуют установленного FFmpeg.
"""

import pytest
from backend import build_conversion_command, build_compression_command, build_lecture_compression_command, build_compression_command_qsv


class TestBuildConversionCommand:
    """Тесты для build_conversion_command."""

    def test_basic_command(self):
        cmd = build_conversion_command(
            ffmpeg_path="ffmpeg",
            input_file="input.mp4",
            output_file="output.m4a",
            codec="aac",
            bitrate="192k",
        )
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert cmd[cmd.index("-i") + 1] == "input.mp4"
        assert "-vn" in cmd  # Без видео
        assert "-acodec" in cmd
        assert cmd[cmd.index("-acodec") + 1] == "aac"
        assert "-b:a" in cmd
        assert cmd[cmd.index("-b:a") + 1] == "192k"
        assert cmd[-1] == "output.m4a"
        assert "-y" in cmd  # Перезаписывать

    def test_different_codec_and_bitrate(self):
        cmd = build_conversion_command(
            ffmpeg_path="/usr/bin/ffmpeg",
            input_file="video.mp4",
            output_file="audio.mp3",
            codec="libmp3lame",
            bitrate="320k",
        )
        assert cmd[0] == "/usr/bin/ffmpeg"
        assert cmd[cmd.index("-acodec") + 1] == "libmp3lame"
        assert cmd[cmd.index("-b:a") + 1] == "320k"

    def test_progress_output(self):
        cmd = build_conversion_command(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.m4a",
            codec="aac",
            bitrate="128k",
        )
        assert "-progress" in cmd
        assert "pipe:1" in cmd
        assert "-nostats" in cmd


class TestBuildCompressionCommand:
    """Тесты для build_compression_command."""

    def test_basic_command(self):
        cmd = build_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="input.mp4",
            output_file="output.mp4",
            crf=23,
            preset="medium",
            audio_bitrate="128k",
        )
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert cmd[cmd.index("-i") + 1] == "input.mp4"
        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "libx264"
        assert "-crf" in cmd
        assert cmd[cmd.index("-crf") + 1] == "23"
        assert "-preset" in cmd
        assert cmd[cmd.index("-preset") + 1] == "medium"
        assert "-c:a" in cmd
        assert cmd[cmd.index("-c:a") + 1] == "aac"
        assert "-b:a" in cmd
        assert cmd[cmd.index("-b:a") + 1] == "128k"
        assert "-movflags" in cmd
        assert cmd[-1] == "output.mp4"

    def test_custom_crf_and_preset(self):
        cmd = build_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            crf=18,
            preset="veryslow",
            audio_bitrate="256k",
        )
        assert cmd[cmd.index("-crf") + 1] == "18"
        assert cmd[cmd.index("-preset") + 1] == "veryslow"
        assert cmd[cmd.index("-b:a") + 1] == "256k"

    def test_crf_is_string(self):
        """CRF should be converted to string in the command."""
        cmd = build_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            crf=32,
            preset="fast",
            audio_bitrate="128k",
        )
        crf_value = cmd[cmd.index("-crf") + 1]
        assert isinstance(crf_value, str)
        assert crf_value == "32"


class TestBuildLectureCompressionCommand:
    """Тесты для build_lecture_compression_command."""

    def test_basic_command(self):
        cmd = build_lecture_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="lecture.mp4",
            output_file="lecture_out.mp4",
            crf=24,
            preset="medium",
            audio_bitrate="64k",
            fps=10,
        )
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert cmd[cmd.index("-i") + 1] == "lecture.mp4"
        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "libx264"
        assert cmd[-1] == "lecture_out.mp4"

    def test_tune_stillimage(self):
        cmd = build_lecture_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            crf=24,
            preset="medium",
            audio_bitrate="64k",
        )
        assert "-tune" in cmd
        assert cmd[cmd.index("-tune") + 1] == "stillimage"

    def test_reduced_fps(self):
        cmd = build_lecture_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            crf=24,
            preset="medium",
            audio_bitrate="64k",
            fps=10,
        )
        assert "-r" in cmd
        assert cmd[cmd.index("-r") + 1] == "10"

    def test_mono_audio(self):
        cmd = build_lecture_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            crf=24,
            preset="medium",
            audio_bitrate="64k",
        )
        assert "-ac" in cmd
        assert cmd[cmd.index("-ac") + 1] == "1"

    def test_custom_fps(self):
        cmd = build_lecture_compression_command(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            crf=28,
            preset="slow",
            audio_bitrate="96k",
            fps=5,
        )
        assert cmd[cmd.index("-r") + 1] == "5"
        assert cmd[cmd.index("-crf") + 1] == "28"
        assert cmd[cmd.index("-preset") + 1] == "slow"
        assert cmd[cmd.index("-b:a") + 1] == "96k"


class TestBuildCompressionCommandQsv:
    """Тесты для build_compression_command_qsv."""

    def test_uses_qsv_codec(self):
        cmd = build_compression_command_qsv(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            global_quality=23,
            preset="medium",
            audio_bitrate="128k",
        )
        assert cmd[0] == "ffmpeg"
        assert "-c:v" in cmd
        assert cmd[cmd.index("-c:v") + 1] == "h264_qsv"

    def test_hwaccel_qsv(self):
        cmd = build_compression_command_qsv(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            global_quality=23,
            preset="medium",
            audio_bitrate="128k",
        )
        assert "-hwaccel" in cmd
        assert cmd[cmd.index("-hwaccel") + 1] == "qsv"

    def test_global_quality(self):
        cmd = build_compression_command_qsv(
            ffmpeg_path="ffmpeg",
            input_file="in.mp4",
            output_file="out.mp4",
            global_quality=28,
            preset="fast",
            audio_bitrate="96k",
        )
        assert "-global_quality" in cmd
        assert cmd[cmd.index("-global_quality") + 1] == "28"
        assert "-crf" not in cmd
        assert cmd[cmd.index("-preset") + 1] == "fast"
        assert cmd[cmd.index("-b:a") + 1] == "96k"
