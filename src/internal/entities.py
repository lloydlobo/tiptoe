from __future__ import annotations

import math
import time
from collections import deque
from enum import Enum
from random import randint, random
from typing import TYPE_CHECKING, Final, Literal, Optional

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
    def __init__(
        self,
        game: Game,
        entity_kind: pre.EntityKind,
        pos: pg.Vector2,
        size: pg.Vector2,
    ) -> None:
        self.game = game
        self.kind = entity_kind
        self.pos = pos.copy()
        self.size = size

        self.animation_assets = self.game.assets.animations_entity[self.kind.value]
        self.velocity = pg.Vector2(0, 0)
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)

        self._terminal_velocity_y: Final = 5  # terminal velocity for Gravity limiter return min of (max_velocity, cur_velocity.) positive velocity is downwards (y-axis)
        self._terminal_limiter_air_friction: Final = max(0.1, ((pre.TILE_SIZE * 0.5) / (pre.FPS_CAP)))  # 0.1333333333.. (makes jumping possible to 3x player height)

        self.anim_offset = pg.Vector2(-1, -1)  # | Workaround for padding used in animated sprites states like run jump
        # Note: should be an int                 | to avoid collisions or rendering overflows outside of hit-box for entity

        self.action: Optional[Action] = None
        self.set_action(Action.IDLE)

        self.flip = False

    def rect(self) -> pg.Rect:
        """Return the rectangular bounds of the entity using position as top-left of the entity."""
        return pg.Rect(int(self.pos.x), int(self.pos.y), int(self.size.x), int(self.size.y))

    def set_action(self, action: Action):
        # Quick check to see if a new action is set. grab animation if changed
        # frame created only when animation has changed. This avoids animation being stuck at 0th frame
        if action != self.action:
            self.action = action
            self.animation = self.game.assets.animations_entity[self.kind.value][self.action.value].copy()

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        """
        Update the entity's position based on physics and collisions.

        Physics: movement via collision detection 2 part axis method handle one
        axis at a time for predictable resolution also pygame-ce allows
        calculating floats with Rects

        Note: For each X and Y axis movement, we update x and y position as int
        as pygame rect don't handle it as of now.
        """
        # Compute players input based movement with entity velocity
        frame_movement: pg.Vector2 = movement + self.velocity

        # Reset collision state at start of each frame
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)

        # X-axis movement
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
                self.pos.x = entity_rect.x

        # Y-axis movement
        self.pos.y += frame_movement.y
        entity_rect = self.rect()
        for rect in tilemap.physics_rects_around((int(self.pos.x), int(self.pos.y))):
            if entity_rect.colliderect(rect):
                if frame_movement.y > 0:  # traveling down
                    entity_rect.bottom = rect.top
                    self.collisions.down = True
                if frame_movement.y < 0:  # traveling up
                    entity_rect.top = rect.bottom
                    self.collisions.up = True
                self.pos.y = entity_rect.y

        if movement.x < 0:
            self.flip = True
        if movement.x > 0:
            self.flip = False

        # Update velocity
        self.velocity.y = min(self._terminal_velocity_y, self.velocity.y + self._terminal_limiter_air_friction)

        # Handle collisions
        if self.collisions.down or self.collisions.up:
            self.velocity.y = 0

        self.animation.update()
        return True

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        surf.blit(pg.transform.flip(self.animation.img(), self.flip, False), (self.pos - offset + self.anim_offset))


