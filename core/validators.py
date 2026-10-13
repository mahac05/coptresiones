# core/validators.py
# -*- coding: utf-8 -*-
"""
Чистые функции валидации параметров.
Легко тестируются без UI и без FFmpeg.
"""

import os
from typing import Tuple

from backend import FFmpegConverter


def validate_input_file(path: str) -> Tuple[bool, str]:
    """
    Валидирует входной файл.

    Returns:
        (valid, error_message)
    """
    if not path or not path.strip():
        return False, "Путь к файлу не указан"
    path = path.strip()
    if not os.path.exists(path):
        return False, f"Файл не найден: {path}"
    if not os.path.isfile(path):
        return False, f"Указанный путь не является файлом: {path}"
    if not os.access(path, os.R_OK):
        return False, f"Нет прав на чтение файла: {path}"
    return True, ""


def validate_output_format(fmt: str) -> Tuple[bool, str]:
    """
    Валидирует формат аудио.

    Returns:
        (valid, error_message)
    """
    if not fmt:
        return False, "Формат не указан"
    if fmt.lower() not in FFmpegConverter.AUDIO_FORMATS:
        supported = ", ".join(FFmpegConverter.AUDIO_FORMATS.keys())
        return False, f"Неподдерживаемый формат: {fmt}. Поддерживаемые: {supported}"
    return True, ""


def build_output_path(
    input_file: str,
    output_folder: str,
    extension: str,
    suffix: str = "",
) -> str:
    """
    Строит путь выходного файла.

    Args:
        input_file: путь к входному файлу
        output_folder: папка для сохранения (пустая строка = та же папка)
        extension: расширение (например 'm4a', 'mp4')
        suffix: суффикс к имени (например '_сжатое')

    Returns:
        Полный путь к выходному файлу
    """
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    folder = output_folder if output_folder else os.path.dirname(input_file)
    return os.path.join(folder, f"{base_name}{suffix}.{extension}")
