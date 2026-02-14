# core/logging_config.py
# -*- coding: utf-8 -*-
"""
Централизованная конфигурация логирования для всех entrypoint'ов приложения.
"""

import logging


def setup_logging(level=logging.INFO):
    """
    Настраивает логирование для приложения.
    
    Args:
        level: Уровень логирования (по умолчанию INFO)
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
