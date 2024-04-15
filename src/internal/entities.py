from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Final

import internal.prelude as pre
from internal.tilemap import Tilemap

if TYPE_CHECKING:  # Thanks for the tip: adamj.eu/tech/2021/05/13/python-type-hints-how-to-fix-circular-imports/
    from tiptoe import Game

import pygame as pg


class Action(Enum):
    IDLE = "idle"
    JUMP = "jump"
    RUN = "run"


class PhysicalEntity:
    def __init__(self, game: Game, entity_kind: pre.EntityKind, pos: pg.Vector2, size: pg.Vector2) -> None:
        self.game = game
        self.kind = entity_kind
        self.pos = pos.copy()
        self.size = size

        self.animation_assets = self.game.assets.animations_entity[self.kind.value]  # note: initialized once at __init__ for performance reasons

        self.velocity = pg.Vector2(0, 0)
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)
        self._terminal_velocity_y: Final = 5

        self.anim_offset = pg.Vector2(-1, -1) or pg.Vector2(-3, -3)  # should be an int
        # ^ workaround for padding used in animated sprites states like run
        # | jump to avoid collisions or rendering overflows outside of hit-box for entity
        # ---
        self.action: Action | None = None  # actual state. # HACK: figure out how to set a None default state without triggering linters
        self.set_action(Action.IDLE)

        self.flip = False

    def rect(self) -> pg.Rect:
        """Using position as top left of the entity"""
        return pg.Rect(int(self.pos.x), int(self.pos.y), int(self.size.x), int(self.size.y))

    def set_action(self, action: Action):
        if action != self.action:  # quick check to see if a new action is set. grab animation if changed
            # ^ see 2:14:00... Do not fully understand this | if called every single frame, this avoids sticking to 0th frame
            # | frame created only when animation has changed. This avoids animation being stuck at 0th frame
            # ===
            self.action = action
            self.animation = self.game.assets.animations_entity[self.kind.value][
                self.action.value
            ].copy()  # or self._animation_assets[self.action.value].copy()
            # print(self.animation)

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

        if movement.x < 0:
            self.flip = True
        if movement.x > 0:  # ideally sprites are right facing images by default
            self.flip = False

        # terminal velocity for Gravity limiter return min of (max_velocity, cur_velocity.) positive velocity is downwards (y-axis)
        terminal_limiter_air_friction = 0.1 or (pre.TILE_SIZE / pre.FPS_CAP)
        self.velocity.y = min(self._terminal_velocity_y, self.velocity.y + terminal_limiter_air_friction)

        if (_experimental_free_fall := True) and not _experimental_free_fall:
            if not self.collisions.down and self.velocity.y >= self._terminal_velocity_y:
                self.velocity.y *= 0.1  # smooth freefall
        else:
            if self.collisions.down or self.collisions.up:
                self.velocity.y = 0  # if you run into the ground it should stop you. if you go up or jump head first to the roof it should stop you
                # ^ PERF: can add bounce if hit head on roof

        return True

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        surf.blit(pg.transform.flip(self.animation.img(), self.flip, False), (self.pos - offset + self.anim_offset))
        # old: =>
        # surf.blit(self.game.assets.surface["player"], self.pos - offset)


class Enemy(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.ENEMY, pos, size)

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        super().update(tilemap, movement)
        return False  # enemy: alive

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        super().render(surf, offset)


class Player(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.PLAYER, pos, size)

        self._jump_thrust: Final = 3
        self._jumps: Final = 1
        self._max_air_time: Final = 5

        self.air_time = 0
        self.jumps = self._jumps

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        super().update(tilemap, movement)

        self.air_time += 1

        # death: by air fall
        if self.air_time > 120:  # 2 secs (2 * FPS_CAP)
            if not self.game.dead:
                self.game.screenshake = max(pre.TILE_SIZE, self.game.screenshake - 1)
            self.game.dead += 1  # incr dead timer

        if self.collisions.down:  # reset times when touch ground
            self.air_time = 0
            self.jumps = self._jumps

        if self.air_time > self._max_air_time - 1:
            self.set_action(Action.JUMP)
        elif movement.x != 0:
            self.set_action(Action.RUN)
        elif self.velocity.y >= 0 and self.collisions.down:
            self.set_action(Action.IDLE)

        return True

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        super().render(surf, offset)

    def jump(self) -> bool:
        """returns True if successful jump"""

        if self.jumps:  # HACK: temp jump impl
            self.velocity.y = -self._jump_thrust  # -y dir: go up
            self.jumps -= 1
            self.air_time = self._max_air_time
            return True

        return False
