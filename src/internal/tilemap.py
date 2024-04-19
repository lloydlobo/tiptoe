from __future__ import annotations

import itertools as it
import json
import sys
from collections import deque, namedtuple
from copy import deepcopy
from typing import TYPE_CHECKING, Final, Optional, TypedDict, Union

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game  # from editor import Editor
    from editor import Editor

from dataclasses import dataclass

import pygame as pg

import internal.prelude as pre


@dataclass
class TileItem:
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

    def tiles_around(self, pos: tuple[int, int]) -> list[TileItem]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        loc_x, loc_y = self.pos_as_grid_loc_tuple2(pos[0], pos[1])
        return [self.tilemap[seen_location] for offset in pre.NEIGHBOR_OFFSETS if (seen_location := calc_pos_to_loc(loc_x, loc_y, offset)) and seen_location in self.tilemap]

    def physics_rects_around(self, pos: tuple[int, int]) -> list[pg.Rect]:
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        return [pg.Rect(int(tile.pos.x * self.tile_size), int(tile.pos.y * self.tile_size), self.tile_size, self.tile_size) for tile in self.tiles_around(pos) if tile.kind in pre.PHYSICS_TILES]

    def extract(self, id_pairs: tuple[tuple[str, int], ...], keep_tile: bool = False) -> list[TileItem]:
        matches: list[TileItem] = []
        if pre.DEBUG_EDITOR_ASSERTS:  # perf: use a context manager
            GridKind = namedtuple(typename="GridKind", field_names=["offgrid", "ongrid"])
            gk: GridKind = GridKind("offgrid", "ongrid")
            q: deque[tuple[str, TileItem]] = deque()
        try:
            for tile in self.offgrid_tiles.copy():
                if pre.DEBUG_EDITOR_ASSERTS:
                    q.appendleft((gk.offgrid, tile))
                if (tile.kind.value, tile.variant) in id_pairs:
                    matches.append(deepcopy(tile))
                    if not keep_tile:
                        self.offgrid_tiles.remove(tile)
            for loc, tile in self.tilemap.items():
                if pre.DEBUG_EDITOR_ASSERTS:
                    q.appendleft((gk.ongrid, tile))
                if (tile.kind.value, tile.variant) in id_pairs:
                    matches.append(deepcopy(tile))
                    matches[-1].pos.update(matches[-1].pos.copy())  # convert to a copyable position obj if it is immutable
                    matches[-1].pos *= self.tile_size
                    if not keep_tile:
                        del self.tilemap[loc]
        except RuntimeError as e:
            if pre.DEBUG_EDITOR_ASSERTS:
                print(f"{e}:\n\twas the spawner tile placed ongrid?\n\t{q[0]}")
            print(f"{e}", sys.stderr)
            sys.exit()
        return matches

    # perf: Implement flood filling feature
    def floodfill(self, tile):
        pass

    def maybe_gridtile(self, pos: pg.Vector2) -> Optional[TileItem]:
        return self.tilemap.get(self.vec2_jsonstr(self.pos_as_grid_loc_vec2(pos)), None)

    def maybe_solid_gridtile_bool(self, pos: pg.Vector2) -> bool:
        """Return boolean if physics tile can be stepped on or None"""
        return True if (tile := self.maybe_gridtile(pos)) and (tile and tile.kind in pre.PHYSICS_TILES) else False

    def maybe_solid_gridtile(self, pos: pg.Vector2) -> Optional[TileItem]:
        """Return optional physics tile can be stepped on or None"""
        return tile if (tile := self.maybe_gridtile(pos)) and (tile and tile.kind in pre.PHYSICS_TILES) else None

    def autotile(self) -> None:
        # note: `loc` should be int not floats int string e.g. `3;10` not `3.0;10.0`
        # perf: can use -shift in offset param
        # perf: maybe use a priority queue instead of a set
        _directions: Final = ((-1, 0), (1, 0), (0, -1), (0, 1))
        neighbors: set[tuple[int, int]] = set()
        for tile in self.tilemap.values():
            if tile.kind not in pre.AUTOTILE_TYPES:
                neighbors.clear()
                continue
            for dir in _directions:
                if (loc := tile.pos + dir, check_loc := calc_pos_to_loc(loc.x, loc.y, None)) and check_loc in self.tilemap:
                    if self.tilemap[check_loc].kind == tile.kind:  # no worries if a different variant
                        neighbors.add(dir)
            if (sn := tuple(sorted(neighbors))) in pre.AUTOTILE_MAP:
                tile.variant = pre.AUTOTILE_MAP[sn]
            neighbors.clear()

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(dict(tile_size=self.tile_size, tilemap=self.tilemap_to_json(), offgrid=self.offgrid_tiles_to_json()), f)

    def load(self, path: str) -> None:
        map_data = None
        with open(path, "r") as f:
            map_data = json.load(f)
        if map_data:
            self.tile_size = map_data["tile_size"]
            self.tilemap = dict(self.tilemap_json_to_dataclass(map_data["tilemap"]))
            self.offgrid_tiles = list(self.offgrid_tiles_json_to_dataclass(map_data["offgrid"]))

    def tilemap_to_json(self) -> dict[str, TileItemJSON]:
        return {key: TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant) for key, tile in self.tilemap.items()}

    def offgrid_tiles_to_json(self) -> list[TileItemJSON]:
        return [TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant) for tile in self.offgrid_tiles]

    def pos_as_grid_loc_vec2(self, vec2: pg.Vector2) -> pg.Vector2:
        return vec2 // self.tile_size  # Vector element-wise division for efficiency

    def pos_as_grid_loc_tuple2(self, x: int | float, y: int | float) -> tuple[int, int]:
        """calc_tile_loc avoids pixel bordering zero to round to 1."""
        return (int(x // self.tile_size), int(y // self.tile_size))

    @staticmethod
    def offgrid_tiles_json_to_dataclass(data: list[TileItemJSON]):  # -> list[TileItem]:
        # print(f"{data=}")
        dataclass_data = it.starmap(TileItem, data)
        # for x in dataclass_data:
        #     print(x)
        # print(dataclass_data)
        # return dataclass_data
        return (TileItem(kind=pre.TileKind(tile["kind"]), pos=pg.Vector2(tile["pos"]), variant=tile["variant"]) for tile in data)

    @staticmethod
    def vec2_jsonstr(vec2: pg.Vector2) -> str:
        return f"{vec2.x:.0f};{vec2.y:.0f}"  # Using f-string formatting for clarity

    @staticmethod
    def tilemap_json_to_dataclass(data: dict[str, TileItemJSON]):  # -> dict[str, TileItem]
        # PERF: needs optimization. use ctx manager for generator function reading?
        return ((key, TileItem(kind=pre.TileKind(tile["kind"]), pos=pg.Vector2(tile["pos"]), variant=tile["variant"])) for key, tile in data.items())

    @staticmethod
    def generate_surf(
        count: int,
        color: tuple[int, int, int] = pre.BLACK,
        size: tuple[int, int] = (pre.TILE_SIZE, pre.TILE_SIZE),
        colorkey: pre.ColorValue = pre.BLACK,
        alpha: int = 255,
        variance: int = 0,
    ) -> list[pg.Surface]:
        """Tip: use lesser alpha to blend with the background fill for a cohesive theme high variance leads to easy detection. Lower in idle state is ideal for being camouflaged in surroundings variance (0==base_color) && (>0 == random colors)"""
        # _ = [max(0, min(255, base + randint(-variance, variance))) for base in color] if variance else color
        alpha = max(0, min(255, alpha))  # clamp from less opaque -> fully opaque
        return [
            (
                surf := pg.Surface(size),
                surf.set_colorkey(colorkey),
                # surf.set_alpha(alpha),
                surf.fill(
                    color
                    # pre.hsl_to_rgb(
                    #     h=(30 + pg.math.lerp(0.0328 * i * (1 + variance), 5, abs(math.sin(i)))),
                    #     s=0.045 * (0.0318 + variance),
                    #     l=max(0.02, (0.03 + min(0.01, (1 / (variance + 1)))) - (0.001618 * i)),
                    #     # l=max(0.02, (0.03 + min(0.01, (1 / (variance + 1)))) - (0.001618 * i)),
                    # )
                ),
            )[0]
            for i in range(count)  # after processing pipeline, select first [0] Surface in tuple
        ]

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        # hack: optimization hack to stop python from initializing dot methods on each iteration in for loop
        blit = surf.blit
        for tile in self.offgrid_tiles:
            blit(self.game.assets.tiles[tile.kind.value][tile.variant], tile.pos - offset)

        xlo, ylo = self.pos_as_grid_loc_tuple2(offset[0], offset[1])
        xhi, yhi = self.pos_as_grid_loc_tuple2(offset[0] + surf.get_width(), offset[1] + surf.get_height())
        blit = surf.blit
        for x in range(xlo, xhi + 1):
            for y in range(ylo, yhi + 1):
                # only draw tiles whose position is found on the screen camera offset range
                if (loc := calc_pos_to_loc(x, y, None)) in self.tilemap:
                    tile = self.tilemap[loc]
                    blit(self.game.assets.tiles[tile.kind.value][tile.variant], (tile.pos * self.tile_size) - offset)


def calc_pos_to_loc(x: int, y: int, offset: Union[tuple[int, int], None]) -> str:
    # FIXME: the level editor you with is this, so if we cannot change this
    """calc_pos_to_loc convert position with offset to json serialise-able key string for game level map"""
    return f"{int(x)-int(offset[0])};{int(y)-int(offset[1])}" if offset else f"{int(x)};{int(y)}"
