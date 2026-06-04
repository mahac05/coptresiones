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
import sys
from pathlib import Path
from typing import Callable, Optional
from dataclasses import dataclass

from core.models import JobResult


@dataclass
class LectureCompressionOptions:
    crf: int = 24
    preset: str = "medium"
    audio_bitrate: str = "64k"
    fps: int = 10


def _get_subprocess_kwargs() -> dict:
    """
    Возвращает дополнительные kwargs для subprocess.Popen/run,
    чтобы на Windows не появлялось консольное окно ffmpeg.
    """
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        return {
            "startupinfo": startupinfo,
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }
    return {}

# НЕ вызываем basicConfig — это задача entrypoint (main)
logger = logging.getLogger(__name__)


def find_ffmpeg_path(executable: str = "ffmpeg") -> str:
    """
    Ищет путь к FFmpeg/FFprobe в следующем порядке:
    1. В локальной папке resources/ffmpeg/ (для разработки и portable версии)
    2. Рядом с исполняемым файлом (для PyInstaller --onefile)
    3. В папке _MEIPASSresources/ffmpeg/ (для PyInstaller с ресурсами)
    4. В системном PATH
    
    Args:
        executable: имя исполняемого файла ("ffmpeg" или "ffprobe")
    
    Returns:
        Полный путь к исполняемому файлу или просто имя (если в PATH)
    """
    exe_name = f"{executable}.exe" if os.name == "nt" else executable
    
    # 1. Проверяем локальную папку resources/ffmpeg/
    # (работает при разработке и при portable распространении)
    script_dir = Path(__file__).parent.resolve()
    local_ffmpeg = script_dir / "resources" / "ffmpeg" / exe_name
    
    # Также проверяем уровень выше (если backend.py в подпапке)
    parent_ffmpeg = script_dir.parent / "resources" / "ffmpeg" / exe_name
    
    if local_ffmpeg.exists():
        logger.info(f"✓ Найден {executable} в локальных ресурсах: {local_ffmpeg}")
        return str(local_ffmpeg)
    elif parent_ffmpeg.exists():
        logger.info(f"✓ Найден {executable} в локальных ресурсах: {parent_ffmpeg}")
        return str(parent_ffmpeg)
    
    # 2. Проверяем папку с исполняемым файлом (PyInstaller --onefile)
    if getattr(sys, 'frozen', False):
        # Приложение запущено из PyInstaller
        exe_dir = Path(sys.executable).parent
        bundled_ffmpeg = exe_dir / exe_name
        if bundled_ffmpeg.exists():
            logger.info(f"✓ Найден {executable} рядом с exe: {bundled_ffmpeg}")
            return str(bundled_ffmpeg)
        
        # 3. Проверяем временную папку PyInstaller с ресурсами (_MEIPASS)
        if hasattr(sys, '_MEIPASS'):
            meipass_ffmpeg = Path(sys._MEIPASS) / "resources" / "ffmpeg" / exe_name
            if meipass_ffmpeg.exists():
                logger.info(f"✓ Найден {executable} в _MEIPASS: {meipass_ffmpeg}")
                return str(meipass_ffmpeg)
    
    # 4. Используем системный PATH
    logger.info(f"→ {executable} не найден локально, используем системный PATH")
    return executable


# ─── Чистые функции построения ffmpeg-команд ─────────────────────────