class Enemy(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.ENEMY, pos, size)
        self._max_alert_time: Final = (60 * 2.5) * 2  # aiming for alert for 5 seconds as if the enemy stops moving the agitation isn't shown for that time period?

        self.walking_timer = 0
        self.alert_timer = 0

        self._lookahead_x: Final = 7  # (-7px west or 7px east) from center
        self._lookahead_y: Final = 23  # 23px south
        self._moveby_x: Final = 0.5  # -0.5px if flip(facing left) else 0.5px
        self._maxlen_movement_history: Final[int] = pre.TILE_SIZE  # or pre.FPS_CAP

        self.movement_history_x: deque[float] = deque(maxlen=self._maxlen_movement_history)
        self.movement_history_y: deque[float] = deque(maxlen=self._maxlen_movement_history)

        self._always_alert = True  # added it just for fun. remove it for real gameplay
        self.history_contact_with_player: deque[tuple[float, Literal['e-face-left', 'e-face-right'], tuple[str, str]]] = deque(maxlen=pre.FPS_CAP * 2)  # _type:ignore

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        # Pre-calculations before inheriting PhysicalEntity update
        match (self.walking_timer > 0):
            case True:
                # Movement via timer
                lookahead_x = -self._lookahead_x if self.flip else self._lookahead_x
                lookahead = pg.Vector2(self.rect().centerx + lookahead_x, self.pos.y + self._lookahead_y)
                solid_ahead = tilemap.maybe_solid_gridtile_bool(lookahead)

                match solid_ahead, self.collisions.left, self.collisions.right:
                    case (True, True, _) | (True, _, True):
                        self.flip = not self.flip

                    case (True, False, False):
                        dx = -self._moveby_x if self.flip else self._moveby_x
                        movement += pg.Vector2(dx, 0)
                        # print(self.alert_timer, end=' ')

                        # Calculate moving average for smooth/erratic movement
                        if self.alert_timer or self._always_alert:
                            avg_mvmt_x = 0.1 * round(10 * sum(self.movement_history_x) / len(self.movement_history_x) if self.movement_history_x else 0)  # perf: hard code the length of movement history ^^^^^
                            boost_x = 3.28 + 2  # 3.28
                            movement.x += 0.1 * round(avg_mvmt_x * boost_x)

                            # TODO: remove extra_crazy after demo
                            extra_crazy = math.sin(self.alert_timer) * randint(0, 2)  # agitated little hops
                            movement.y -= extra_crazy
                        self.movement_history_x.append(dx)

                    case _:
                        self.flip = not self.flip

                self.alert_timer = max(0, self.alert_timer - 1)
                self.walking_timer = max(0, self.walking_timer - 1)  # timer: decrement. becomes 0 or static once every walk cycle to begin spawning a projectile

                # if 0:  # JFL :)
                #     if self.rect().colliderect(self.game.player.rect()):
                #         e_pos = f"{int(self.pos.x), int(self.pos.y)}"
                #         p_pos = f"{int(self.game.player.pos.x), int(self.game.player.pos.y)}"
                #         e_dir = "e-face-left" if self.flip else "e-face-right"
                #         time_time: float = time()
                #         record = (time_time, e_dir, (e_pos, p_pos))
                #         if record not in self.history_contact_with_player:  # _type:ignore
                #             pprint(self.history_contact_with_player)  # _type:ignore
                #             print("enemy contact player", len(self.history_contact_with_player))
                #         if self.game.player.dash_time >= self.game.player.dash_time_burst_1 - self.game.player.dash_time_burst_2:
                # print("dashed")
                #         self.history_contact_with_player.appendleft(record)  # _type:ignore

                # Enemy interaction: can now shoot while static!!
                if not self.walking_timer:
                    # Calculate distance between player and enemy
                    dist_pe = self.game.player.pos - self.pos
                    if abs(dist_pe.y) < pre.TILE_SIZE:
                        self.alert_timer = self._max_alert_time
                        # print(f"{dist_pe=}")
                        pass
                    pass

                    # death by rect collision????

                    # else:
                    #     self.scanned_pos.clear()

                    # TODO: replenish alert timer if enemy spots player
                    if 0:
                        self.alert_timer = randint(30 * 2, 120 * 2)
                        pass

            case False if random() < 0.01:  # Timer replenish (1% chance or one in every .67 seconds)
                self.walking_timer = randint(30, 120)  # 0.5s to 2.0s random duration for walking

            case _:
                pass

        super().update(tilemap, movement)

        # Action: handles animation state
        if movement.x != 0:
            self.set_action(Action.RUN)
        else:
            self.set_action(Action.IDLE)

        # enemy: death
        #   TODO: ....
        #   if _dead_condition:
        #       return True
        return False  # Enemy: alive

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        super().render(surf, offset)


