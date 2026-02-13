# core/__init__.py
# -*- coding: utf-8 -*-
"""
Core package: доменные модели, настройки, валидация и сервисы.
"""

from core.models import JobResult, ConversionRequest, CompressionRequest
from core.settings import TOOLTIPS, PRESETS, get_crf_description

__all__ = [
    "JobResult",
    "ConversionRequest",
    "CompressionRequest",
    "TOOLTIPS",
    "PRESETS",
    "get_crf_description",
]
