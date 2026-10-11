import pytest
from ui_components_pyqt import elide_path

def test_elide_path_short():
    """Test with a path shorter than max_chars"""
    path = "C:/short/path.mp4"
    assert elide_path(path, max_chars=45) == path

def test_elide_path_exact():
    """Test with a path exactly max_chars long"""
    # 45 chars long string
    path = "C:/a_very/specific/folder_structure/video.mp4"
    assert len(path) == 45
    assert elide_path(path, max_chars=45) == path

def test_elide_path_long_huge_filename():
    """Test with a filename that is itself too long"""
    # max_chars = 10, len(name) = 8
    path = "C:/folder/file.mp4"
    result = elide_path(path, max_chars=10)
    # file.mp4 is 8 chars, 8 >= 10 - 5 (8 >= 5)
    # returns name[:10-8] + "..." + p.suffix -> "fi...mp4" Wait, p.suffix is ".mp4", name[:2] is "fi" -> "fi....mp4"
    assert result == "fi....mp4"

def test_elide_path_long_huge_filename_longer():
    """Test with a filename that is itself too long with default max_chars"""
    # max_chars = 45
    path = "C:/folder/" + "a" * 40 + ".mp4"
    result = elide_path(path, max_chars=45)
    name = "a" * 40 + ".mp4" # 44 chars
    # name[:45-8] = name[:37]
    assert result == ("a" * 37) + "....mp4"

def test_elide_path_smart_collapse():
    """Test that parent directories are collapsed properly"""
    path = "C:/a_very_long_directory_name_to_collapse/folder/video.mp4"
    # len(name) = 9
    # allowed_start = 45 - 9 - 3 = 33
    # path[:33] is "C:/a_very_long_directory_name_to_"
    result = elide_path(path, max_chars=45)
    assert result == "C:/a_very_long_directory_name_to_...video.mp4"
    assert len(result) == 45

def test_elide_path_missing_directories():
    """Test with just a long filename"""
    path = "a" * 50 + ".mp4"
    result = elide_path(path, max_chars=45)
    assert result == ("a" * 37) + "....mp4"
    assert len(result) == 44
