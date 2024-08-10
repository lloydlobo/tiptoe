# file: test_map.py
#
# : find src -name 'test_*.py' | entr -crs 'pytest -W ignore::DeprecationWarning src/test_map.py'

import re  # pyright: ignore [reportUnusedImport]
from pathlib import Path

import pygame as pg  # pyright: ignore [reportUnusedImport]
import pytest  # pyright: ignore [reportUnusedImport]

from internal.assets import (
    Assets,  # pyright: ignore [reportUnusedImport]
)
from internal.prelude import MAP_PATH


# TODO: Test: <map_level>.json should have valid spawners, pre-"complile" time

# When fixing a bug, add a failing test first, as a separate commit. That way
# it becomes easy to verify for anyone that test indeed fails without the
# follow up fix.
# - @matklad [Git Things](https://matklad.github.io/2023/12/31/git-things.html)


def fs_load_json_map_level(filename: str = "0.json"):
    assert filename.endswith(".json")
    assert MAP_PATH.is_dir()
    filepath: Path = MAP_PATH / filename
    assert filepath.exists()
    assert filepath.is_file()
    with open(filepath, 'r') as f:
        data = f.read()
    return data


def test_map_json():
    map_data = fs_load_json_map_level("0.json")
    # with pytest.raises(AssertionError, match=re.escape("test should fail! map_data cannot be \"\"")):
    #     assert map_data == "", f"test should fail! map_data cannot be \"\": {map_data = }"
    assert map_data != "", f"Expected map data to not be empty. Actual: {map_data}"
