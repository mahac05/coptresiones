# core/logging_config.py
# -*- coding: utf-8 -*-
"""
Централизованная конфигурация логирования для всех entrypoint'ов приложения.
"""

import logging
import sys

def setup_logging(level=logging.INFO):
    """
    Настраивает базовое логирование в консоль.
    """
    logger = logging.getLogger()
    logger.setLevel(level)

    # Очищаем существующие обработчики
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Настраиваем консольный вывод
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
