from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game
    from editor import Editor

import pygame as pg

from internal.prelude import TILE_SIZE


class Tilemap:
    def __init__(self, game: Game, tile_size: int = TILE_SIZE) -> None:
        self.game = game
        self.tile_size = tile_size
        self.tilemap = {}
        self.offgrid_tiles = []

        # self.game = game
        # self.tile_size = tile_size
        # self.tilemap: dict[str, TileDict] = {}
        # self.offgrid_tiles: list[TileDict] = []

    def render(self, surf: pg.Surface, offset=pg.Vector2(0, 0)) -> None:
        pass
