from __future__ import annotations

from typing import TYPE_CHECKING, Final

import internal.prelude as pre
from internal.tilemap import Tilemap

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game

import pygame as pg


class PhysicalEntity:
    def __init__(self, game: Game, entity_kind: pre.EntityKind, pos: pg.Vector2, size: pg.Vector2) -> None:
        self.game = game
        self.kind = entity_kind
        self.pos = pos.copy()
        self.size = size

        self.velocity = pg.Vector2(0, 0)
        self._terminal_velocity_y: Final = 5
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)

    def rect(self) -> pg.Rect:
        """Using position as top left of the entity"""
        return pg.Rect(int(self.pos.x), int(self.pos.y), int(self.size.x), int(self.size.y))

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)  # reset at start of each frame

        frame_movement = movement + self.velocity

        # physics: movement via collision detection 2 part axis method
        # handle one axis at a time for predictable resolution
        # also pygame-ce allows calculating floats with Rects

        if not False:
            self.pos.x += frame_movement.x
            entity_rect = self.rect()
            for rect in tilemap.physics_rects_around((int(self.pos.x), int(self.pos.y))):
                if entity_rect.colliderect(rect):
                    if frame_movement.x > 0:  # traveling right
                        entity_rect.right = rect.left
                        self.collisions.right = True
                    if frame_movement.x < 0:  # traveling left
                        entity_rect.left = rect.right
                        self.collisions.left = True
                    self.pos.x = entity_rect.x  # update x pos as int
            self.pos.y += frame_movement.y
            entity_rect = self.rect()  # !!!Important to re-calculate this since pos.x changes rect.
            for rect in tilemap.physics_rects_around((int(self.pos.x), int(self.pos.y))):
                if entity_rect.colliderect(rect):
                    if frame_movement.y > 0:  # traveling down
                        entity_rect.bottom = rect.top
                        self.collisions.down = True
                    if frame_movement.y < 0:  # traveling up
                        entity_rect.top = rect.bottom
                        self.collisions.up = True
                    self.pos.y = entity_rect.y  # update y pos as int

        # terminal velocity for Gravity limiter return min of (max_velocity, cur_velocity.) positive velocity is downwards (y-axis)
        self.velocity.y = min(self._terminal_velocity_y, self.velocity.y + 0.1)

        if (_experimental_free_fall := True) and not _experimental_free_fall:
            if not self.collisions.down and self.velocity.y >= self._terminal_velocity_y:
                self.velocity.y *= 0.1  # smooth freefall
        else:
            if self.collisions.down or self.collisions.up:
                self.velocity.y = 0  # if you run into the ground it should stop you. if you go up or jump head first to the roof it should stop you
                # ^ PERF: can add bounce if hit head on roof

        return True

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        surf.blit(self.game.assets.surface["player"], self.pos - offset)


class Enemy(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.ENEMY, pos, size)

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        super().update(tilemap, movement)
        return False  # enemy: alive

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        super().render(surf, offset)


class Player(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.PLAYER, pos, size)

        self._jump_thrust: Final = 3

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        super().update(tilemap, movement)
        return True

    def render(self, surf: pg.Surface, offset: pg.Vector2 = pg.Vector2(0, 0)) -> None:
        super().render(surf, offset)

    def jump(self) -> bool:
        """returns True if successful jump"""

        if (_tmp_impl := True) and _tmp_impl:  # HACK: temp jump impl
            self.velocity.y = -self._jump_thrust  # -y dir: go up
            return True

        return False
