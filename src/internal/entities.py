from __future__ import annotations

from typing import TYPE_CHECKING

from internal.prelude import EntityKind
from internal.tilemap import Tilemap

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game

import pygame as pg


class PhysicalEntity:
    def __init__(self, game: Game, entity_kind: EntityKind, pos: pg.Vector2, size: pg.Vector2) -> None:
        self.game = game
        self.kind = entity_kind
        self.pos = pos.copy()
        self.size = size

        self.velocity = pg.Vector2(0, 0)

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        frame_movement = movement + self.velocity

        # physics: movement via collision detection 2 part axis method

        self.pos.x += frame_movement.x

        self.pos.y += frame_movement.y

        return True

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        surf.blit(self.game.assets.surface["player"], self.pos - offset)


class Enemy(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, EntityKind.ENEMY, pos, size)

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        return super().update(tilemap, movement)

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        super().render(surf, offset)


class Player(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, EntityKind.PLAYER, pos, size)

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        return super().update(tilemap, movement)

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        super().render(surf, offset)
