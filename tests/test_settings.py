import pytest
from core.settings import get_crf_description

@pytest.mark.parametrize(
    "crf, expected",
    [
        (18, "(высокое качество)"),
        (20, "(высокое качество)"),
        (23, "(стандартное)"),
        (25, "(стандартное)"),
        (28, "(хорошее сжатие)"),
        (30, "(хорошее сжатие)"),
        (32, "(сильное сжатие)"),
        (35, "(сильное сжатие)"),
    ],
)
def test_get_crf_description(crf: int, expected: str):
    """Test get_crf_description function for different CRF values."""
    assert get_crf_description(crf) == expected
