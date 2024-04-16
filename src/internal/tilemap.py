from __future__ import annotations

import json
import math
import time
from functools import lru_cache
from random import randint
from typing import TYPE_CHECKING, TypedDict, Union

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game  # from editor import Editor
    from editor import Editor

from dataclasses import dataclass

import pygame as pg

import internal.prelude as pre


@lru_cache(maxsize=None)
def calc_pos_to_loc(x: int, y: int, offset: Union[tuple[int, int], None]) -> str:
    # FIXME: named params have issue: either reduce maxsize or remove None, or change param names
    """
    calc_pos_to_loc convert position with offset to json serializable key for game level map
    Returns a string with `_lru_cache_wrapper` that is a 'Constants shared by all lru cache instances'
    # NOTE!: named params will not work with this lru function. maybe due to adding generic like `None` to handle multiple cases
    """
    if offset:
        return f"{int(x)-int(offset[0])};{int(y)-int(offset[1])}"
    return f"{int(x)};{int(y)}"


@dataclass
class TileItem:
    """TODO: create a parser to convert this data type to be json serializable"""

    kind: pre.TileKind  # use an enum or verify with field()
    variant: int
    pos: pg.Vector2  # | list[int | float] | tuple[int | float, ...]


class TileItemJSON(TypedDict):
    kind: str  # use an enum or verify with field()
    variant: int
    pos: list[int | float] | tuple[int | float, ...]


