from __future__ import annotations

from functools import lru_cache
from random import randint
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game  # from editor import Editor
    from editor import Editor

from dataclasses import dataclass

import pygame as pg

import internal.prelude as pre


@dataclass
class TileItem:
    """TODO: create a parser to convert this data type to be json serializable"""

    kind: pre.TileKind  # use an enum or verify with field()
    variant: int
    pos: pg.Vector2  # | list[int | float] | tuple[int | float, ...]


class Tilemap:
    def __init__(self, game: Game | Editor, tile_size: int = pre.TILE_SIZE) -> None:
        self.game = game
        self.tile_size = tile_size
        self.tilemap: dict[str, TileItem] = {}
        self.offgrid_tiles: list[TileItem] = []

        for i in range(20):
            self.tilemap[f"{3+i};{10}"] = TileItem(kind=pre.TileKind.STONE, variant=0, pos=pg.Vector2(3 + i, 10))  # horizontal contiguous tiles
            self.tilemap[f"{3+i};{11}"] = TileItem(kind=pre.TileKind.STONE, variant=1, pos=pg.Vector2(3 + i, 11))

        for i in range(6):
            self.tilemap[f"{7+i};{8}"] = TileItem(kind=pre.TileKind.STONE, variant=1, pos=pg.Vector2(7 + i, 8))

        for i in range(3):
            self.tilemap[f"{16+i};{7}"] = TileItem(kind=pre.TileKind.STONE, variant=0, pos=pg.Vector2(16 + i, 7))
            # self.tilemap[f"{10};{5+i}"] = TileItem(kind=pre.TileKind.STONE, variant=0, pos=pg.Vector2(10, 5 + i))  vertical contiguous tiles

        for i in range(2):
            self.tilemap[f"{20+i};{6}"] = TileItem(kind=pre.TileKind.STONE, variant=0, pos=pg.Vector2(20 + i, 6))
            self.tilemap[f"{20+i};{5}"] = TileItem(kind=pre.TileKind.STONE, variant=0, pos=pg.Vector2(20 + i, 5))

        self.tilemap[f"{20};{5}"] = TileItem(kind=pre.TileKind.PORTAL, variant=0, pos=pg.Vector2(20, 5))

    @lru_cache(maxsize=None)
    def calc_tile_loc(self, x: int | float, y: int | float) -> tuple[int, int]:
        """calc_tile_loc avoids pixel bordering zero to round to 1."""

        # HACK: passing float as x,y param to see if perf decreases
        # HACK: or round this?
        return (int(x // self.tile_size), int(y // self.tile_size))

    @lru_cache(maxsize=None)
    def tiles_around(self, pos: tuple[int, int]) -> list[TileItem]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        loc_x, loc_y = self.calc_tile_loc(pos[0], pos[1])
        return [self.tilemap[seen_location] for offset in pre.NEIGHBOR_OFFSETS if (seen_location := pre.calc_pos_to_loc(loc_x, loc_y, offset)) and seen_location in self.tilemap]

    @lru_cache(maxsize=None)
    def physics_rects_around(self, pos: tuple[int, int]) -> list[pg.Rect]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""

        return [pg.Rect(int(tile.pos.x * self.tile_size), int(tile.pos.y * self.tile_size), self.tile_size, self.tile_size) for tile in self.tiles_around(pos) if tile.kind in pre.PHYSICS_TILES]

    @staticmethod
    @lru_cache(maxsize=None)
    def generate_surf(
        count: int, color: tuple[int, int, int] = pre.BLACK, size: tuple[int, int] = (pre.TILE_SIZE, pre.TILE_SIZE), colorkey: pre.ColorValue = pre.BLACK, alpha: int = 255, variance: int = 0
    ) -> list[pg.Surface]:
        """Tip: use lesser alpha to blend with the background fill for a cohesive theme"""
        # variance (0==base_color) && (>0 == random colors)
        alpha = max(0, min(255, alpha))  # clamp from less opaque -> fully opaque
        fill = [max(0, min(255, base + randint(-variance, variance))) for base in color] if variance else color

        return [
            (
                surf := pg.Surface(size),
                surf.set_colorkey(colorkey),
                surf.set_alpha(alpha),
                surf.fill(fill),
            )[0]
            # ^ after processing pipeline, select first [0] Surface in tuple
            for _ in range(count)
        ]

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        blit = surf.blit  # hack: optimization hack to stop python from initializing dot methods on each iteration in for loop
        for tile in self.offgrid_tiles:
            blit(self.game.assets.surfaces[tile.kind.value][tile.variant], tile.pos - offset)

        blit = surf.blit
        xlo, ylo = self.calc_tile_loc(offset[0], offset[1])
        xhi, yhi = self.calc_tile_loc(offset[0] + surf.get_width(), offset[1] + surf.get_height())
        for x in range(xlo, xhi + 1):
            for y in range(ylo, yhi + 1):  # only draw tiles whose position is found on the screen camera offset range
                if (loc := pre.calc_pos_to_loc(x, y, None)) and loc in self.tilemap:
                    tile = self.tilemap[loc]
                    blit(self.game.assets.surfaces[tile.kind.value][tile.variant], (tile.pos * self.tile_size) - offset)

        # blit = surf.blit
        # for loc in self.tilemap:
        #     tile = self.tilemap[loc]
        #     blit(self.game.assets.surfaces[tile.kind.value][tile.variant], (tile.pos * self.tile_size) - offset)
