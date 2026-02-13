# core/models.py
# -*- coding: utf-8 -*-
"""
Доменные модели для видео обработчика.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JobResult:
    """
    Структурированный результат обработки файла.

    Attributes:
        status: "success" | "error" | "cancelled" | "timeout"
        error_code: Машиночитаемый код ошибки (пустая строка при успехе)
        error_message: Человекочитаемое описание ошибки
        output_file: Путь к выходному файлу (пустая строка при ошибке)
        duration_ms: Длительность обработки в миллисекундах
    """

    status: str = "success"
    error_code: str = ""
    error_message: str = ""
    output_file: str = ""
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        """True если обработка завершилась успешно."""
        return self.status == "success"

    # Фабричные методы для удобства

    @classmethod
    def success(cls, output_file: str, duration_ms: int = 0) -> "JobResult":
        return cls(
            status="success",
            output_file=output_file,
            duration_ms=duration_ms,
        )

    @classmethod
    def error(
        cls,
        error_code: str,
        error_message: str,
        duration_ms: int = 0,
    ) -> "JobResult":
        return cls(
            status="error",
            error_code=error_code,
            error_message=error_message,
            duration_ms=duration_ms,
        )

    @classmethod
    def cancelled(cls, duration_ms: int = 0) -> "JobResult":
        return cls(
            status="cancelled",
            error_code="cancelled",
            error_message="Операция отменена пользователем",
            duration_ms=duration_ms,
        )

    @classmethod
    def timeout(cls, duration_ms: int = 0) -> "JobResult":
        return cls(
            status="timeout",
            error_code="timeout",
            error_message="Превышено время ожидания",
            duration_ms=duration_ms,
        )


@dataclass
class ConversionRequest:
    """Запрос на конвертацию видео в аудио."""

    input_file: str
    output_file: str
    output_format: str = "m4a"
    bitrate: str = "192k"


@dataclass
class CompressionRequest:
    """Запрос на сжатие видео."""

    input_file: str
    output_file: str
    crf: int = 23
    preset: str = "medium"
    audio_bitrate: str = "128k"
