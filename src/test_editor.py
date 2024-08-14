# file: test_editor.py

# Usage:
#   fd -e py . | entr -cprs make -j4 test

import random
import time
import unittest
from typing import List, Set, Tuple

import pygame
import pytest
from pygame.event import post

from editor import Editor
from internal.prelude import TILE_SIZE, Number, TileKind
from internal.tilemap import TileItem, Tilemap


class TestEditor(unittest.TestCase):
    def setUp(self) -> None:
        if pygame.get_init():
            pygame.quit()
        return super().setUp()

    def tearDown(self) -> None:
        if pygame.get_init():
            pygame.quit()
        return super().tearDown()

    def test_editor_init_with_level_id(self):
        import editor
        from game import quit_exit

        ed_with_level_id = editor.Editor(level_id=1)
        self.assertEqual(ed_with_level_id.level, 1)
        with self.assertRaises(SystemExit):
            quit_exit()

    def test_editor_init_without_level_id(self):
        import editor
        from game import quit_exit

        ed_without_level_id = editor.Editor(level_id=None)
        self.assertEqual(ed_without_level_id.level, 0)
        with self.assertRaises(SystemExit):
            quit_exit()


# def make_tilemap() -> Tilemap:
#     editor = Editor(level_id=0)
#     return Tilemap(game=editor, tile_size=TILE_SIZE)
#
#
# def create_tilemap(variants: Set[int]) -> Tilemap:
#     tilemap = make_tilemap()
#     # tilemap.tilemap


def create_offgrid_tiles(variants: Set[int]) -> Set[TileItem]:
    Vec2: type = pygame.Vector2
    assert variants, f"Should have positive amount of variants. Actual: '{len(variants)}'."
    offgrid_tiles: Set[TileItem] = set()
    positions_seen: Set[Tuple[Number, Number]] = set()
    for variant in variants:
        while (pos := (random.random() * 16, random.random() * 16)) and pos not in positions_seen:
            offgrid_tiles.add(TileItem(pos=Vec2(pos[0], pos[1]), kind=TileKind.SPAWNERS, variant=variant))
            positions_seen.add(pos)  # sort it?
    expected, actual = len(variants), len(offgrid_tiles)
    errmsg = f"Failed to create same count of offgrid tiles given the input variants. Expected: '{expected}', Actual: '{actual}'."
    assert actual == expected, errmsg
    return offgrid_tiles


# @pytest.mark.parametrize("variants, expected", [
#     ([0, 1, 2, 1], (True, "")),
#     ([], (False, "Map should contain at least one offgrid tile with spawners")),
#     ([0, 0, 1], (False, "There should be exactly one player spawner (variant 0)")),
#     ([0, 2], (False, "There should be atleast one enemy spawner (variant 1)")),
#     ([0, 1, 2, 2], (False, "Spawner portal should not have multiple instances (variant 2)")),
#     ([0, 1, 3], (False, "There should be no 'flag is collect' spawner (variant 3)")),
# ])
# def test_validate_unique_spawners(variants, expected):
#     assert validate_unique_spawners(create_tilemap(variants)) == expected
#


if __name__ == "__main__":
    from pathlib import Path

    FILENAME: str = Path(__file__).name
    print(f"{time.process_time():.5f}", "[debug]", time.monotonic_ns(), time.ctime(), f"in {FILENAME}")

    unittest.main()