class Tilemap:
    def __init__(self, game: Game | Editor, tile_size: int = pre.TILE_SIZE) -> None:
        self.game = game
        self.tile_size = tile_size
        self.tilemap: dict[str, TileItem] = {}
        self.offgrid_tiles: list[TileItem] = []

    @lru_cache(maxsize=None)
    def tiles_around(self, pos: tuple[int, int]) -> list[TileItem]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        loc_x, loc_y = self.calc_tile_loc(pos[0], pos[1])
        return [self.tilemap[seen_location] for offset in pre.NEIGHBOR_OFFSETS if (seen_location := calc_pos_to_loc(loc_x, loc_y, offset)) and seen_location in self.tilemap]

    @lru_cache(maxsize=None)
    def physics_rects_around(self, pos: tuple[int, int]) -> list[pg.Rect]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""

        return [pg.Rect(int(tile.pos.x * self.tile_size), int(tile.pos.y * self.tile_size), self.tile_size, self.tile_size) for tile in self.tiles_around(pos) if tile.kind in pre.PHYSICS_TILES]

    # PERF: Implement flood filling feature

    def extract(self, spawners: list[tuple[str, int]]) -> list[TileItem]:
        print(f"{ __class__, spawners =}")
        return [TileItem(pre.TileKind.SPAWNERS, 0, pg.Vector2(0)) for _ in range(4)]

    def autotile(self) -> None:  # 3:04:00
        for tile in self.tilemap.values():
            if tile.kind not in pre.AUTOTILE_TYPES:
                continue

            neighbors: set[tuple[int, int]] = set()

            for shift in {(-1, 0), (1, 0), (0, -1), (0, 1)}:
                if (
                    # NOTE: `loc` should be int not floats int string e.g. `3;10` not `3.0;10.0`
                    loc := tile.pos + shift,
                    # PERF: can use -shift in offset param
                    check_loc := calc_pos_to_loc(loc.x, loc.y, None),
                ) and check_loc in self.tilemap:
                    if self.tilemap[check_loc].kind == tile.kind:  # no worry if a different variant
                        neighbors.add(shift)

            if (sorted_ngbrs := tuple(sorted(neighbors))) and sorted_ngbrs in pre.AUTOTILE_MAP:
                tile.variant = pre.AUTOTILE_MAP[sorted_ngbrs]

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        blit = surf.blit  # hack: optimization hack to stop python from initializing dot methods on each iteration in for loop
        for tile in self.offgrid_tiles:
            blit(self.game.assets.tiles[tile.kind.value][tile.variant], tile.pos - offset)

        blit = surf.blit
        xlo, ylo = self.calc_tile_loc(offset[0], offset[1])
        xhi, yhi = self.calc_tile_loc(offset[0] + surf.get_width(), offset[1] + surf.get_height())
        for x in range(xlo, xhi + 1):
            for y in range(ylo, yhi + 1):  # only draw tiles whose position is found on the screen camera offset range
                if (loc := calc_pos_to_loc(x, y, None)) and loc in self.tilemap:
                    tile = self.tilemap[loc]
                    blit(self.game.assets.tiles[tile.kind.value][tile.variant], (tile.pos * self.tile_size) - offset)

        # simple algorithm
        # blit = surf.blit
        # for loc in self.tilemap:
        #     tile = self.tilemap[loc]
        #     blit(self.game.assets.surfaces[tile.kind.value][tile.variant], (tile.pos * self.tile_size) - offset)

    def tilemap_to_json(self) -> dict[str, TileItemJSON]:
        return {key: TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant) for key, tile in self.tilemap.items()}

    def offgrid_tiles_to_json(self) -> list[TileItemJSON]:
        return [TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant) for tile in self.offgrid_tiles]

    @staticmethod
    def tilemap_json_to_dataclass(data: dict[str, TileItemJSON]) -> dict[str, TileItem]:
        return {key: TileItem(kind=pre.TileKind(tile["kind"]), pos=pg.Vector2(tile["pos"]), variant=tile["variant"]) for key, tile in data.items()}

    @staticmethod
    def offgrid_tiles_json_to_dataclass(data: list[TileItemJSON]) -> list[TileItem]:
        return [TileItem(kind=pre.TileKind(tile["kind"]), pos=pg.Vector2(tile["pos"]), variant=tile["variant"]) for tile in data]

    def save(self, path: str) -> float:
        with open(path, "w") as f:
            json.dump(dict(tile_size=self.tile_size, tilemap=self.tilemap_to_json(), offgrid=self.offgrid_tiles_to_json()), f)
            return time.time()

    def load(self, path: str) -> None:
        with open(path, "r") as f:
            map_data = json.load(f)
            self.tile_size = map_data["tile_size"]
            self.tilemap = self.tilemap_json_to_dataclass(map_data["tilemap"])
            self.offgrid_tiles = self.offgrid_tiles_json_to_dataclass(map_data["offgrid"])

    @lru_cache(maxsize=None)
    def calc_tile_loc(self, x: int | float, y: int | float) -> tuple[int, int]:
        """calc_tile_loc avoids pixel bordering zero to round to 1."""

        # HACK: passing float as x,y param to see if perf decreases
        # HACK: or round this?
        return (int(x // self.tile_size), int(y // self.tile_size))

    @staticmethod
    @lru_cache(maxsize=None)
    def generate_surf(
        count: int, color: tuple[int, int, int] = pre.BLACK, size: tuple[int, int] = (pre.TILE_SIZE, pre.TILE_SIZE), colorkey: pre.ColorValue = pre.BLACK, alpha: int = 255, variance: int = 0
    ) -> list[pg.Surface]:
        """Tip: use lesser alpha to blend with the background fill for a cohesive theme"""
        # variance (0==base_color) && (>0 == random colors)
        alpha = max(0, min(255, alpha))  # clamp from less opaque -> fully opaque
        # fill = [max(0, min(255, base + randint(-variance, variance))) for base in color] if variance else color
        fill = [max(0, min(255, base + randint(-variance, variance))) for base in color] if variance else color

        return [
            (
                surf := pg.Surface(size),
                surf.set_colorkey(colorkey),
                surf.set_alpha(alpha),
                # surf.fill((color[0] // (1 + i), int(color[1] * i * variance) % 255, color[2])),
                surf.fill(
                    pre.hsl_to_rgb(
                        h=(30 + pg.math.lerp(0.0328 * i * (1 + variance), 5, abs(math.sin(i)))),
                        s=0.045 * (0.0318 + variance),
                        l=max(0.02, (0.03 + min(0.01,(1 / (variance + 1)))) - (0.001618 * i)),
                    )
                ),
            )[0]
            # ^ after processing pipeline, select first [0] Surface in tuple
            for i in range(count)
        ]
