# backend.py
# -*- coding: utf-8 -*-
"""
Backend для обработки видео с использованием FFmpeg.
Содержит только логику, без UI.
"""

import os
import subprocess
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from core.models import JobResult

# НЕ вызываем basicConfig — это задача entrypoint (main)
logger = logging.getLogger(__name__)


# ─── Чистые функции построения ffmpeg-команд ─────────────────────────

def build_conversion_command(
    ffmpeg_path: str,
    input_file: str,
    output_file: str,
    codec: str,
    bitrate: str,
) -> list[str]:
    """
    Строит команду ffmpeg для конвертации видео в аудио.
    Чистая функция — легко тестировать без запуска ffmpeg.
    """
    return [
        ffmpeg_path,
        "-i", input_file,
        "-vn",
        "-acodec", codec,
        "-b:a", bitrate,
        "-q:a", "0",
        "-progress", "pipe:1",
        "-nostats",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        output_file,
    ]


def build_compression_command(
    ffmpeg_path: str,
    input_file: str,
    output_file: str,
    crf: int,
    preset: str,
    audio_bitrate: str,
) -> list[str]:
    """
    Строит команду ffmpeg для сжатия видео (H.264 + CRF).
    Чистая функция — легко тестировать без запуска ffmpeg.
    """
    return [
        ffmpeg_path,
        "-i", input_file,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        output_file,
    ]


