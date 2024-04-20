from __future__ import annotations

from collections import deque
from enum import Enum
from random import randint, random
from typing import TYPE_CHECKING, Final, Optional

import internal.prelude as pre
from internal.tilemap import Tilemap

if TYPE_CHECKING:
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
        self._terminal_limiter_air_friction: Final = max(0.1, ((pre.TILE_SIZE * 0.5) / (pre.FPS_CAP)))  # 0.1333333333.. (makes jumping possible to 3x player height)

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

    def set_action(self, action: Action):
        if action != self.action:  # quick check to see if a new action is set. grab animation if changed
            # ^ see 2:14:00... Do not fully understand this | if called every single frame, this avoids sticking to 0th frame
            # | frame created only when animation has changed. This avoids animation being stuck at 0th frame
            # ===
            self.action = action
            self.animation = self.game.assets.animations_entity[self.kind.value][self.action.value].copy()  # or self._animation_assets[self.action.value].copy()

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)  # reset at start of each frame

        frame_movement: pg.Vector2 = movement + self.velocity

        # physics: movement via collision detection 2 part axis method handle one axis at a time
        #   for predictable resolution also pygame-ce allows calculating floats with Rects
        self.pos.x += frame_movement.x  # X-AXIS
        entity_rect = self.rect()
        for rect in tilemap.physics_rects_around((int(self.pos.x), int(self.pos.y))):
            if entity_rect.colliderect(rect):
                if frame_movement.x > 0:  # traveling right
                    entity_rect.right = rect.left
                    self.collisions.right = True
                if frame_movement.x < 0:  # traveling left
                    entity_rect.left = rect.right
                    self.collisions.left = True
                # update x pos as int as pygame rect don't handle it as of now
                self.pos.x = entity_rect.x

        self.pos.y += frame_movement.y  # Y-AXIS
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


class Enemy(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.ENEMY, pos, size)

        self.walking_timer = 0

        self._lookahead_x: Final = 7  # (-7px west or 7px east) from center
        self._lookahead_y: Final = 23  # 23px south
        self._moveby_x: Final = 0.5  # -0.5px if flip(facing left) else 0.5px

        self.movement_history_x: deque[float] = deque(maxlen=pre.FPS_CAP or 10)
        self.movement_history_y: deque[float] = deque(maxlen=pre.FPS_CAP or 10)

        self.alert_timer = 0
        self._always_alert = True  # added it just for fun. remove it for real gameplay

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        # pre-calculations: before inherited PhysicalEntity update()

        match self.walking_timer > 0:
            case True:  # movement: via timer
                _lookahead = pg.Vector2(
                    self.rect().centerx + (-self._lookahead_x if self.flip else self._lookahead_x),
                    self.pos.y + self._lookahead_y,
                )
                _solid_ahead = tilemap.maybe_solid_gridtile_bool(_lookahead)
                match (_solid_ahead, self.collisions.left, self.collisions.right):
                    case (True, True, _) | (True, _, True):
                        self.flip = not self.flip
                    case (True, False, False):
                        dx = -self._moveby_x if self.flip else self._moveby_x
                        movement = pg.Vector2(movement.x + dx, movement.y)
                        if self.alert_timer or self._always_alert:  # calculate moving average for smooth/erratic movement and apply to enemy movement
                            # perf: we can just hard code the length of movement history vvv
                            avg_x_mvmt = round(10 * sum(self.movement_history_x) / len(self.movement_history_x) if self.movement_history_x else 0) * 0.1
                            movement.x += round(avg_x_mvmt * 0.328 * 10) * 0.1
                        self.movement_history_x.append(dx)
                    case _:  # Any other case (not solid ahead or one tile space glitch)
                        self.flip = not self.flip

                self.alert_timer = max(0, self.alert_timer - 1)

                # timer: decrement. becomes 0 or static once every walk cycle to begin spawning a projectile
                self.walking_timer = max(0, self.walking_timer - 1)

                # interaction: can now shoot while static
                if not self.walking_timer:

                    # TODO: calculate distance between player and enemy
                    if 0:
                        pass

                    # todo: replenish alert timer if enemy spots player
                    if 0:
                        self.alert_timer = randint(30 * 2, 120 * 2)
                    pass

            case False if random() < 0.01:  # timer: replenish (1% chance or one in every .67 seconds)
                self.walking_timer = randint(30, 120)  # 0.5s to 2.0s random duration for walking
            case _:
                pass

        super().update(tilemap, movement)

        # action: handles animation state
        if movement.x != 0:
            self.set_action(Action.RUN)
        else:
            self.set_action(Action.IDLE)

        # enemy: death
        #   TODO: ....
        #   if _dead_condition:
        #       return True

        return False  # enemy: alive

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        super().render(surf, offset)


