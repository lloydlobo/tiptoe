"""
DOD
```cpp

// Reference:
// - CppCon 2014: Mike Acton "Data-Oriented Design and C++"

// 12 bytes * count(32) -> 384 == 64 * 6
struct FooUpdateIn {
    float m_velocity[2];
    float m_foo;
}

// 4 bytes * count(32) -> 128 == 64 * 2
struct FooUpdateOut {
    float m_foo;
}

// (6/32) == ~5.33 loop/cache line
// Sqrt + math == ~40 * 5.33 == 213.33 cycles/cache line + streaming prefetch bonus
void UpdateFoos(const FooUpdateIn* in, size_t count, FooUpdateOut* out, float f)
{
    for (size t i = 0; i < count; ++i) {
        float mag = sqrtf(
            in[i].m_velocity[0] * in[i].m_velocity[0] + 
            in[i].m_velocity[1] * in[i].m_velocity[1]);
        out[i].m_foo = in[i].m_foo + mag * f;
    }
}
```
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict, deque, namedtuple
from collections.abc import Iterator
from copy import deepcopy
from functools import partial
from typing import (
    TYPE_CHECKING,
    Final,
    Iterable,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
    TypedDict,
    Union,
)


if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game  # from editor import Editor
    from editor import Editor

from dataclasses import dataclass

import pygame as pg

import internal.prelude as pre


def pos_to_loc(x: int | float, y: int | float, offset: Union[tuple[int | float, int | float], None]) -> str:
    """calc_pos_to_loc convert position with offset to json serialise-able key
    string for game level map"""
    # NOTE: the level editor uses this, so cannot change this, without updating the saved map data
    return f"{int(x)-int(offset[0])};{int(y)-int(offset[1])}" if offset else f"{int(x)};{int(y)}"


pos_to_loc_partial: partial[str] = partial(pos_to_loc)
pos_to_loc_wo_offset_partial: partial[str] = partial(pos_to_loc, offset=None)


@dataclass
class TileItem:
    kind: pre.TileKind  # use an enum or verify with field()
    variant: int
    pos: pg.Vector2

    def __hash__(self) -> int:
        return hash((self.kind, self.variant, self.pos.x, self.pos.y))

    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, TileItem):
            return False
        return (self.kind, self.variant, self.pos) == (other.kind, other.variant, other.pos)


class TileItemJSON(TypedDict):
    kind: str  # use an enum or verify with field()
    variant: int
    pos: list[int | float] | tuple[int | float, ...]


class Tilemap:
    def __init__(self, game: Game | Editor, tile_size: int = pre.TILE_SIZE) -> None:
        self.game = game
        self.offgrid_tiles: set[TileItem] = set()  # PERF: use set,list,arrays?
        self.tilesize: int = tile_size
        self.tilemap: dict[str, TileItem] = {}
        # self.offgrid_tiles.add(TileItem(pre.TileKind.STONE, 0, pg.Vector2(0, 0)))

        # derived local like variables
        self.game_assets_tiles = self.game.assets.tiles
        _game_display_rect = self.game.display.get_rect()
        self.dimensions: Final = pg.Vector2(_game_display_rect.w, _game_display_rect.h)
        # ^ hack: this can be an issue if screen is resized!!!!

        # constants
        self._autotile_map: Final = pre.AUTOTILE_MAP  # 9 cells
        self._autotile_types: Final = pre.AUTOTILE_TYPES
        self._autotile_horizontal_map: Final = pre.AUTOTILE_HORIZONTAL_MAP  # 3 cells
        self._autotile_horizontal_types: Final = pre.AUTOTILE_TYPES
        self._neighbour_offsets: Final = pre.NEIGHBOR_OFFSETS
        self._physics_tiles: Final = pre.PHYSICS_TILES
        self._loc_format = f"{{}};{{}}"  # Pre-calculate string format

        # partial functions
        self._locfmt_p_fn: Final = partial(f"{{}};{{}}".format)
        self._locfmt_p_fn.__doc__ = "This partial function takes x and y integers and serializes into json map_data dictionary keys."
        self._pg_rect_p_fn = partial(pg.Rect)
        self._pg_rect_p_fn.__doc__ = "This partial function takes pygame Rect style object parameters and returns a Rect."

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        """
        # - Optimization hack to stop python from initializing dot methods on each iteration in for loop or use without functool.partial e.g. `blit = surf.blit`
        # - Minor optimization: Pre-format string for potential slight speedup during loop iterations. F-strings are generally preferred for readability.
        # - draw tiles only if its position is in camera range
        """

        # PERF: fix input map data JSON to avoiud having physics tiles as
        # offgrid tile. can reduce checks inside for loop.
        # And USE SPIKES as non-physics tile!!!! as now they are used ongrid

        blit_partial = partial(surf.blit)

        for tile in self.offgrid_tiles:
            surfaces = self.game_assets_tiles[tile.kind.value]
            if surfaces and tile.variant < len(surfaces):
                blit_partial(surfaces[tile.variant], tile.pos - offset)

        xlo, ylo = self.pos_as_grid_loc_tuple2(offset[0], offset[1])
        xhi, yhi = self.pos_as_grid_loc_tuple2(offset[0] + surf.get_width(), offset[1] + surf.get_height())

        for x in range(xlo, xhi + 1):
            for y in range(ylo, yhi + 1):
                if (loc := self._loc_format.format(int(x), int(y))) in self.tilemap:
                    tile = self.tilemap[loc]
                    surfaces = self.game_assets_tiles[tile.kind.value]
                    if surfaces and tile.variant < len(surfaces):
                        blit_partial(surfaces[tile.variant], (tile.pos * self.tilesize) - offset)

    def tiles_around(self, pos: tuple[int, int]) -> Iterable[TileItem]:
        return (
            self.tilemap[seen_loc]
            for ofst in self._neighbour_offsets
            if (
                loc := self.pos_as_grid_loc_tuple2(*pos),
                seen_loc := f"{int(loc[0])-int(ofst[0])};{int(loc[1])-int(ofst[1])}",
            )
            and seen_loc in self.tilemap
        )

    def physics_rects_around(self, pos: tuple[int, int]) -> Iterable[pg.Rect]:
        size = self.tilesize
        return (
            self._pg_rect_p_fn(
                tile.pos.x * size,
                tile.pos.y * size,
                size,
                size,
            )
            for tile in self.tiles_around(pos)
            if tile.kind in self._physics_tiles
        )

    def extract(self, id_pairs: Sequence[tuple[str, int]], keep: bool = False) -> list[TileItem]:
        matches: list[TileItem] = []
        for tile in self.offgrid_tiles.copy():
            if (tile.kind.value, tile.variant) in id_pairs:
                matches.append(deepcopy(tile))
                if not keep:
                    self.offgrid_tiles.remove(tile)

        for loc, tile in self.tilemap.items():
            if (tile.kind.value, tile.variant) in id_pairs:
                # make clean copy of tile data, to avoid modification to original reference
                # deepcopy does the next 2 things
                #   matches.append(tile.copy())
                #   matches[-1].pos.update(matches[-1].pos.copy())  # convert to a copyable position obj if it is immutable
                matches.append(deepcopy(tile))

                # convert to pixel coordinates
                matches[-1].pos *= self.tilesize

                if not keep:
                    del self.tilemap[loc]
        return matches

    def in_tilemap(self, gridpos: tuple[int | float, int | float]) -> bool:
        """
        in_tilemap checks whether the position is inside the tilemap.
        Useful for flood fill to aid in auto tiling
        Note: Ported from DaFluffyPotato's tilemap.py
        """
        dimensions_r = self._pg_rect_p_fn(0, 0, self.dimensions.x, self.dimensions.y)
        return dimensions_r.collidepoint(*gridpos)

    # note: `loc` should be int not floats int string e.g. `3;10` not `3.0;10.0`
    # perf: can use -shift in offset param
    # perf: maybe use a priority queue instead of a set
    # note: `loc` should be int not floats int string e.g. `3;10` not `3.0;10.0`
    # perf: can use -shift in offset param
    # perf: maybe use a priority queue instead of a set

    def autotile(self) -> None:
        _directions: Final = ((-1, 0), (1, 0), (0, -1), (0, 1))
        _directions_horizontal: Final = ((-1, 0), (1, 0))
        neighbors: set[tuple[int, int]] = set()

        for tile in self.tilemap.values():
            if tile.kind in self._autotile_types:
                for dir in _directions:
                    loc = tile.pos + dir
                    if (check_loc := pos_to_loc_wo_offset_partial(loc.x, loc.y)) in self.tilemap:
                        if self.tilemap[check_loc].kind == tile.kind:  # no worries if a different variant
                            neighbors.add(dir)

                sn = tuple(sorted(neighbors))
                if sn in self._autotile_map:
                    tile.variant = self._autotile_map[sn]
                neighbors.clear()
            elif tile.kind not in self._autotile_horizontal_types:
                for dir in _directions_horizontal:
                    loc = tile.pos + dir
                    if (check_loc := pos_to_loc_wo_offset_partial(loc.x, loc.y)) in self.tilemap:
                        if self.tilemap[check_loc].kind == tile.kind:  # no worries if a different variant
                            neighbors.add(dir)
                sorted_ngbrs = tuple(sorted(neighbors))
                if sorted_ngbrs in self._autotile_horizontal_map:
                    tile.variant = self._autotile_horizontal_map[sorted_ngbrs]
                neighbors.clear()

    def save(self, path: str) -> None:
        # TODO: convert path type from str to use Path
        with open(path, "w") as f:
            json.dump(
                dict(tile_size=self.tilesize, tilemap=self.tilemap_to_json(), offgrid=self.offgrid_tiles_to_json()),
                f,
            )

    def load(self, path: str) -> None:
        # TODO: convert path type from str to use Path
        map_data = None
        with open(path, "r") as f:
            map_data = json.load(f)
        if map_data:
            self.tilesize = map_data["tile_size"]
            if pre.DEBUG_GAME_ASSERTS:
                assert isinstance(self.tilesize, int), f"want int got. {type(self.tilesize)}"
            self.tilemap = dict(self.tilemap_json_to_dataclass(map_data["tilemap"]))
            self.offgrid_tiles = set(self.offgrid_tiles_json_to_dataclass(map_data["offgrid"]))

    def maybe_gridtile(self, pos: pg.Vector2) -> Optional[TileItem]:
        return self.tilemap.get(self.vec2_jsonstr(self.pos_as_grid_loc_vec2(pos)), None)

    def maybe_solid_gridtile_bool(self, pos: pg.Vector2) -> bool:
        """Return boolean if physics tile can be stepped on or None"""
        return True if (tile := self.maybe_gridtile(pos)) and (tile and tile.kind in self._physics_tiles) else False

    def maybe_solid_gridtile(self, pos: pg.Vector2) -> Optional[TileItem]:
        """Return optional physics tile can be stepped on or None"""
        return tile if (tile := self.maybe_gridtile(pos)) and (tile and tile.kind in self._physics_tiles) else None

    def tilemap_to_json(self) -> dict[str, TileItemJSON]:
        return {key: TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant) for key, tile in self.tilemap.items()}

    def offgrid_tiles_to_json(self) -> list[TileItemJSON]:
        return [TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant) for tile in self.offgrid_tiles]

    def pos_as_grid_loc_vec2(self, vec2: pg.Vector2) -> pg.Vector2:
        return vec2 // self.tilesize  # Vector element-wise division for efficiency

    def pos_as_grid_loc_tuple2(self, x: int | float, y: int | float) -> tuple[int, int]:
        """calc_tile_loc avoids pixel bordering zero to round to 1."""
        return (int(x // self.tilesize), int(y // self.tilesize))

    @staticmethod
    def offgrid_tiles_json_to_dataclass(data: Sequence[TileItemJSON]) -> Iterator[TileItem]:
        return (
            TileItem(
                kind=pre.TileKind(tile["kind"]),
                pos=pg.Vector2(tile["pos"]),
                variant=tile["variant"],
            )
            for tile in data
        )

    @staticmethod
    def vec2_jsonstr(vec2: pg.Vector2) -> str:
        # return f"{vec2.x:.0f};{vec2.y:.0f}"  # Using f-string formatting for clarity
        return f"{int(vec2.x)};{int(vec2.y)}"

    @staticmethod
    def tilemap_json_to_dataclass(data: Mapping[str, TileItemJSON]) -> Iterator[tuple[str, TileItem]]:
        return (
            (
                key,
                TileItem(
                    kind=pre.TileKind(tile["kind"]),
                    pos=pg.Vector2(tile["pos"]),
                    variant=tile["variant"],
                ),
            )
            for key, tile in data.items()
        )

    @classmethod
    def spawn_spikes(cls, spikes: Sequence[TileItem]) -> Iterator[pg.Rect]:
        """Return a generator iterator of spike rects hitboxes from a list of
        spike tile items.

        Note: Hardcode hit box based on the location offset by 4 from top-left to each right and bottom
        """

        # xgrace: left and right. 12 width safe == 4 width danger on x-axis
        # ygrace: top and bottom. 12 height safe == 4 height danger on y-axis
        xgrace, _ = 4 + 4, 4 + 4

        # based on orientation of spike tile
        horzsize = (16, 6)  # w,h
        vertsize = (6, 16)  # w,h

        def spikerect(x: int | float, y: int | float, variant: int):
            match variant:
                # fmt: off
                case 0:  # bottom
                    return pg.Rect(x + xgrace / 2, y + (pre.TILE_SIZE - horzsize[1]), horzsize[0] - xgrace, horzsize[1])
                case 1:  # top
                    return pg.Rect(x + xgrace / 2, y, horzsize[0] - xgrace, horzsize[1])
                case 2:  # left
                    return pg.Rect(x, y + xgrace / 2, vertsize[0], vertsize[1] - xgrace)
                case 3:  # right
                    return pg.Rect(x + (pre.TILE_SIZE - vertsize[0]), y + xgrace / 2, vertsize[0], vertsize[1] - xgrace)
                # fmt: on
                case _:
                    raise ValueError(f"unreachable value. invalid variant {variant=}")

        return (spikerect(spike.pos.x, spike.pos.y, spike.variant) for spike in spikes)