class FFmpegConverter:
    """Класс для конвертирования и сжатия видео."""

    # Поддерживаемые форматы выходного аудио
    AUDIO_FORMATS = {
        'm4a': {'codec': 'aac', 'extension': '.m4a'},
        'mp3': {'codec': 'libmp3lame', 'extension': '.mp3'},
        'wav': {'codec': 'pcm_s16le', 'extension': '.wav'},
        'aac': {'codec': 'aac', 'extension': '.aac'},
        'flac': {'codec': 'flac', 'extension': '.flac'},
        'ogg': {'codec': 'libvorbis', 'extension': '.ogg'},
    }

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """
        Инициализация конвертера.

        Args:
            ffmpeg_path: путь к ffmpeg (по умолчанию ffmpeg из PATH)
        """
        self.ffmpeg_path = ffmpeg_path
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Проверяет доступность FFmpeg."""
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5
            )
            logger.info("FFmpeg найден и готов к использованию")
        except FileNotFoundError:
            logger.error(f"FFmpeg не найден по пути: {self.ffmpeg_path}")
            raise FileNotFoundError(
                f"FFmpeg не установлен или недоступен. "
                f"Скачайте с https://ffmpeg.org/download.html"
            )
        except Exception as e:
            logger.error(f"Ошибка при проверке FFmpeg: {e}")
            raise

    def _get_ffprobe_path(self) -> str:
        """Возвращает путь к ffprobe на основе ffmpeg_path."""
        if self.ffmpeg_path.lower().endswith(("ffmpeg", "ffmpeg.exe")):
            return self.ffmpeg_path.rsplit("ffmpeg", 1)[0] + "ffprobe"
        return "ffprobe"

    def _get_duration_seconds(self, input_file: str) -> Optional[float]:
        """Получает длительность файла (секунды) через ffprobe."""
        ffprobe_path = self._get_ffprobe_path()
        try:
            result = subprocess.run(
                [
                    ffprobe_path,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=nokey=1:noprint_wrappers=1",
                    input_file,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return None
            duration_str = result.stdout.strip()
            return float(duration_str) if duration_str else None
        except Exception:
            return None

    def _run_ffmpeg_with_progress(
        self,
        command: list,
        duration_seconds: Optional[float],
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> subprocess.CompletedProcess:
        """Запускает ffmpeg и отображает прогресс."""
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        last_percent = -1
        cancelled = False
        if process.stdout:
            for line in process.stdout:
                # Проверяем отмену
                if cancel_event and cancel_event.is_set():
                    process.terminate()
                    process.wait()
                    cancelled = True
                    break

                if duration_seconds and line.startswith("out_time_ms="):
                    try:
                        ms = int(line.split("=", 1)[1].strip())
                        percent = min(100, int((ms / 1_000_000) / duration_seconds * 100))
                        if percent != last_percent:
                            last_percent = percent
                            if progress_callback:
                                progress_callback(percent)
                            else:
                                print(f"\rПрогресс: {percent}%", end="", flush=True)
                    except ValueError:
                        pass
                elif line.strip() == "progress=end":
                    if progress_callback:
                        progress_callback(100)
                    else:
                        print("\rПрогресс: 100%", end="", flush=True)

        if cancelled:
            return subprocess.CompletedProcess(
                args=command, returncode=-1, stdout="", stderr="Отменено"
            )

        returncode = process.wait()

        if duration_seconds:
            print("")

        return subprocess.CompletedProcess(
            args=command,
            returncode=returncode,
            stdout="",
            stderr="",
        )

    def convert_mp4_to_audio(
        self,
        input_file: str,
        output_format: str = "m4a",
        bitrate: str = "192k",
        output_file: str = None,
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> JobResult:
        """
        Преобразует MP4 видео в аудио файл.

        Args:
            input_file: путь к MP4 файлу
            output_format: формат выходного аудио (mp3, wav, aac, flac, ogg)
            bitrate: битрейт аудио (например, '192k', '320k', '128k')
            output_file: путь к выходному файлу (если не указан, создаётся в той же папке)

        Returns:
            JobResult с результатом операции
        """
        start_time = time.monotonic()

        if not os.path.exists(input_file):
            logger.error(f"Входной файл не найден: {input_file}")
            return JobResult.error("file_not_found", f"Входной файл не найден: {input_file}")

        if not input_file.lower().endswith('.mp4'):
            logger.warning(f"Файл может быть не MP4: {input_file}")

        if output_format.lower() not in self.AUDIO_FORMATS:
            msg = (
                f"Неподдерживаемый формат: {output_format}. "
                f"Поддерживаемые: {', '.join(self.AUDIO_FORMATS.keys())}"
            )
            logger.error(msg)
            return JobResult.error("invalid_format", msg)

        if output_file is None:
            input_path = Path(input_file)
            ext = self.AUDIO_FORMATS[output_format.lower()]['extension']
            output_file = str(input_path.parent / (input_path.stem + "_audio" + ext))

        logger.info(f"Начинаем конвертирование...")
        logger.info(f"Входной файл: {input_file}")
        logger.info(f"Выходной файл: {output_file}")
        logger.info(f"Формат: {output_format}, Битрейт: {bitrate}")

        try:
            codec = self.AUDIO_FORMATS[output_format.lower()]['codec']

            command = build_conversion_command(
                ffmpeg_path=self.ffmpeg_path,
                input_file=input_file,
                output_file=output_file,
                codec=codec,
                bitrate=bitrate,
            )

            duration_seconds = self._get_duration_seconds(input_file) if show_progress else None

            if show_progress:
                result = self._run_ffmpeg_with_progress(
                    command,
                    duration_seconds,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                )
            else:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=3600
                )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            if cancel_event and cancel_event.is_set():
                return JobResult.cancelled(duration_ms=elapsed_ms)

            if result.returncode == 0:
                logger.info(f"✅ Конвертирование успешно завершено!")
                logger.info(f"Файл сохранён: {output_file}")
                return JobResult.success(output_file=output_file, duration_ms=elapsed_ms)
            else:
                logger.error(f"❌ Ошибка при конвертировании:")
                logger.error(result.stderr)
                return JobResult.error(
                    "ffmpeg_error",
                    f"FFmpeg вернул код {result.returncode}: {result.stderr}",
                    duration_ms=elapsed_ms,
                )

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("❌ Таймаут: процесс конвертирования занял слишком много времени")
            return JobResult.timeout(duration_ms=elapsed_ms)
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"❌ Неожиданная ошибка: {e}")
            return JobResult.error("unknown", str(e), duration_ms=elapsed_ms)

    def convert_batch(
        self,
        input_folder: str,
        output_format: str = "m4a",
        bitrate: str = "192k",
        output_folder: str = None
    ) -> dict:
        """
        Преобразует все MP4 файлы в папке.

        Args:
            input_folder: папка с MP4 файлами
            output_format: формат выходного аудио
            bitrate: битрейт аудио
            output_folder: папка для сохранения

        Returns:
            dict с результатами: {'успешно': список файлов, 'ошибки': список файлов}
        """

        if not os.path.isdir(input_folder):
            logger.error(f"Папка не найдена: {input_folder}")
            return {'успешно': [], 'ошибки': []}

        if output_folder is None:
            output_folder = input_folder
        else:
            os.makedirs(output_folder, exist_ok=True)

        results = {'успешно': [], 'ошибки': []}

        mp4_files = list(Path(input_folder).glob('*.mp4'))

        if not mp4_files:
            logger.warning(f"MP4 файлы не найдены в папке: {input_folder}")
            return results

        logger.info(f"Найдено {len(mp4_files)} MP4 файлов. Начинаем обработку...")

        for idx, mp4_file in enumerate(mp4_files, 1):
            logger.info(f"\n[{idx}/{len(mp4_files)}] Обрабатываем: {mp4_file.name}")

            output_file = os.path.join(
                output_folder,
                mp4_file.stem + self.AUDIO_FORMATS[output_format.lower()]['extension']
            )

            job_result = self.convert_mp4_to_audio(str(mp4_file), output_format, bitrate, output_file)
            if job_result.ok:
                results['успешно'].append(mp4_file.name)
            else:
                results['ошибки'].append(mp4_file.name)

        logger.info("\n" + "="*50)
        logger.info("ИТОГОВЫЙ ОТЧЁТ")
        logger.info("="*50)
        logger.info(f"✅ Успешно: {len(results['успешно'])}")
        for file in results['успешно']:
            logger.info(f"   - {file}")

        if results['ошибки']:
            logger.info(f"❌ Ошибки: {len(results['ошибки'])}")
            for file in results['ошибки']:
                logger.info(f"   - {file}")

        return results

    def compress_mp4_video(
        self,
        input_file: str,
        output_file: str = None,
        crf: int = 23,
        preset: str = "medium",
        audio_bitrate: str = "128k",
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> JobResult:
        """
        Сжимает MP4 видео (H.264) с использованием CRF.

        CRF ориентиры:
        - 18-23: Стандартное высокое качество (файл будет большим).
        - 28: Хорошее сжатие (размер сильно падает, качество приемлемое).
        - 32 и выше: Сильное сжатие (качество заметно падает).

        Returns:
            JobResult с результатом операции
        """
        start_time = time.monotonic()

        if not os.path.exists(input_file):
            logger.error(f"Входной файл не найден: {input_file}")
            return JobResult.error("file_not_found", f"Входной файл не найден: {input_file}")

        if output_file is None:
            input_path = Path(input_file)
            output_file = str(input_path.parent / (input_path.stem + "_compressed.mp4"))

        logger.info("Начинаем сжатие видео...")
        logger.info(f"Входной файл: {input_file}")
        logger.info(f"Выходной файл: {output_file}")
        logger.info(f"CRF: {crf}, preset: {preset}, audio: {audio_bitrate}")

        try:
            command = build_compression_command(
                ffmpeg_path=self.ffmpeg_path,
                input_file=input_file,
                output_file=output_file,
                crf=crf,
                preset=preset,
                audio_bitrate=audio_bitrate,
            )

            duration_seconds = self._get_duration_seconds(input_file) if show_progress else None

            if show_progress:
                result = self._run_ffmpeg_with_progress(
                    command,
                    duration_seconds,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                )
            else:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            if cancel_event and cancel_event.is_set():
                return JobResult.cancelled(duration_ms=elapsed_ms)

            if result.returncode == 0:
                logger.info("✅ Сжатие успешно завершено!")
                logger.info(f"Файл сохранён: {output_file}")
                return JobResult.success(output_file=output_file, duration_ms=elapsed_ms)

            logger.error("❌ Ошибка при сжатии видео:")
            logger.error(result.stderr)
            return JobResult.error(
                "ffmpeg_error",
                f"FFmpeg вернул код {result.returncode}: {result.stderr}",
                duration_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("❌ Таймаут: процесс сжатия занял слишком много времени")
            return JobResult.timeout(duration_ms=elapsed_ms)
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"❌ Неожиданная ошибка: {e}")
            return JobResult.error("unknown", str(e), duration_ms=elapsed_ms)
