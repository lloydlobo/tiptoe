from __future__ import annotations

from typing import TYPE_CHECKING, Final

import pygame as pg

import internal.prelude as pre


if TYPE_CHECKING:
    from tiptoe import Game


class Spawner:
    def __init__(self, game: Game, skind: pre.SpawnerKind, ekind: pre.EntityKind, pos: pg.Vector2, size: pg.Vector2) -> None:
        if pre.DEBUG_GAME_ASSERTS:
            assert skind.as_entity(ekind) == skind, f"want similar spawner and entity kind. got {skind, ekind}"

        self.game = game
        self.pos = pos.copy()
        self.size = size

        self.spawner_kind: Final = skind
        self.entity_kind: Final = ekind
        self.assets: Final[list[pg.Surface]] = self.game.assets.tiles[self.entity_kind.value]

    def rect(self) -> pg.Rect:
        return pg.Rect(self.pos.x, self.pos.y, self.size.x, self.size.y)


class Portal(Spawner):
    def __init__(self, game: Game, ekind: pre.EntityKind, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.SpawnerKind.PORTAL, ekind, pos, size)

    def rect(self) -> pg.Rect:
        return super().rect()
