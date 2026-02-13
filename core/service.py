# core/service.py
# -*- coding: utf-8 -*-
"""
ProcessingService — сервисный слой для оркестрации задач обработки видео.
Использует Thread-пул на основе threading + queue (без concurrent.futures,
который сломан в Python 3.13.2).
"""

import logging
import os
import threading
import queue
from typing import Callable, Optional

from backend import FFmpegConverter
from core.models import JobResult, ConversionRequest, CompressionRequest
from core.settings import MAX_PARALLEL_TASKS

logger = logging.getLogger(__name__)


class _SimpleThreadPool:
    """
    Простой пул потоков на основе threading + queue.Queue.
    Замена ThreadPoolExecutor для совместимости с Python 3.13.
    """

    def __init__(self, max_workers: int):
        self._max_workers = max_workers
        self._queue: queue.Queue = queue.Queue()
        self._workers: list[threading.Thread] = []
        self._shutdown = False

        for _ in range(max_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self._workers.append(t)

    def _worker_loop(self):
        while True:
            try:
                task = self._queue.get(timeout=0.5)
            except queue.Empty:
                if self._shutdown:
                    return
                continue
            if task is None:  # Sentinel for shutdown
                return
            func, args = task
            try:
                func(*args)
            except Exception as e:
                logger.error(f"Worker error: {e}")
            finally:
                self._queue.task_done()

    def submit(self, func, *args):
        """Отправляет задачу в пул."""
        self._queue.put((func, args))

    def shutdown(self, wait: bool = False):
        """Останавливает пул."""
        self._shutdown = True
        for _ in self._workers:
            self._queue.put(None)  # Sentinel
        if wait:
            for t in self._workers:
                t.join()


class ProcessingService:
    """
    Централизованный сервис обработки видео.

    Вместо thread-per-file + Semaphore использует пул воркеров.
    UI только подписывается на колбэки.
    """

    def __init__(self, max_workers: int = MAX_PARALLEL_TASKS):
        self._pool = _SimpleThreadPool(max_workers=max_workers)
        self._converter = FFmpegConverter()
        self._max_workers = max_workers

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def converter(self) -> FFmpegConverter:
        """Public access to the underlying converter, for single-file UIs (tkinter)."""
        return self._converter

    def submit_conversion(
        self,
        request: ConversionRequest,
        cancel_event: threading.Event,
        on_progress: Optional[Callable[[int, str], None]] = None,
        on_finished: Optional[Callable[[JobResult, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        """
        Отправляет задачу конвертации в пул.

        Args:
            request: параметры конвертации
            cancel_event: событие для отмены задачи
            on_progress: callback(percent, file_path)
            on_finished: callback(result, file_path)
            on_log: callback(message)
        """
        self._pool.submit(
            self._run_conversion,
            request, cancel_event, on_progress, on_finished, on_log,
        )

    def submit_compression(
        self,
        request: CompressionRequest,
        cancel_event: threading.Event,
        on_progress: Optional[Callable[[int, str], None]] = None,
        on_finished: Optional[Callable[[JobResult, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        """
        Отправляет задачу сжатия в пул.

        Args:
            request: параметры сжатия
            cancel_event: событие для отмены задачи
            on_progress: callback(percent, file_path)
            on_finished: callback(result, file_path)
            on_log: callback(message)
        """
        self._pool.submit(
            self._run_compression,
            request, cancel_event, on_progress, on_finished, on_log,
        )

    def shutdown(self, wait: bool = False):
        """Останавливает пул воркеров."""
        self._pool.shutdown(wait=wait)

    # ─── Internal workers ────────────────────────────────────────────

    def _run_conversion(
        self,
        request: ConversionRequest,
        cancel_event: threading.Event,
        on_progress: Optional[Callable[[int, str], None]],
        on_finished: Optional[Callable[[JobResult, str], None]],
        on_log: Optional[Callable[[str], None]],
    ):
        file_name = os.path.basename(request.input_file)

        if cancel_event.is_set():
            result = JobResult.cancelled()
            if on_finished:
                on_finished(result, request.input_file)
            return

        if on_log:
            on_log(f"▶ Конвертация: {file_name}")

        def progress_cb(percent: int):
            if on_progress:
                on_progress(percent, request.input_file)

        try:
            result = self._converter.convert_mp4_to_audio(
                input_file=request.input_file,
                output_format=request.output_format,
                bitrate=request.bitrate,
                output_file=request.output_file,
                show_progress=True,
                progress_callback=progress_cb,
                cancel_event=cancel_event,
            )
        except Exception as e:
            logger.error(f"Ошибка конвертации ({file_name}): {e}")
            result = JobResult.error("unknown", str(e))
            if on_log:
                on_log(f"❌ Ошибка ({file_name}): {e}")

        if on_finished:
            on_finished(result, request.input_file)

    def _run_compression(
        self,
        request: CompressionRequest,
        cancel_event: threading.Event,
        on_progress: Optional[Callable[[int, str], None]],
        on_finished: Optional[Callable[[JobResult, str], None]],
        on_log: Optional[Callable[[str], None]],
    ):
        file_name = os.path.basename(request.input_file)

        if cancel_event.is_set():
            result = JobResult.cancelled()
            if on_finished:
                on_finished(result, request.input_file)
            return

        if on_log:
            on_log(f"▶ Сжатие: {file_name}")

        def progress_cb(percent: int):
            if on_progress:
                on_progress(percent, request.input_file)

        try:
            result = self._converter.compress_mp4_video(
                input_file=request.input_file,
                output_file=request.output_file,
                crf=request.crf,
                preset=request.preset,
                audio_bitrate=request.audio_bitrate,
                show_progress=True,
                progress_callback=progress_cb,
                cancel_event=cancel_event,
            )
        except Exception as e:
            logger.error(f"Ошибка сжатия ({file_name}): {e}")
            result = JobResult.error("unknown", str(e))
            if on_log:
                on_log(f"❌ Ошибка ({file_name}): {e}")

        if on_finished:
            on_finished(result, request.input_file)
