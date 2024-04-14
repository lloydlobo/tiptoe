from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game  # from editor import Editor

from dataclasses import dataclass

import pygame as pg

from internal.prelude import TILE_SIZE, TileKind


@dataclass
class TileItem:
    """TODO: create a parser to convert this data type to be json serializable"""

    kind: TileKind  # use an enum or verify with field()
    variant: int
    pos: pg.Vector2 | list[int | float] | tuple[int | float, ...]


class Tilemap:
    def __init__(self, game: Game, tile_size: int = TILE_SIZE) -> None:
        self.game = game
        self.tile_size = tile_size
        self.tilemap: dict[str, TileItem] = {}
        self.offgrid_tiles: list[TileItem] = []

        for i in range(50):
            self.tilemap[f"{3+i};{10}"] = TileItem(kind=TileKind.GRASS, variant=1, pos=pg.Vector2(3 + i, 10))  # vertical contiguous tiles
            self.tilemap[f"{10};{5+i}"] = TileItem(kind=TileKind.STONE, variant=1, pos=pg.Vector2(10, 5 + i))  # horizontal contiguous tiles

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        for tile in self.offgrid_tiles:
            surf.blit(self.game.assets.surfaces[tile.kind.value][tile.variant], tile.pos - offset)

        for loc in self.tilemap:
            tile = self.tilemap[loc]
            surf.blit(self.game.assets.surfaces[tile.kind.value][tile.variant], ((tile.pos * self.tile_size) - offset))
