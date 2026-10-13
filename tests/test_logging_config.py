# -*- coding: utf-8 -*-
import logging
import sys
from core.logging_config import setup_logging
import pytest

@pytest.fixture(autouse=True)
def reset_logging():
    """
    Fixture to reset logging state after each test.
    """
    logger = logging.getLogger()
    # Save original state
    old_handlers = logger.handlers[:]
    old_level = logger.level

    yield

    # Restore original state
    logger.handlers = old_handlers
    logger.setLevel(old_level)


def test_setup_logging_default_level():
    """
    Test setup_logging with default level (INFO).
    """
    setup_logging()

    logger = logging.getLogger()
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1

    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream == sys.stdout
    assert handler.level == logging.INFO

    formatter = handler.formatter
    assert isinstance(formatter, logging.Formatter)
    assert formatter._fmt == '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    assert formatter.datefmt == '%H:%M:%S'


def test_setup_logging_custom_level():
    """
    Test setup_logging with a custom level (DEBUG).
    """
    setup_logging(level=logging.DEBUG)

    logger = logging.getLogger()
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 1

    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream == sys.stdout
    assert handler.level == logging.DEBUG


def test_setup_logging_clears_existing_handlers():
    """
    Test setup_logging clears existing handlers before adding a new one.
    """
    logger = logging.getLogger()
    # Add a dummy handler
    dummy_handler = logging.NullHandler()
    logger.addHandler(dummy_handler)

    setup_logging()

    # Verify the dummy handler was removed and only one stream handler remains
    assert len(logger.handlers) == 1
    assert dummy_handler not in logger.handlers
    assert isinstance(logger.handlers[0], logging.StreamHandler)