def build_conversion_command(
    *,
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
    *,
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


def build_compression_command_qsv(
    *,
    ffmpeg_path: str,
    input_file: str,
    output_file: str,
    global_quality: int,
    preset: str,
    audio_bitrate: str,
) -> list[str]:
    """
    Строит команду ffmpeg для сжатия видео через Intel QSV (GPU).
    Использует h264_qsv кодек и -global_quality вместо -crf.
    Чистая функция — легко тестировать без запуска ffmpeg.
    """
    return [
        ffmpeg_path,
        "-hwaccel", "qsv",
        "-i", input_file,
        "-c:v", "h264_qsv",
        "-global_quality", str(global_quality),
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


def build_compression_command_nvenc(
    *,
    ffmpeg_path: str,
    input_file: str,
    output_file: str,
    cq: int,
    preset: str,
    audio_bitrate: str,
) -> list[str]:
    """
    Строит команду ffmpeg для сжатия видео через NVIDIA NVENC (GPU).
    Использует h264_nvenc кодек и -cq (Constant Quality) вместо -crf.
    Чистая функция — легко тестировать без запуска ffmpeg.
    """
    return [
        ffmpeg_path,
        "-hwaccel", "cuda",
        "-hwaccel_output_format", "cuda",
        "-i", input_file,
        "-c:v", "h264_nvenc",
        "-preset", preset,
        "-rc", "vbr",
        "-cq", str(cq),
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


def build_lecture_compression_command(
    *,
    ffmpeg_path: str,
    input_file: str,
    output_file: str,
    crf: int,
    preset: str,
    audio_bitrate: str,
    fps: int = 10,
) -> list[str]:
    """
    Строит команду ffmpeg для сжатия видео-лекций со слайдами.
    Использует -tune stillimage для оптимизации статичных кадров,
    пониженный FPS и моно-аудио (-ac 1).
    Чистая функция — легко тестировать без запуска ffmpeg.
    """
    return [
        ffmpeg_path,
        "-i", input_file,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", preset,
        "-crf", str(crf),
        "-r", str(fps),
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-ac", "1",
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

    def __init__(self, ffmpeg_path: Optional[str] = None):
        """
        Инициализация конвертера.

        Args:
            ffmpeg_path: путь к ffmpeg (если None, ищется автоматически)
        """
        # Если путь не указан, ищем FFmpeg автоматически
        if ffmpeg_path is None:
            self.ffmpeg_path = find_ffmpeg_path("ffmpeg")
        else:
            self.ffmpeg_path = ffmpeg_path
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Проверяет доступность FFmpeg."""
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                timeout=5,
                **_get_subprocess_kwargs(),
            )
            logger.info(f"✓ FFmpeg найден и готов к использованию: {self.ffmpeg_path}")
        except FileNotFoundError:
            logger.error(f"FFmpeg не найден по пути: {self.ffmpeg_path}")
            raise FileNotFoundError(
                f"FFmpeg не установлен или недоступен.\n"
                f"Варианты решения:\n"
                f"1. Поместите ffmpeg.exe в папку resources/ffmpeg/\n"
                f"2. Скачайте с https://ffmpeg.org/download.html и добавьте в PATH\n"
                f"3. Используйте скрипт download_ffmpeg.ps1"
            )
        except Exception as e:
            logger.error(f"Ошибка при проверке FFmpeg: {e}")
            raise

    def _get_ffprobe_path(self) -> str:
        """Возвращает путь к ffprobe на основе ffmpeg_path."""
        # Пытаемся найти ffprobe тем же способом, что и ffmpeg
        if self.ffmpeg_path.lower().endswith(("ffmpeg", "ffmpeg.exe")):
            # Если путь к ffmpeg явный, заменяем ffmpeg на ffprobe
            base = self.ffmpeg_path.rsplit("ffmpeg", 1)[0]
            ext = ".exe" if os.name == "nt" else ""
            return f"{base}ffprobe{ext}"
        # Иначе ищем ffprobe автоматически
        return find_ffmpeg_path("ffprobe")

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
                **_get_subprocess_kwargs(),
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
            **_get_subprocess_kwargs(),
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
                    timeout=3600,
                    **_get_subprocess_kwargs(),
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


    def compress_mp4_video(
        self,
        input_file: str,
        output_file: str = None,
        crf: int = 23,
        preset: str = "medium",
        audio_bitrate: str = "128k",
        hw_accel: str = "cpu",
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> JobResult:
        """
        Сжимает MP4 видео (H.264) с использованием CRF.

        Args:
            hw_accel: "cpu", "nvenc" (NVIDIA) или "qsv" (Intel)

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

        encoder_names = {"cpu": "libx264 (CPU)", "nvenc": "h264_nvenc (NVIDIA)", "qsv": "h264_qsv (Intel)"}
        encoder = encoder_names.get(hw_accel, "libx264 (CPU)")
        logger.info(f"Начинаем сжатие видео [{encoder}]...")
        logger.info(f"Входной файл: {input_file}")
        logger.info(f"Выходной файл: {output_file}")
        logger.info(f"CRF: {crf}, preset: {preset}, audio: {audio_bitrate}")

        try:
            if hw_accel == "nvenc":
                command = build_compression_command_nvenc(
                    ffmpeg_path=self.ffmpeg_path,
                    input_file=input_file,
                    output_file=output_file,
                    cq=crf,
                    preset=preset,
                    audio_bitrate=audio_bitrate,
                )
            elif hw_accel == "qsv":
                command = build_compression_command_qsv(
                    ffmpeg_path=self.ffmpeg_path,
                    input_file=input_file,
                    output_file=output_file,
                    global_quality=crf,
                    preset=preset,
                    audio_bitrate=audio_bitrate,
                )
            else:
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
                    **_get_subprocess_kwargs(),
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

    def compress_lecture(
        self,
        input_file: str,
        output_file: str = None,
        options: LectureCompressionOptions = None,
        show_progress: bool = True,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> JobResult:
        """
        Сжимает видео-лекцию со слайдами.

        Использует -tune stillimage для оптимизации статичных кадров,
        пониженный FPS и моно-аудио. Даёт 10–50× сжатие по сравнению
        с обычным видео.

        Returns:
            JobResult с результатом операции
        """
        if options is None:
            options = LectureCompressionOptions()

        start_time = time.monotonic()

        if not os.path.exists(input_file):
            logger.error(f"Входной файл не найден: {input_file}")
            return JobResult.error("file_not_found", f"Входной файл не найден: {input_file}")

        if output_file is None:
            input_path = Path(input_file)
            output_file = str(input_path.parent / (input_path.stem + "_лекция.mp4"))

        logger.info("Начинаем сжатие лекции...")
        logger.info(f"Входной файл: {input_file}")
        logger.info(f"Выходной файл: {output_file}")
        logger.info(f"CRF: {options.crf}, preset: {options.preset}, audio: {options.audio_bitrate}, fps: {options.fps}")

        try:
            command = build_lecture_compression_command(
                ffmpeg_path=self.ffmpeg_path,
                input_file=input_file,
                output_file=output_file,
                crf=options.crf,
                preset=options.preset,
                audio_bitrate=options.audio_bitrate,
                fps=options.fps,
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
                    **_get_subprocess_kwargs(),
                )

            elapsed_ms = int((time.monotonic() - start_time) * 1000)

            if cancel_event and cancel_event.is_set():
                return JobResult.cancelled(duration_ms=elapsed_ms)

            if result.returncode == 0:
                logger.info("✅ Сжатие лекции успешно завершено!")
                logger.info(f"Файл сохранён: {output_file}")
                return JobResult.success(output_file=output_file, duration_ms=elapsed_ms)

            logger.error("❌ Ошибка при сжатии лекции:")
            logger.error(result.stderr)
            return JobResult.error(
                "ffmpeg_error",
                f"FFmpeg вернул код {result.returncode}: {result.stderr}",
                duration_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("❌ Таймаут: процесс сжатия лекции занял слишком много времени")
            return JobResult.timeout(duration_ms=elapsed_ms)
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"❌ Неожиданная ошибка: {e}")
            return JobResult.error("unknown", str(e), duration_ms=elapsed_ms)
