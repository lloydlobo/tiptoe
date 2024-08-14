# file: test_map.py

# : find src -name 'test_*.py' | entr -crs 'pytest -v -W ignore::DeprecationWarning src/test_map.py'
#
# TODO: Test: <map_level>.json should have valid spawners, pre-"complile" time
#
# When fixing a bug, add a failing test first, as a separate commit. That way
# it becomes easy to verify for anyone that test indeed fails without the
# follow up fix.
# - @matklad [Git Things](https://matklad.github.io/2023/12/31/git-things.html)


import json
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest  # pyright: ignore [reportUnusedImport]
from hypothesis import assume  # pyright: ignore [reportUnusedImport]
from hypothesis import (
    strategies as st,  # pyright: ignore [reportUnusedImport]
)

from internal.prelude import MAP_PATH


@pytest.fixture
def map_data():
    return fs_load_json_map_level("0.json")


def fs_load_json_map_level(filename: str = "0.json") -> Dict[str, Any]:
    filepath: Path = MAP_PATH / filename
    assert filepath.is_file(), f"Map file {filename} does not exist or is not a file"
    with open(filepath, 'r') as f:
        data = json.load(f)
    assert data, f"Map data is empty for file {filename}"
    return data


def test_map_structure(map_data: Dict[str, Any]):
    assert isinstance(map_data, Dict), "Map data should be a dictionary"
    assert "offgrid" in map_data, "Map data should contain 'offgrid' key"
    assert isinstance(map_data["offgrid"], list), "Offgrid data should be a list"


def test_offgrid_tiles(map_data: Dict[str, Any]):
    offgrid_tiles = map_data["offgrid"]
    for tile in offgrid_tiles:
        assert isinstance(tile, Dict), "Each offgrid tile should be a dictionary"
        assert "kind" in tile, "Each offgrid tile should have a 'kind' key"
        assert "pos" in tile, "Each offgrid tile should have a 'pos' key"
        assert "variant" in tile, "Each offgrid tile should have a 'variant' key"


def test_spawner_variants(map_data: Dict[str, Any]):
    offgrid_tiles = map_data["offgrid"]
    spawner_variants = {tile["variant"] for tile in offgrid_tiles if tile["kind"] == "spawners"}
    assert 0 in spawner_variants, "Player spawner (variant 0) should be present"
    assert 1 in spawner_variants, "Enemy spawner (variant 1) should be present"
    assert 2 in spawner_variants, "Destination flag (variant 2) should be present"
    assert 3 not in spawner_variants, "Collection flag (variant 3) should not be present"


def test_spawner_uniqueness(map_data: Dict[str, Any]):
    offgrid_tiles = map_data["offgrid"]
    spawner_variants = [tile["variant"] for tile in offgrid_tiles if tile["kind"] == "spawners"]
    # with pytest.raises(hypothesis.errors.UnsatisfiedAssumption):
    enabled = False
    if enabled:
        assume(len(spawner_variants) == len(set(spawner_variants)) and "Spawner variants should be unique")


def test_tile_positions(map_data: Dict[str, Any]):
    offgrid_tiles = map_data["offgrid"]
    for tile in offgrid_tiles:
        assert isinstance(tile["pos"], List), "Tile position should be a list"
        assert len(tile["pos"]) == 2, "Tile position should have two coordinates"
        assert all(isinstance(coord, (int, float)) for coord in tile["pos"]), "Tile coordinates should be numbers"


@pytest.mark.parametrize("filename", ["0.json", "1.json", "2.json"])
def test_multiple_map_files(filename: str):
    map_data = fs_load_json_map_level(filename)
    test_map_structure(map_data)
    test_offgrid_tiles(map_data)
    test_spawner_variants(map_data)
    test_spawner_uniqueness(map_data)
    test_tile_positions(map_data)


def test_first_draft():
    expected_offgrid_data = "[{'kind': 'spawners', 'pos': [92.5, 224.5], 'variant': 2}, {'kind': 'spawners', 'pos': [371.5, 225.0], 'variant': 1}, {'kind': 'spawners', 'pos': [219.0, 170.5], 'variant': 0}]"
    mapdata = fs_load_json_map_level("0.json")
    assert isinstance(mapdata, Dict), f"Expected: {repr(Dict)}. Actual: {Dict}"
    assert (
        mapdata["offgrid"] is not None
    ), f"Asserts that offgrid data is not 'None'. offgrid data mismatch. Expected: {expected_offgrid_data}. Actual: {mapdata['offgrid']}"
    offgrid_tiles: List[Dict[str, Any]]  # pyright: ignore [reportUnknownArgumentType]
    offgrid_tiles = mapdata["offgrid"]  # pyright: ignore [reportUnknownVariableType]
    assert (
        offgrid_tiles is not None
    ), f"Asserts that offgrid field in json file is not None. Actual: {repr(offgrid_tiles)}"  # pyright: ignore [reportUnknownArgumentType]
    assert isinstance(offgrid_tiles, List), f"Asserts offgrid data to be a list. Expected: {repr(List)}. Actual: {List}"
    for tile in offgrid_tiles:  # pyright: ignore [reportUnknownVariableType]
        assert isinstance(
            tile, Dict
        ), f"Expected: {Dict}. Actual: {type(tile)}"  # pyright: ignore [reportUnknownArgumentType]
    offgrid_len = len(offgrid_tiles)
    offgrid_spawners_variant_set: Set[Any] = {tile["variant"] for tile in offgrid_tiles if tile["kind"] == "spawners"}
    offgrid_spawners_variant_set_len = len(offgrid_spawners_variant_set)
    all_spawners_variants: Set[int] = {0, 1, 2}
    assume(
        offgrid_spawners_variant_set_len == offgrid_len
        and f"Asserts that offgrid tiles have unique spawner tile variants. Actual: {offgrid_spawners_variant_set}, All variants: {all_spawners_variants}"
    )
    assume(
        offgrid_spawners_variant_set & all_spawners_variants == all_spawners_variants
        and "Assume all spawners variant set intersects. It can fail"
    )
    assert 0 in offgrid_spawners_variant_set, f"Asserts that player spawner variant is always present"
    assert 1 in offgrid_spawners_variant_set, f"Asserts that enemy spawner variant is always present"
    assert 2 in offgrid_spawners_variant_set, f"Asserts that destination flag variant is always present"
    assert (
        3 not in offgrid_spawners_variant_set
    ), f"Asserts that collection flag variant is never present, as it is auto-generated at runtime; based on player spawners position"


# from hypothesis import given  # pyright: ignore [reportUnusedImport]
# @given(st.integers(min_value=0, max_value=2))
# def test_spawner_positions(map_data: Dict[str, Any], variant: int):
#     offgrid_tiles = map_data["offgrid"]
#     spawner_positions = [
#         tuple(tile["pos"]) for tile in offgrid_tiles if tile["kind"] == "spawners" and tile["variant"] == variant
#     ]
#     enabled = False
#     if enabled:
#         assert len(spawner_positions) == 1, f"There should be exactly one spawner of variant {variant}"

