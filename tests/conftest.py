# tests/conftest.py
# -*- coding: utf-8 -*-
"""
Конфигурация pytest: добавляем корень проекта в sys.path.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
