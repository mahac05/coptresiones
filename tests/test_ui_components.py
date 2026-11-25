import pytest
from ui_components_pyqt import format_duration

@pytest.mark.parametrize(
    "ms, expected",
    [
        (0, "<1с"),
        (999, "<1с"),
        (1000, "1с"),
        (59000, "59с"),
        (60000, "1м 0с"),
        (61000, "1м 1с"),
        (119000, "1м 59с"),
        (120000, "2м 0с"),
        (3600000, "60м 0с"),
        (3661000, "61м 1с"),
    ],
)
def test_format_duration(ms, expected):
    """Test format_duration handles various inputs correctly."""
    assert format_duration(ms) == expected