class Player(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.PLAYER, pos, size)  # NOTE: allow entity kind to be passed to Player class, to use switchable player mid games

        # Constants
        self._air_time_freefall_death: Final = 2 * pre.FPS_CAP  # 120 or 2 seconds
        self._jump_thrust: Final = 3
        self._dash_thrust: Final = 8
        self._jumps: Final = 2
        self._max_air_time: Final = 5
        self._max_dash_time: Final = 60  # directional velocity vector
        self.dash_time_burst_1: Final = self._max_dash_time
        self.dash_time_burst_2: Final = 50
        # self.dash_time_stream: Final = 10

        # Timers
        self.air_time = 0
        self.dash_time = 0

        # Flags
        self.jumps = self._jumps
        self.wall_slide = False

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        """
        Dash mechanics:

            Dash with particles burst and stream:
            |  idle ---> burst ---> stream ---> burst ---> idle
            |  0         60                  51 50         0
        """
        super().update(tilemap, movement)

        self.air_time += 1

        # Handle death by air fall
        if self.air_time > self._air_time_freefall_death:
            if not self.game.dead:
                self.game.screenshake = max(self.game.tilemap.tile_size, self.game.screenshake - 1)
            self.game.dead += 1  # Increment dead timer

        # Reset times when touch ground
        if self.collisions.down:
            if self.air_time > self._max_air_time:  # Credit: mrc
                # TODO:
                #    self.game.sfx["land_anim"]
                #    self.game.sfx.play("land", volume=0.5)
                print(f"{time.time()}: render land anim")
                print(f"{time.time()}: play land sound")
                pass
            self.air_time = 0
            self.jumps = self._jumps
        else:
            pass
            # self.air_time += self.game.clock_dt

        # Update action based on player state
        if not self.wall_slide:
            if self.air_time > self._max_air_time - 1:
                self.set_action(Action.JUMP)
            elif movement.x != 0:
                self.set_action(Action.RUN)
            else:
                self.set_action(Action.IDLE)  # Player IDLE state blends into the nearby color and can't be seen by enemies

        # Handle dash
        if abs(self.dash_time) in {self.dash_time_burst_1, self.dash_time_burst_2}:
            # TODO: spawn dash burst particles
            pass
        if self.dash_time > 0:  # 0:60
            self.dash_time = max(0, self.dash_time - 1)
        if self.dash_time < 0:  # -60:0
            self.dash_time = min(0, self.dash_time + 1)
        if abs(self.dash_time) > 50:  # at first ten frames of dash abs(60 -> 50)
            self.velocity.x = self._dash_thrust * (abs(self.dash_time) / self.dash_time)  # Modify speed based on direction
            if abs(self.dash_time) == 51:
                self.velocity.x *= 0.1  # Deceleration also acts as a cooldown for next trigger
            # TODO: spawn dash streeam particles
            pass

        # Normalize horizontal velocity
        self.velocity.x = max(0, self.velocity.x - 0.1) if (self.velocity.x > 0) else min(0, self.velocity.x + 0.1)

        return True

    def jump(self) -> bool:
        """Returns True if player jumps successfully"""
        if self.jumps:
            self.velocity.y = -self._jump_thrust  # Go up in -y direction
            self.jumps -= 1
            self.air_time = self._max_air_time
            return True
        return False

    def dash(self) -> Optional[bool]:
        """Initiate a dash action"""
        dash: Optional[bool] = None

        match (self.dash_time == 0), self.flip:
            case True, False:
                self.dash_time = self._max_dash_time
                dash = True

            case True, True:
                self.dash_time = -self._max_dash_time
                dash = True

            case _:
                dash = False

        if dash:
            # self.game.sfx["dash"].play()
            return dash
        return dash

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        """
        Hide the player during initial dash burst for 10 frames
        Render burst of particles before and after dash and render a stream of particles during the dash
        """
        if abs(self.dash_time) <= self.dash_time_burst_2:
            super().render(surf, offset)
        # else player is invincible and invisible


