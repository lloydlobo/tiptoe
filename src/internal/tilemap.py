from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game  # from editor import Editor

from dataclasses import dataclass

import pygame as pg

from internal.prelude import NEIGHBOR_OFFSETS, PHYSICS_TILES, TILE_SIZE, TileKind, calc_pos_to_loc


@dataclass
class TileItem:
    """TODO: create a parser to convert this data type to be json serializable"""

    kind: TileKind  # use an enum or verify with field()
    variant: int
    pos: pg.Vector2  # | list[int | float] | tuple[int | float, ...]


class Tilemap:
    def __init__(self, game: Game, tile_size: int = TILE_SIZE) -> None:
        self.game = game
        self.tile_size = tile_size
        self.tilemap: dict[str, TileItem] = {}
        self.offgrid_tiles: list[TileItem] = []

        for i in range(10):
            self.tilemap[f"{3+i};{10}"] = TileItem(kind=TileKind.GRASS, variant=0, pos=pg.Vector2(3 + i, 10))  # vertical contiguous tiles
            self.tilemap[f"{10};{5+i}"] = TileItem(kind=TileKind.STONE, variant=0, pos=pg.Vector2(10, 5 + i))  # horizontal contiguous tiles

            # print(self.tiles_around(tuple(pg.Vector2((3 + i) * TILE_SIZE, 10 * TILE_SIZE))))
            # print(self.tiles_around(tuple(pg.Vector2(10 * TILE_SIZE, (5 + i) * TILE_SIZE))))
        # print(f"{self.tilemap =}")

    @lru_cache(maxsize=None)
    def calc_tile_loc(self, x: int, y: int) -> tuple[int, int]:
        """calc_tile_loc avoids pixel bordering zero to round to 1."""
        return (int(x // self.tile_size), int(y // self.tile_size))

    @lru_cache(maxsize=None)
    def tiles_around(self, pos: tuple[int, int]) -> list[TileItem]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        loc_x, loc_y = self.calc_tile_loc(pos[0], pos[1])
        return [
            self.tilemap[seen_location]
            for offset in NEIGHBOR_OFFSETS
            if (seen_location := calc_pos_to_loc(loc_x, loc_y, offset)) and seen_location in self.tilemap
        ]

    @lru_cache(maxsize=None)
    def physics_rects_around(self, pos: tuple[int, int]) -> list[pg.Rect]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        return [
            pg.Rect(int(tile.pos.x * self.tile_size), int(tile.pos.y * self.tile_size), self.tile_size, self.tile_size)
            for tile in self.tiles_around(pos)
            if tile.kind in PHYSICS_TILES
        ]

    #
    # def tiles_around(self, pos: list[int | float] | tuple[int | float, int | float]) -> list[TileItem]:
    #     tile_loc = self.calc_tile_loc(int(pos[0]), int(pos[1]))
    #     return [
    #         self.tilemap[check_loc]
    #         for offset in NEIGHBOR_OFFSETS
    #         if (check_loc := calc_pos_to_loc(tile_loc[0], tile_loc[1], offset)) and check_loc in self.tilemap
    #     ]
    #
    # def physics_rects_around(self, pos: tuple[int, int]) -> list[pg.Rect]:
    #     return [
    #         pg.Rect(int(tile.pos.x) * self.tile_size, int(tile.pos.y) * self.tile_size, self.tile_size, self.tile_size)
    #         for tile in self.tiles_around(pos)
    #         if tile.kind in PHYSICS_TILES
    #     ]

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        for tile in self.offgrid_tiles:
            surf.blit(
                self.game.assets.surfaces[tile.kind.value][tile.variant],
                (int(tile.pos.x) - offset[0], int(tile.pos.y) - offset[1]),
            )

        for loc in self.tilemap:
            tile = self.tilemap[loc]
            surf.blit(
                self.game.assets.surfaces[tile.kind.value][tile.variant],
                (int(tile.pos.x) * self.tile_size - offset[0], int(tile.pos.y) * self.tile_size - offset[1]),
            )