class Player(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.PLAYER, pos, size)  # NOTE: allow entity kind to be passed to Player class, to use switchable player mid games

        self._air_time_freefall_death: Final = 2 * pre.FPS_CAP  # 120 or 2 seconds
        self._jump_thrust: Final = 3
        self._jumps: Final = 1
        self._max_air_time: Final = 5
        self._max_dash_time: Final = 60  # directional velocity vector

        # timers
        self.air_time = 0
        self.dash_time = 0

        self.jumps = self._jumps
        self.wall_slide = False

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        super().update(tilemap, movement)

        self.air_time += 1

        # death: by air fall
        #   note: should this apply to enemy too? what if they fall accidently?
        if self.air_time > self._air_time_freefall_death:
            if not self.game.dead:
                self.game.screenshake = max(self.game.tilemap.tile_size, self.game.screenshake - 1)
            self.game.dead += 1  # incr dead timer

        if self.collisions.down:  # reset times when touch ground
            self.air_time = 0
            self.jumps = self._jumps

        if not self.wall_slide:
            if self.air_time > self._max_air_time - 1:
                self.set_action(Action.JUMP)
            elif movement.x != 0:
                self.set_action(Action.RUN)
            else:
                self.set_action(Action.IDLE)  # note: player IDLE state blends into the nearby color and can't be seen by enemies

        # Dash with particles burst and stream:
        # |  idle ---> burst ---> stream ---> burst ---> idle
        # |  0         60                  51 50         0
        # ....
        if abs(self.dash_time) in {60, 50}:
            # TODO: spawn dash burst particles
            # print(f"spawning particles: dash burst: {self.dash_time=}")
            pass
        if self.dash_time > 0:  # 0:60
            self.dash_time = max(0, self.dash_time - 1)
        if self.dash_time < 0:  # -60:0
            self.dash_time = min(0, self.dash_time + 1)
        if abs(self.dash_time) > 50:  # at first ten frames of dash abs(60 -> 50)
            self.velocity.x = 8 * (abs(self.dash_time) / self.dash_time)  # modify speed based on direction
            if abs(self.dash_time) == 51:
                self.velocity.x *= 0.1  # deceleration also acts as a cooldown, for next trigger
            # TODO: spawn dash streeam particles
            # print(f"spawning particles: dash stream: {self.dash_time=}")
            pass

        # normalize horizontal velocity
        if self.velocity.x > 0:
            self.velocity.x = max(0, self.velocity.x - 0.1)
        else:
            self.velocity.x = min(0, self.velocity.x + 0.1)

        return True

    def jump(self) -> bool:
        """returns True if successful jump"""
        if self.jumps:
            self.velocity.y = -self._jump_thrust  # -y dir: go up
            self.jumps -= 1
            self.air_time = self._max_air_time
            return True
        return False

    def dash(self) -> Optional[bool]:
        dash: Optional[bool] = None
        match self.dash_time == 0, self.flip:
            case True, True:
                self.dash_time = -self._max_dash_time
                dash = True
            case True, False:
                self.dash_time = self._max_dash_time
                dash = True
            case _:
                dash = False
        if dash:
            # self.game.sfx["dash"].play()
            return dash
        return dash

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        """
        Hide the player during initial dash burst for 10 frames
        Render burst of particles before and after dash and render a stream of particles during the dash
        """
        if abs(self.dash_time) <= 50:
            super().render(surf, offset)
