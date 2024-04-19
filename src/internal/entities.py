from __future__ import annotations

from enum import Enum
from random import randint, random
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

        # terminal velocity for Gravity limiter return min of (max_velocity, cur_velocity.) positive velocity is downwards (y-axis)
        self._terminal_velocity_y: Final = 5
        self._terminal_limiter_air_friction: Final = max(
            0.1, ((pre.TILE_SIZE * 0.5) / (pre.FPS_CAP))
        )  # 0.1333333333.. (makes jumping possible to 3x player height)

        self.anim_offset = pg.Vector2(-1, -1) or pg.Vector2(-3, -3)  # should be an int
        # ^ workaround for padding used in animated sprites states like run
        # | jump to avoid collisions or rendering overflows outside of hit-box for entity
        # ---
        self.action: Action | None = None  # actual state. # HACK: figure out how to set a None default state without triggering linters
        self.set_action(Action.IDLE)

        self.flip = False

    # @cache
    def rect(self) -> pg.Rect:
        """Using position as top left of the entity"""

        return pg.Rect(int(self.pos.x), int(self.pos.y), int(self.size.x), int(self.size.y))

    # def __eq__(self, value: object, /) -> bool:
    #     print(f"{self.kind,value=}")
    #     return self.pos==value.pos and self.collisions==value.collisions
    #
    # def __hash__(self) -> int:
    #     return hash(tuple(self.pos))

    def set_action(self, action: Action):

        if action != self.action:  # quick check to see if a new action is set. grab animation if changed
            # ^ see 2:14:00... Do not fully understand this | if called every single frame, this avoids sticking to 0th frame
            # | frame created only when animation has changed. This avoids animation being stuck at 0th frame
            # ===
            self.action = action
            self.animation = self.game.assets.animations_entity[self.kind.value][
                self.action.value
            ].copy()  # or self._animation_assets[self.action.value].copy()

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)  # reset at start of each frame

        frame_movement: pg.Vector2 = movement + self.velocity

        # physics: movement via collision detection 2 part axis method
        # handle one axis at a time for predictable resolution
        # also pygame-ce allows calculating floats with Rects

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

        self.velocity.y = min(self._terminal_velocity_y, self.velocity.y + self._terminal_limiter_air_friction)

        # stop: if run into ground. stop if travel up or jump head first to ceiling
        if self.collisions.down or self.collisions.up:
            self.velocity.y = 0

        self.animation.update()

        return True

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        surf.blit(pg.transform.flip(self.animation.img(), self.flip, False), (self.pos - offset + self.anim_offset))
        # old: =>
        # surf.blit(self.game.assets.surface["player"], self.pos - offset)


class Enemy(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.ENEMY, pos, size)
        self.walking = 0

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        """
        solid_ahead = True  # TODO: physics tiles around

        match (solid_ahead, self.collisions.left, self.collisions.right):
            case (True, True, _):  # Solid ahead and colliding on the left
            case (True, _, True):  # Solid ahead and colliding on the right
                self.flip = not self.flip
            case (True, False, False):  # Solid ahead but not colliding
                movement = pg.Vector2(movement.x + (-0.5 if self.flip else 0.5), movement.y)
            case _:  # Any other case (not solid ahead)
                # Handle movement as usual (code not provided in the prompt)
                pass

            if (solid_ahead := tilemap.solid_check(_lookahead)) and (solid_ahead and (self.collisions["right"] or self.collisions["left"])):
                self.flip = not self.flip
            elif solid_ahead:  # turn
                movement = (movement[0] + (-0.5 if self.flip else 0.5), movement[1])
            else:
                self.flip = not self.flip
        """
        # manipulate movement
        if self.walking:
            _lookahead: Final = (self.rect().centerx + (-7 if self.flip else 7), self.pos[1] + 23)  # (x=7px * west/east from center, y=23px * south)
            # fmt: off
            if (
                (solid_ahead := tilemap.maybe_solid_gridtile(pg.Vector2(_lookahead)))
                and (
                    solid_ahead
                    and (self.collisions.right or self.collisions.left)
                )
            ):
                self.flip = not self.flip
            elif solid_ahead:
                movement = pg.Vector2(movement.x + (-0.5 if self.flip else 0.5), movement.y)
            else:
                self.flip = not self.flip
            # fmt: on

            # match (solid_ahead, self.collisions.left, self.collisions.right):
            #     case (True, True, _) | (True, _, True):
            #         self.flip = not self.flip
            #     case (True, _, _):
            #         movement.x = movement.x + (-0.5 if self.flip else 0.5)
            #         movement.y = movement.y
            #     case _:  # if tile glitch
            #         self.flip = not self.flip
            # becomes 0 (static once every walk cycle of spawning a projectile)
            self.walking = max(0, self.walking - 1)  # NOTE: max only!!!!
            if not self.walking:  # can shoot
                pass
        elif random() < 0.01:
            self.walking = randint(30, 120)

        super().update(tilemap, movement)

        if movement[0] != 0:
            self.set_action(Action.RUN)
        else:
            self.set_action(Action.IDLE)

        return False  # enemy: alive

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        super().render(surf, offset)


class Player(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        # NOTE: allow entity kind to be passed to Player class, to use switchable player mid games
        super().__init__(game, pre.EntityKind.PLAYER, pos, size)

        self._air_time_freefall_death: Final = 2 * pre.FPS_CAP  # 120 or 2 seconds
        self._jump_thrust: Final = 3
        self._jumps: Final = 1
        self._max_air_time: Final = 5

        self.air_time = 0
        self.jumps = self._jumps

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        super().update(tilemap, movement)

        self.air_time += 1

        # death: by air fall
        # note: should this apply to enemy too? what if they fall accidently?
        if self.air_time > self._air_time_freefall_death:
            if not self.game.dead:
                self.game.screenshake = max(self.game.tilemap.tile_size, self.game.screenshake - 1)
            self.game.dead += 1  # incr dead timer

        if self.collisions.down:  # reset times when touch ground
            self.air_time = 0
            self.jumps = self._jumps

        if (_tmp_not_self_wall_slide := True) and _tmp_not_self_wall_slide:
            if self.air_time > self._max_air_time - 1:
                self.set_action(Action.JUMP)
            elif movement.x != 0:
                self.set_action(Action.RUN)
            else:
                self.set_action(Action.IDLE)  # note: player IDLE state blends into the nearby color and can't be seen by enemies

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