"""
Wed Apr 24 06:38:49 PM IST 2024
    deque([(1713964061.9896417, 'e-face-left', ('(240, 32)', '(237, 32)')),
           (1713964061.9707654, 'e-face-left', ('(241, 32)', '(246, 32)')),
           (1713964058.0381913, 'e-face-right', ('(291, 32)', '(293, 32)')),
           (1713964053.4319324, 'e-face-right', ('(189, 32)', '(189, 32)')),
           (1713964048.8090303, 'e-face-left', ('(202, 32)', '(209, 32)')),
           (1713964048.7927675, 'e-face-left', ('(203, 32)', '(209, 32)')),
           (1713964048.7729623, 'e-face-left', ('(204, 32)', '(209, 32)')),
           (1713964048.7554986, 'e-face-left', ('(204, 32)', '(209, 32)')),
           (1713964048.7385905, 'e-face-left', ('(205, 32)', '(209, 32)')),
           (1713964048.721735, 'e-face-left', ('(206, 32)', '(209, 32)')),
           (1713964048.704961, 'e-face-left', ('(206, 32)', '(209, 32)')),
           (1713964048.688162, 'e-face-left', ('(207, 32)', '(209, 32)')),
           (1713964048.6705403, 'e-face-left', ('(208, 32)', '(209, 32)')),
           (1713964048.654289, 'e-face-left', ('(208, 32)', '(209, 32)')),
           (1713964048.637389, 'e-face-left', ('(209, 32)', '(209, 32)')),
           (1713964048.6207702, 'e-face-left', ('(210, 32)', '(209, 32)')),
           (1713964048.6042001, 'e-face-left', ('(211, 32)', '(209, 32)')),
           (1713964048.58783, 'e-face-left', ('(211, 32)', '(209, 32)')),
           (1713964048.5712888, 'e-face-left', ('(212, 32)', '(209, 32)')),
           (1713964048.5547907, 'e-face-left', ('(213, 32)', '(209, 32)')),
           (1713964048.5389752, 'e-face-left', ('(213, 32)', '(209, 32)')),
           (1713964048.5212402, 'e-face-left', ('(214, 32)', '(209, 32)')),
           (1713964048.5034754, 'e-face-left', ('(215, 32)', '(209, 32)')),
           (1713964048.4877558, 'e-face-left', ('(215, 32)', '(209, 32)')),
           (1713964048.4717875, 'e-face-left', ('(216, 32)', '(209, 32)')),
           (1713964046.4511201, 'e-face-left', ('(243, 32)', '(237, 32)')),
           (1713964046.4345365, 'e-face-left', ('(244, 32)', '(246, 32)')),
           (1713964045.5948856, 'e-face-left', ('(281, 32)', '(288, 32)')),
           (1713964045.5772123, 'e-face-left', ('(281, 32)', '(288, 32)')),
           (1713964045.5593374, 'e-face-left', ('(282, 32)', '(288, 32)')),
           (1713964045.5423868, 'e-face-left', ('(283, 32)', '(288, 32)')),
           (1713964045.5254648, 'e-face-left', ('(283, 32)', '(288, 32)')),
           (1713964045.5088181, 'e-face-left', ('(284, 32)', '(288, 32)')),
           (1713964045.4916656, 'e-face-left', ('(285, 32)', '(288, 32)')),
           (1713964045.474993, 'e-face-left', ('(285, 32)', '(288, 32)')),
           (1713964045.4586277, 'e-face-left', ('(286, 32)', '(288, 32)')),
           (1713964045.4422865, 'e-face-left', ('(287, 32)', '(288, 32)')),
           (1713964045.4258285, 'e-face-left', ('(288, 32)', '(288, 32)')),
           (1713964045.409118, 'e-face-left', ('(288, 32)', '(288, 32)')),
           (1713964045.393071, 'e-face-left', ('(289, 32)', '(288, 32)')),
           (1713964045.3774922, 'e-face-left', ('(290, 32)', '(288, 32)')),
           (1713964045.360984, 'e-face-left', ('(290, 32)', '(288, 32)')),
           (1713964045.344959, 'e-face-left', ('(291, 32)', '(288, 32)')),
           (1713964045.3267052, 'e-face-left', ('(292, 32)', '(288, 32)')),
           (1713964045.3077047, 'e-face-left', ('(292, 32)', '(288, 32)')),
           (1713964045.291059, 'e-face-left', ('(293, 32)', '(288, 32)')),
           (1713964045.2748382, 'e-face-left', ('(294, 32)', '(288, 32)')),
           (1713964045.2586634, 'e-face-left', ('(295, 32)', '(288, 32)')),
           (1713964045.2428951, 'e-face-left', ('(295, 32)', '(288, 32)')),
           (1713964041.4347827, 'e-face-right', ('(254, 32)', '(247, 32)')),
           (1713964041.418044, 'e-face-right', ('(253, 32)', '(247, 32)')),
           (1713964041.4028215, 'e-face-right', ('(253, 32)', '(247, 32)')),
           (1713964041.3875556, 'e-face-right', ('(252, 32)', '(247, 32)')),
           (1713964041.371632, 'e-face-right', ('(251, 32)', '(247, 32)')),
           (1713964041.355926, 'e-face-right', ('(251, 32)', '(247, 32)')),
           (1713964041.3391201, 'e-face-right', ('(250, 32)', '(247, 32)')),
           (1713964041.3225977, 'e-face-right', ('(249, 32)', '(247, 32)')),
           (1713964041.3074193, 'e-face-right', ('(248, 32)', '(247, 32)')),
           (1713964041.2907696, 'e-face-right', ('(248, 32)', '(247, 32)')),
           (1713964041.2753384, 'e-face-right', ('(247, 32)', '(247, 32)')),
           (1713964041.2589593, 'e-face-right', ('(246, 32)', '(247, 32)')),
           (1713964041.2426426, 'e-face-right', ('(246, 32)', '(247, 32)')),
           (1713964041.2264535, 'e-face-right', ('(245, 32)', '(247, 32)')),
           (1713964041.20952, 'e-face-right', ('(244, 32)', '(247, 32)')),
           (1713964041.193247, 'e-face-right', ('(244, 32)', '(247, 32)')),
           (1713964041.1767647, 'e-face-right', ('(243, 32)', '(247, 32)')),
           (1713964041.1601684, 'e-face-right', ('(242, 32)', '(247, 32)')),
           (1713964041.1437523, 'e-face-right', ('(241, 32)', '(247, 32)')),
           (1713964041.127156, 'e-face-right', ('(241, 32)', '(247, 32)')),
           (1713964041.1110845, 'e-face-right', ('(240, 32)', '(247, 32)')),
           (1713964038.2243853, 'e-face-right', ('(167, 32)', '(160, 32)')),
           (1713964038.2076352, 'e-face-right', ('(167, 32)', '(160, 32)')),
           (1713964038.1912184, 'e-face-right', ('(166, 32)', '(160, 32)')),
           (1713964038.175467, 'e-face-right', ('(166, 32)', '(160, 32)')),
           (1713964038.156516, 'e-face-right', ('(165, 32)', '(160, 32)')),
           (1713964038.1369078, 'e-face-right', ('(164, 32)', '(160, 32)')),
           (1713964038.1198149, 'e-face-right', ('(164, 32)', '(160, 32)')),
           (1713964038.1028335, 'e-face-right', ('(163, 32)', '(160, 32)')),
           (1713964038.086036, 'e-face-right', ('(163, 32)', '(160, 32)')),
           (1713964038.0697258, 'e-face-right', ('(162, 32)', '(160, 32)')),
           (1713964038.052996, 'e-face-right', ('(162, 32)', '(160, 32)')),
           (1713964038.036721, 'e-face-right', ('(161, 32)', '(160, 32)')),
           (1713964038.0200157, 'e-face-right', ('(161, 32)', '(160, 32)')),
           (1713964038.0026534, 'e-face-right', ('(161, 32)', '(160, 32)')),
           (1713964037.9862387, 'e-face-right', ('(160, 32)', '(160, 32)')),
           (1713964037.9699142, 'e-face-right', ('(160, 32)', '(160, 32)')),
           (1713964037.9524043, 'e-face-right', ('(160, 32)', '(160, 32)')),
           (1713964037.936448, 'e-face-right', ('(160, 32)', '(160, 32)')),
           (1713964037.9207802, 'e-face-left', ('(160, 32)', '(160, 32)')),
           (1713964037.9041502, 'e-face-left', ('(160, 32)', '(160, 32)')),
           (1713964037.8834908, 'e-face-left', ('(161, 32)', '(160, 32)')),
           (1713964037.867336, 'e-face-left', ('(162, 32)', '(160, 32)')),
           (1713964037.8513367, 'e-face-left', ('(162, 32)', '(160, 32)')),
           (1713964037.8345664, 'e-face-left', ('(163, 32)', '(160, 32)')),
           (1713964037.8170195, 'e-face-left', ('(164, 32)', '(160, 32)')),
           (1713964037.8007066, 'e-face-left', ('(164, 32)', '(160, 32)')),
           (1713964037.7848005, 'e-face-left', ('(165, 32)', '(160, 32)')),
           (1713964037.7693536, 'e-face-left', ('(166, 32)', '(160, 32)')),
           (1713964037.7529182, 'e-face-left', ('(167, 32)', '(160, 32)')),
           (1713964037.7371526, 'e-face-left', ('(167, 32)', '(160, 32)')),
           (1713964037.4318607, 'e-face-left', ('(181, 32)', '(177, 32)')),
           (1713964037.4148474, 'e-face-left', ('(181, 32)', '(186, 32)')),
           (1713964034.7434077, 'e-face-left', ('(260, 32)', '(267, 32)')),
           (1713964034.7270463, 'e-face-left', ('(260, 32)', '(267, 32)')),
           (1713964034.7110572, 'e-face-left', ('(261, 32)', '(267, 32)')),
           (1713964034.6956165, 'e-face-left', ('(262, 32)', '(267, 32)')),
           (1713964034.6795309, 'e-face-left', ('(262, 32)', '(267, 32)')),
           (1713964034.663023, 'e-face-left', ('(263, 32)', '(267, 32)')),
           (1713964034.6467125, 'e-face-left', ('(264, 32)', '(267, 32)')),
           (1713964034.631061, 'e-face-left', ('(264, 32)', '(267, 32)')),
           (1713964034.6153016, 'e-face-left', ('(265, 32)', '(267, 32)')),
           (1713964034.5995936, 'e-face-left', ('(266, 32)', '(267, 32)')),
           (1713964034.583123, 'e-face-left', ('(267, 32)', '(267, 32)')),
           (1713964034.5671496, 'e-face-left', ('(267, 32)', '(267, 32)')),
           (1713964034.550338, 'e-face-left', ('(268, 32)', '(267, 32)')),
           (1713964034.5347009, 'e-face-left', ('(269, 32)', '(267, 32)')),
           (1713964034.5189173, 'e-face-left', ('(269, 32)', '(267, 32)')),
           (1713964034.5028317, 'e-face-left', ('(270, 32)', '(267, 32)')),
           (1713964034.4871984, 'e-face-left', ('(271, 32)', '(267, 32)')),
           (1713964034.4709213, 'e-face-left', ('(271, 32)', '(267, 32)'))],
          maxlen=120)
    enemy contact player 120
"""
