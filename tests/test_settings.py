import pytest
from core.settings import get_crf_description

@pytest.mark.parametrize(
    "crf, expected",
    [
        # crf <= 20
        (0, "(высокое качество)"),
        (18, "(высокое качество)"),
        (20, "(высокое качество)"),
        (-10, "(высокое качество)"),
        # 20 < crf <= 25
        (21, "(стандартное)"),
        (23, "(стандартное)"),
        (25, "(стандартное)"),
        # 25 < crf <= 30
        (26, "(хорошее сжатие)"),
        (28, "(хорошее сжатие)"),
        (30, "(хорошее сжатие)"),
        # crf > 30
        (31, "(сильное сжатие)"),
        (40, "(сильное сжатие)"),
        (51, "(сильное сжатие)"),
    ],
)
def test_get_crf_description(crf, expected):
    """Test get_crf_description returns correct string based on crf value."""
    assert get_crf_description(crf) == expected
