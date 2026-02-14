# tests/test_service.py
# -*- coding: utf-8 -*-
"""
Тесты для ProcessingService.
Используют mock FFmpegConverter для изоляции.
"""

import threading
import time
from unittest.mock import patch, MagicMock

import pytest
from core.models import JobResult, ConversionRequest, CompressionRequest, LectureCompressionRequest
from core.service import ProcessingService


class TestProcessingService:
    """Тесты для ProcessingService."""

    @patch("core.service.FFmpegConverter")
    def test_submit_conversion_calls_backend(self, MockConverter):
        """Проверяет, что submit_conversion вызывает backend."""
        mock_converter = MockConverter.return_value
        mock_converter.convert_mp4_to_audio.return_value = JobResult.success(
            output_file="out.m4a", duration_ms=100
        )

        service = ProcessingService(max_workers=1)
        request = ConversionRequest(
            input_file="input.mp4",
            output_file="output.m4a",
            output_format="m4a",
            bitrate="192k",
        )

        done = threading.Event()
        finished_results = []

        def on_finished(result, filepath):
            finished_results.append((result, filepath))
            done.set()

        cancel = threading.Event()
        service.submit_conversion(
            request=request,
            cancel_event=cancel,
            on_finished=on_finished,
        )
        done.wait(timeout=5)

        mock_converter.convert_mp4_to_audio.assert_called_once()
        call_kwargs = mock_converter.convert_mp4_to_audio.call_args
        assert call_kwargs.kwargs["input_file"] == "input.mp4"
        assert call_kwargs.kwargs["output_format"] == "m4a"

        assert len(finished_results) == 1
        assert finished_results[0][0].ok is True
        assert finished_results[0][1] == "input.mp4"

        service.shutdown(wait=True)

    @patch("core.service.FFmpegConverter")
    def test_submit_compression_calls_backend(self, MockConverter):
        """Проверяет, что submit_compression вызывает backend."""
        mock_converter = MockConverter.return_value
        mock_converter.compress_mp4_video.return_value = JobResult.success(
            output_file="out.mp4", duration_ms=200
        )

        service = ProcessingService(max_workers=1)
        request = CompressionRequest(
            input_file="input.mp4",
            output_file="output.mp4",
            crf=23,
            preset="medium",
            audio_bitrate="128k",
        )

        done = threading.Event()
        finished_results = []

        def on_finished(result, filepath):
            finished_results.append((result, filepath))
            done.set()

        cancel = threading.Event()
        service.submit_compression(
            request=request,
            cancel_event=cancel,
            on_finished=on_finished,
        )
        done.wait(timeout=5)

        mock_converter.compress_mp4_video.assert_called_once()
        assert len(finished_results) == 1
        assert finished_results[0][0].ok is True

        service.shutdown(wait=True)

    @patch("core.service.FFmpegConverter")
    def test_cancelled_before_start(self, MockConverter):
        """Проверяет, что задача отменяется если cancel_event уже set."""
        service = ProcessingService(max_workers=1)
        request = ConversionRequest(
            input_file="input.mp4",
            output_file="output.m4a",
        )

        done = threading.Event()
        finished_results = []

        def on_finished(result, filepath):
            finished_results.append((result, filepath))
            done.set()

        cancel = threading.Event()
        cancel.set()  # Отменяем до старта

        service.submit_conversion(
            request=request,
            cancel_event=cancel,
            on_finished=on_finished,
        )
        done.wait(timeout=5)

        assert len(finished_results) == 1
        assert finished_results[0][0].ok is False
        assert finished_results[0][0].status == "cancelled"

        service.shutdown(wait=True)

    @patch("core.service.FFmpegConverter")
    def test_max_workers(self, MockConverter):
        """Проверяет, что max_workers корректно устанавливается."""
        service = ProcessingService(max_workers=8)
        assert service.max_workers == 8
        service.shutdown()

    @patch("core.service.FFmpegConverter")
    def test_progress_callback(self, MockConverter):
        """Проверяет, что progress callback вызывается."""
        mock_converter = MockConverter.return_value

        progress_values = []

        def fake_convert(**kwargs):
            cb = kwargs.get("progress_callback")
            if cb:
                cb(50)
                cb(100)
            return JobResult.success(output_file="out.m4a", duration_ms=100)

        mock_converter.convert_mp4_to_audio.side_effect = fake_convert

        service = ProcessingService(max_workers=1)
        request = ConversionRequest(
            input_file="input.mp4",
            output_file="output.m4a",
        )

        done = threading.Event()

        def on_progress(percent, filepath):
            progress_values.append(percent)

        def on_finished(result, filepath):
            done.set()

        cancel = threading.Event()
        service.submit_conversion(
            request=request,
            cancel_event=cancel,
            on_progress=on_progress,
            on_finished=on_finished,
        )
        done.wait(timeout=5)

        assert 50 in progress_values
        assert 100 in progress_values

        service.shutdown(wait=True)

    @patch("core.service.FFmpegConverter")
    def test_submit_lecture_compression_calls_backend(self, MockConverter):
        """Проверяет, что submit_lecture_compression вызывает backend."""
        mock_converter = MockConverter.return_value
        mock_converter.compress_lecture.return_value = JobResult.success(
            output_file="lecture_out.mp4", duration_ms=300
        )

        service = ProcessingService(max_workers=1)
        request = LectureCompressionRequest(
            input_file="lecture.mp4",
            output_file="lecture_out.mp4",
            crf=24,
            preset="medium",
            audio_bitrate="64k",
            fps=10,
        )

        done = threading.Event()
        finished_results = []

        def on_finished(result, filepath):
            finished_results.append((result, filepath))
            done.set()

        cancel = threading.Event()
        service.submit_lecture_compression(
            request=request,
            cancel_event=cancel,
            on_finished=on_finished,
        )
        done.wait(timeout=5)

        mock_converter.compress_lecture.assert_called_once()
        call_kwargs = mock_converter.compress_lecture.call_args
        assert call_kwargs.kwargs["input_file"] == "lecture.mp4"
        assert call_kwargs.kwargs["fps"] == 10

        assert len(finished_results) == 1
        assert finished_results[0][0].ok is True
        assert finished_results[0][1] == "lecture.mp4"

        service.shutdown(wait=True)
