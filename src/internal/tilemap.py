from __future__ import annotations

import itertools as it
import json
from collections.abc import Iterator
from copy import deepcopy
from functools import partial
from pathlib import Path
from pprint import pprint
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Final,
    Iterable,
    List,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
    Set,
    Tuple,
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
pos_to_loc_nooffset_partialfn: partial[str] = partial(pos_to_loc, offset=None)


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

        self.cur_level_map_dimension = (pre.DIMENSIONS_HALF[0], pre.DIMENSIONS_HALF[1])

        # constants
        self._autotile_map: Final = pre.AUTOTILE_MAP  # 9 cells
        self._autotile_types: Final = pre.AUTOTILE_TYPES
        self._autotile_horizontal_map: Final = pre.AUTOTILE_HORIZONTAL_MAP  # 3 cells
        self._autotile_horizontal_types: Final = pre.AUTOTILE_HORIZONTAL_TYPES
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

        # PERF: fix input map data JSON to avoiud having physics tiles as offgrid tile. can reduce checks inside for loop.
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

    def extract(self, id_pairs: Sequence[Tuple[str, int]], keep: bool = False) -> List[TileItem]:
        matches: List[TileItem] = []

        for tile in self.offgrid_tiles.copy():
            if (tile.kind.value, tile.variant) in id_pairs:
                matches.append(deepcopy(tile))
                if not keep:
                    self.offgrid_tiles.remove(tile)

        for loc, tile in self.tilemap.items():
            if (tile.kind.value, tile.variant) in id_pairs:

                # make clean copy of tile data, to avoid modification to original reference
                #   deepcopy does the next 2 things
                #     matches.append(tile.copy())
                #     # convert to a copyable position obj if it is immutable
                #     matches[-1].pos.update(matches[-1].pos.copy())
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

    def autotile(self) -> None:
        directions_matrix: Final = ((-1, 0), (1, 0), (0, -1), (0, 1))
        directions_horizontal: Final = ((-1, 0), (1, 0))
        _directions_vertical: Final = ((0, -1), (0, 1))

        def sort_key(item: TileItem) -> str:
            if item.kind in self._autotile_types:
                return "matrix"
            elif item.kind in self._autotile_horizontal_types:
                return "horizontal"
            else:
                return "none"

        tiles = self.tilemap.values()
        sorted_tiles = sorted(tiles, key=lambda item: item.kind.value)
        grouped_tiles = {kind: list(items) for kind, items in it.groupby(sorted_tiles, key=sort_key)}

        none_tiles = grouped_tiles.get("none", None)
        assert none_tiles is None, f"want no tiles to be grouped in none key. got {none_tiles}"

        for tile in grouped_tiles["matrix"]:
            neighbors = set(
                (x, y)
                for (x, y) in directions_matrix
                if (
                    ngbr_loc := f"{int(tile.pos.x+x)};{int(tile.pos.y+y)}",
                    item := self.tilemap.get(ngbr_loc, None),
                )
                and item
                and item.kind == tile.kind
            )
            if (sorted_ngbrs := tuple(sorted(neighbors))) in self._autotile_map:
                tile_loc = f"{int(tile.pos.x)};{int(tile.pos.y)}"
                self.tilemap[tile_loc].variant = self._autotile_map[sorted_ngbrs]

        for tile in grouped_tiles["horizontal"]:
            neighbors = set(
                (x, y)
                for (x, y) in directions_horizontal
                if (
                    ngbr_loc := f"{int(tile.pos.x+x)};{int(tile.pos.y+y)}",
                    item := self.tilemap.get(ngbr_loc, None),
                )
                and item
                and item.kind == tile.kind
            )
            if (sorted_ngbrs := tuple(sorted(neighbors))) in self._autotile_horizontal_map:
                tile_loc = f"{int(tile.pos.x)};{int(tile.pos.y)}"
                self.tilemap[tile_loc].variant = self._autotile_horizontal_map[sorted_ngbrs]

        if 0:  # old code works and is simple
            neighbors: set[tuple[int, int]] = set()
            for tile in self.tilemap.values():
                if tile.kind in self._autotile_types:
                    for dir in directions_matrix:
                        loc = tile.pos + dir
                        if (check_loc := pos_to_loc_nooffset_partialfn(loc.x, loc.y)) in self.tilemap:
                            if self.tilemap[check_loc].kind == tile.kind:  # no worries if a different variant
                                neighbors.add(dir)
                    sn = tuple(sorted(neighbors))
                    if sn in self._autotile_map:
                        tile.variant = self._autotile_map[sn]
                    neighbors.clear()
                elif tile.kind in self._autotile_horizontal_types:
                    for dir in directions_horizontal:
                        loc = tile.pos + dir
                        if (check_loc := pos_to_loc_nooffset_partialfn(loc.x, loc.y)) in self.tilemap:
                            if self.tilemap[check_loc].kind == tile.kind:  # no worries if a different variant
                                neighbors.add(dir)
                    sorted_ngbrs = tuple(sorted(neighbors))
                    if sorted_ngbrs in self._autotile_horizontal_map:
                        tile.variant = self._autotile_horizontal_map[sorted_ngbrs]
                    neighbors.clear()

    def save(self, path: str | Path) -> None:
        """Save the current level data to the specified path."""
        disp_w, disp_h = pre.DIMENSIONS_HALF
        map_w, map_h = self._calculate_loaded_level_map_dimension()
        map_dimension = {"w": max(disp_w, map_w), "h": max(disp_h, map_h)}

        data = {
            "tile_size": self.tilesize,
            "map_dimension": map_dimension,
            "tilemap": self.tilemap_to_json(),
            "offgrid": self.offgrid_tiles_to_json(),
        }

        path = Path(path)
        with open(path, "w") as f:
            json.dump(data, f)

    def load(self, path: str | Path) -> None:
        """Load the level data from the specified path."""
        path = Path(path)
        with open(path, "r") as f:
            map_data = json.load(f)

        self.tilesize = map_data["tile_size"]
        if pre.DEBUG_GAME_ASSERTS:
            assert isinstance(self.tilesize, int), f"want int got. {type(self.tilesize)}"

        self.offgrid_tiles = set(self.offgrid_tiles_json_to_dataclass(map_data["offgrid"]))
        self.tilemap = dict(self.tilemap_json_to_dataclass(map_data["tilemap"]))

        disp_w, disp_h = pre.DIMENSIONS_HALF  # see if it is in multiples after adjusting.
        if (map_dimension := map_data.get("map_dimension", None)) and isinstance(map_dimension, Dict):
            map_w_, map_h_ = map_dimension.get("w"), map_dimension.get("h")  # pyright: ignore
            if isinstance(map_w_, int) and isinstance(map_h_, int):
                self.cur_level_map_dimension = max(disp_w, map_w_), max(disp_h, map_h_)
                return

        map_w, map_h = self._calculate_loaded_level_map_dimension()
        self.cur_level_map_dimension = (max(disp_w, map_w), max(disp_h, map_h))  # NOTE: adjust map size based on preset screen resolution sizes defined in src/internal/prelude.py

    def _calculate_loaded_level_map_dimension(self) -> Tuple[int, int]:
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for loc in self.tilemap:
            x, y = map(int, loc.split(";", 1))
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

        seen_w = abs(min_x) + abs(max_x)
        seen_h = abs(min_y) + abs(max_y)
        map_w = int(seen_w * self.tilesize)
        map_h = int(seen_h * self.tilesize)

        return map_w, map_h

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
        return (TileItem(kind=pre.TileKind(tile["kind"]), pos=pg.Vector2(tile["pos"]), variant=tile["variant"]) for tile in data)

    @staticmethod
    def vec2_jsonstr(vec2: pg.Vector2) -> str:
        return f"{int(vec2.x)};{int(vec2.y)}"

    @staticmethod
    def tilemap_json_to_dataclass(data: Mapping[str, TileItemJSON]) -> Iterator[tuple[str, TileItem]]:
        return ((key, TileItem(kind=pre.TileKind(tile["kind"]), pos=pg.Vector2(tile["pos"]), variant=tile["variant"])) for key, tile in data.items())

    # FIXME: This is invalid for all except bottom spike orientation after
    # using actual sprites and not generative pygame Surfaces
    @classmethod
    def spawn_spikes(cls, spikes: Sequence[TileItem]) -> Iterator[pg.Rect]:
        """Return a generator iterator of spike rects hitboxes from a list of spike tile items.
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
