from __future__ import annotations

import itertools as it
import json
import sys
from collections import defaultdict, deque, namedtuple
from copy import deepcopy
from functools import partial, reduce
from typing import (
    TYPE_CHECKING,
    Final,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
    TypedDict,
    Union,
)


if (
    TYPE_CHECKING
):  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game  # from editor import Editor
    from editor import Editor

from dataclasses import dataclass

import pygame as pg

import internal.prelude as pre


def pos_to_loc(
    x: int | float, y: int | float, offset: Union[tuple[int | float, int | float], None]
) -> str:  # FIXME: the level editor you with is this, so if we cannot change this
    """calc_pos_to_loc convert position with offset to json serialise-able key string for game level map"""
    return f"{int(x)-int(offset[0])};{int(y)-int(offset[1])}" if offset else f"{int(x)};{int(y)}"


pos_to_loc_partial: partial[str] = partial(pos_to_loc)
pos_to_loc_wo_offset_partial: partial[str] = partial(pos_to_loc, offset=None)


@dataclass
class TileItem:
    kind: pre.TileKind  # use an enum or verify with field()
    variant: int
    pos: pg.Vector2  # | list[int | float] | tuple[int | float, ...]

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
        self.offgrid_tiles: set[TileItem] = set()  # PERF: use set?
        self.tile_size = tile_size
        self.tilemap: dict[str, TileItem] = {}  # use defaultdict?
        # print(self.offgrid_tiles)
        self.offgrid_tiles.add(TileItem(pre.TileKind.STONE, 0, pg.Vector2(0, 0)))
        # print(self.offgrid_tiles)

        # derived local like variables
        self.game_assets_tiles = self.game.assets.tiles
        _game_display_rect = self.game.display.get_rect()
        self._dimensions: Final = (
            _game_display_rect.w,
            _game_display_rect.h,
        )  # hack: this can be an issue if screen is resized!!!!

        # constants
        self._autotile_map: Final = pre.AUTOTILE_MAP
        self._autotile_types: Final = pre.AUTOTILE_TYPES
        self._neighbour_offsets: Final = pre.NEIGHBOR_OFFSETS
        self._physics_tiles: Final = pre.PHYSICS_TILES

        # partial functions
        self._locfmt_p_fn: Final = partial(f"{{}};{{}}".format)
        self._locfmt_p_fn.__doc__ = "This partial function takes x and y integers and serializes into json map_data dictionary keys."
        self._pg_rect_p_fn = partial(pg.Rect)
        self._pg_rect_p_fn.__doc__ = (
            "This partial function takes pygame Rect style object parameters and returns a Rect."
        )

    def tiles_around(self, pos: tuple[int, int]):
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        return (
            self.tilemap[seen_loc]
            for ofst in self._neighbour_offsets
            if (
                loc := self.pos_as_grid_loc_tuple2(*pos),
                seen_loc := f"{int(loc[0])-int(ofst[0])};{int(loc[1])-int(ofst[1])}",
            )
            and seen_loc in self.tilemap
        )

    def physics_rects_around(self, pos: tuple[int, int]):
        """note: need hashable position so pygame.Vector2 won't work for input parameter"""
        size = self.tile_size
        return (
            self._pg_rect_p_fn(
                (tile.pos.x * size),
                (tile.pos.y * size),
                size,
                size,
            )
            for tile in self.tiles_around(pos)
            if tile.kind in self._physics_tiles
        )

    # def extract(self, id_pairs: list[tuple[str, int]], keep: bool = False) -> list[TileItem]:
    # def extract(self, id_pairs: MutableSequence[tuple[str, int]], keep: bool = False) -> list[TileItem]:
    def extract(self, id_pairs: Sequence[tuple[str, int]], keep: bool = False) -> list[TileItem]:
        matches: list[TileItem] = []

        if pre.DEBUG_EDITOR_ASSERTS:  # perf: use a context manager
            GridKind = namedtuple(typename="GridKind", field_names=["offgrid", "ongrid"])  # type: ignore
            gk = GridKind("offgrid", "ongrid")
            q = deque()  # type: ignore

        try:  # use itertools.chain?
            for tile in self.offgrid_tiles.copy():
                if pre.DEBUG_EDITOR_ASSERTS:
                    q.appendleft((gk.offgrid, tile))  # type: ignore
                if (tile.kind.value, tile.variant) in id_pairs:
                    matches.append(deepcopy(tile))
                    if not keep:
                        self.offgrid_tiles.remove(tile)

            for loc, tile in self.tilemap.items():
                if pre.DEBUG_EDITOR_ASSERTS:
                    q.appendleft((gk.ongrid, tile))  # type: ignore
                if (tile.kind.value, tile.variant) in id_pairs:
                    matches.append(
                        deepcopy(tile)
                    )  # make clean copy of tile data, to avoid modification to original reference
                    # deepcopy does the next 2 things
                    #   matches.append(tile.copy())
                    #   matches[-1].pos.update(matches[-1].pos.copy())  # convert to a copyable position obj if it is immutable
                    matches[-1].pos *= self.tile_size  # convert to pixel coordinates
                    if not keep:
                        del self.tilemap[loc]
        except RuntimeError as e:
            if pre.DEBUG_EDITOR_ASSERTS:
                print(f"{e}:\n\twas the spawner tile placed ongrid?\n\t{q[0]}")  # type: ignore

            print(f"{e}", sys.stderr)
            sys.exit()

        return matches

    def in_tilemap(self, gridpos: tuple[int | float, int | float]) -> bool:
        """
        in_tilemap checks whether the position is inside the tilemap.
        Useful for flood fill to aid in auto tiling
        Note: Ported from DaFluffyPotato's tilemap.py
        """
        dimensions_r = self._pg_rect_p_fn(0, 0, *self._dimensions)
        return dimensions_r.collidepoint(*gridpos)

    def floodfill(self, tile):  # type: ignore
        pass

    # note: `loc` should be int not floats int string e.g. `3;10` not `3.0;10.0`
    # perf: can use -shift in offset param
    # perf: maybe use a priority queue instead of a set
    def autotile(self) -> None:
        # note: `loc` should be int not floats int string e.g. `3;10` not `3.0;10.0`
        # perf: can use -shift in offset param
        # perf: maybe use a priority queue instead of a set
        _directions: Final = ((-1, 0), (1, 0), (0, -1), (0, 1))
        neighbors: set[tuple[int, int]] = set()

        for tile in self.tilemap.values():
            if tile.kind not in self._autotile_types:
                neighbors.clear()
                continue
            for dir in _directions:
                if (
                    loc := tile.pos + dir,
                    check_loc := pos_to_loc_wo_offset_partial(loc.x, loc.y),
                ) and check_loc in self.tilemap:
                    if (
                        self.tilemap[check_loc].kind == tile.kind
                    ):  # no worries if a different variant
                        neighbors.add(dir)
            if (sn := tuple(sorted(neighbors))) in self._autotile_map:
                tile.variant = self._autotile_map[sn]
            neighbors.clear()

    # NOTE: unstable doesn't work
    def _autotile_v2(self) -> None:
        # pprint(self.tilemap, compact=False, width=300)
        DIRECTIONS: Final = ((-1, 0), (1, 0), (0, -1), (0, 1))

        neighbors: set[tuple[int, int]] = set()
        tile_neighbors: defaultdict[tuple[int | float, int | float], set[tuple[int, int]]] = (
            defaultdict(set)
        )  # : defaultdict[pg.Vector2, set[tuple[int,int]]

        for tile in self.tilemap.values():

            if tile.kind not in self._autotile_types:
                neighbors.clear()
                continue

            tile_pos: tuple[int, int] = int(tile.pos.x), int(tile.pos.y)

            for dx, dy in DIRECTIONS:
                ngbr_loc = tile_pos[0] + dx, tile_pos[1] + dy
                if (check_loc := self._locfmt_p_fn(ngbr_loc[0], ngbr_loc[1])) in self.tilemap:
                    if (
                        ngbr_tile := self.tilemap[check_loc]
                    ) and ngbr_tile.kind == tile.kind:  # can be any different variant
                        neighbors.add((dx, dy))
                        tile_neighbors[ngbr_loc].add((-dx, -dy))

            if (sorted_ngbrs := tuple(sorted(neighbors))) in self._autotile_map:
                # print(f"OG:::{sorted_ngbrs}")
                tile.variant = self._autotile_map[sorted_ngbrs]

            for ngbr_loc, directions in tile_neighbors.items():
                # print(ngbr_loc, directions)
                if len(directions) > 1:
                    ngbr_tile = self.tilemap[self._locfmt_p_fn(ngbr_loc[0], ngbr_loc[1])]
                    sorted_ngbrs = tuple(sorted(directions))
                    # print(f"not OG:::{sorted_ngbrs}")
                    # print(f"{tile.pos,ngbr_loc,directions,ngbr_tile.pos,sorted_ngbrs = }")
                    # print(sorted_ngbrs)
                    if sorted_ngbrs in self._autotile_map:
                        # FIXME: this is redundant as it is not direcly mutating self.tilema. should mutate `tile`
                        # print(f"{tile,ngbr_loc, ngbr_tile = }")
                        ngbr_tile.variant = self._autotile_map[sorted_ngbrs]

            # print(neighbors, tile_neighbors)
            neighbors.clear()
            # tile_neighbors.clear()

    def save(self, path: str) -> None:
        # TODO: convert path type from str to use Path
        with open(path, "w") as f:
            json.dump(
                dict(
                    tile_size=self.tile_size,
                    tilemap=self.tilemap_to_json(),
                    offgrid=self.offgrid_tiles_to_json(),
                ),
                f,
            )

    def load(self, path: str) -> None:
        # TODO: convert path type from str to use Path
        map_data = None
        with open(path, "r") as f:
            map_data = json.load(f)
        if map_data:
            self.tile_size = map_data["tile_size"]
            self.tilemap = dict(self.tilemap_json_to_dataclass(map_data["tilemap"]))
            self.offgrid_tiles = set(self.offgrid_tiles_json_to_dataclass(map_data["offgrid"]))

    def maybe_gridtile(self, pos: pg.Vector2) -> Optional[TileItem]:
        return self.tilemap.get(self.vec2_jsonstr(self.pos_as_grid_loc_vec2(pos)), None)

    def maybe_solid_gridtile_bool(self, pos: pg.Vector2) -> bool:
        """Return boolean if physics tile can be stepped on or None"""
        return (
            True
            if (tile := self.maybe_gridtile(pos)) and (tile and tile.kind in self._physics_tiles)
            else False
        )

    def maybe_solid_gridtile(self, pos: pg.Vector2) -> Optional[TileItem]:
        """Return optional physics tile can be stepped on or None"""
        return (
            tile
            if (tile := self.maybe_gridtile(pos)) and (tile and tile.kind in self._physics_tiles)
            else None
        )

    def tilemap_to_json(self) -> dict[str, TileItemJSON]:
        return {
            key: TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant)
            for key, tile in self.tilemap.items()
        }

    def offgrid_tiles_to_json(self) -> list[TileItemJSON]:
        return [
            TileItemJSON(kind=tile.kind.value, pos=tuple(tile.pos), variant=tile.variant)
            for tile in self.offgrid_tiles
        ]

    def pos_as_grid_loc_vec2(self, vec2: pg.Vector2) -> pg.Vector2:
        return vec2 // self.tile_size  # Vector element-wise division for efficiency

    def pos_as_grid_loc_tuple2(self, x: int | float, y: int | float) -> tuple[int, int]:
        """calc_tile_loc avoids pixel bordering zero to round to 1."""
        return (int(x // self.tile_size), int(y // self.tile_size))

    @staticmethod
    # def offgrid_tiles_json_to_dataclass(data: list[TileItemJSON]):  # -> list[TileItem]:
    def offgrid_tiles_json_to_dataclass(data: Sequence[TileItemJSON]):  # -> list[TileItem]:
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
    # def tilemap_json_to_dataclass(data: dict[str, TileItemJSON]):
    def tilemap_json_to_dataclass(data: Mapping[str, TileItemJSON]):
        # PERF: needs optimization. use generators or ctx manager for file i/o?
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

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        blit_partial = partial(surf.blit)
        # ^ hack: optimization hack to stop python from initializing dot methods
        # | on each iteration in for loop or use without functool.partial e.g. `blit = surf.blit`
        # ====

        for tile in self.offgrid_tiles:
            blit_partial(self.game_assets_tiles[tile.kind.value][tile.variant], tile.pos - offset)

        xlo, ylo = self.pos_as_grid_loc_tuple2(offset[0], offset[1])
        xhi, yhi = self.pos_as_grid_loc_tuple2(
            offset[0] + surf.get_width(), offset[1] + surf.get_height()
        )
        # Minor optimization: Pre-format string for potential slight speedup during loop iterations.
        # F-strings are generally preferred for readability.
        loc_format = f"{{}};{{}}"  # Pre-calculate string format

        # draw tiles only if its position is in camera range
        for x in range(xlo, xhi + 1):
            for y in range(ylo, yhi + 1):
                # if (loc := f"{int(x)};{int(y)}") in self.tilemap:
                loc = loc_format.format(int(x), int(y))  # Use format method
                if loc in self.tilemap:
                    tile = self.tilemap[loc]
                    # img = self.game_assets_tiles[tile.kind.value][tile.variant]
                    imgs = self.game_assets_tiles.get(tile.kind.value, None)
                    if imgs is not None and (index := tile.variant) < len(imgs):
                        img = imgs[index]
                        blit_partial(img, (tile.pos * self.tile_size) - offset)


# map_data = [
#     [0, 0, 1, 0],
#     [0, 0, 1, 0],
#     [0, 1, 0, 0],
#     [0, 1, 1, 1],
# ]
# origin = (0, 0)
#
# print(f"{map_data=}")
# print(f"{origin=}")
# loc_fmt = f"{{}};{{}}"  # Pre-calculate string format
#
#
# def is_valid(map_data: list[list[int]], x: int, y: int) -> bool:
#     if not (0 <= x < len(map_data) and 0 <= y < len(map_data[0]) and map_data[x][y] == 0):
#         print(f"{loc_fmt.format(x,y)}) out of bounds")
#     else:
#         print(f"{loc_fmt.format(x,y)} in bounds")
#     return False
#
#
# def flood_fill(map_data: list[list[int]], x: int, y: int):
#     valid = is_valid(map_data, x, y)
#     print(f"{loc_fmt.format(x,y)} : ({valid=})")
#
#
# print(flood_fill(map_data, origin[0], origin[1]))

# from pprint import pprint

origin = (0, 0)

# Example map data (0 represents floor, 1 represents wall)
map_data = [[0, 0, 1, 1, 1], [1, 0, 0, 0, 1], [1, 1, 1, 0, 1], [1, 0, 0, 0, 0], [1, 1, 1, 1, 1]]
nrows = len(map_data)
ncols = len(map_data[0])
rows_range = range(nrows)
cols_range = range(ncols)

CELL_EMPTY = 0
CELL_OCCUPIED = 1

# Pre-calculate string format
loc_fmt = f"({{}};{{}})"
locfmt_partial = partial(loc_fmt.format)


# def is_valid(map_data: list[list[int]], x: int, y: int) -> bool:
def is_valid(map_data: Sequence[list[int]], x: int, y: int) -> bool:
    if not (0 <= x < len(map_data) and 0 <= y < len(map_data[0])):
        # print(f"{locfmt_partial(x,y)}", end="\tcell out of bounds\n")
        return False
    if map_data[x][y] != CELL_EMPTY:
        # print(f"{locfmt_partial(x,y)}", end="\tcell not empty\n")
        return False
    # print(f"{locfmt_partial(x,y)}", end="\tcell valid\n")
    return True


def floodfill(map_data: Sequence[list[int]], x: int, y: int):
    if not is_valid(map_data, x, y):
        return
    # mark cell visited
    map_data[x][y] = CELL_OCCUPIED
    # print(f"{locfmt_partial(x,y)}", end="\tcell marked visited\n")
    # recursion: neighbor offsets
    floodfill(map_data, x + 1, y)
    floodfill(map_data, x - 1, y)
    floodfill(map_data, x, y + 1)
    floodfill(map_data, x, y - 1)


def example_floodfill():
    print(f"{origin=}", end="\n\n")
    # pprint(list(itertools.product(rows, cols)), compact=True, width=80)

    # Draw the map: BEFORE
    for x, y in it.product(rows_range, cols_range):
        _tile_rect = pg.Rect(x * pre.TILE_SIZE, y * pre.TILE_SIZE, pre.TILE_SIZE, pre.TILE_SIZE)
        if map_data[x][y] == CELL_EMPTY:
            print(" ", end=" ")  # pg.draw.rect(screen, FLOOR_COLOR, tile_rect)
        else:
            print("#", end=" ")  # pg.draw.rect(screen, WALL_COLOR, tile_rect)
        if y == len(map_data[0]) - 1:
            print()

    # Update Buffer
    floodfill(map_data, origin[0], origin[1])

    # Draw the map: AFTER
    for x, y in it.product(rows_range, cols_range):
        _tile_rect = pg.Rect(x * pre.TILE_SIZE, y * pre.TILE_SIZE, pre.TILE_SIZE, pre.TILE_SIZE)
        if map_data[x][y] == CELL_EMPTY:
            print(" ", end=" ")
            # pg.draw.rect(screen, FLOOR_COLOR, tile_rect)
        else:
            print("#", end=" ")
        # pg.draw.rect(screen, WALL_COLOR, tile_rect)
        if y == len(map_data[0]) - 1:
            print()
