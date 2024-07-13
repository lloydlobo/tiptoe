from __future__ import annotations  # Requisite for: TYPE_CHECKING

import math
import time
from collections import deque
from enum import Enum
from functools import partial
from random import randint, random, uniform
from typing import (
    TYPE_CHECKING,  # Prerequisites: from __future__ import annotations
)
from typing import Dict, Final, List, Literal, Optional, Tuple

import pygame as pg

import internal.prelude as pre
from internal.particle import Particle
from internal.spark import Spark
from internal.tilemap import Tilemap


if TYPE_CHECKING:
    from game import Game


# _TDeque = deque[tuple[float, Literal['e-face-left', 'e-face-right'], tuple[str, str]]]


class Action(Enum):
    IDLE = "idle"
    JUMP = "jump"
    RUN = "run"
    SLEEPING = "sleeping"
    WALLSLIDE = "wallslide"
    WALLJUMP = "walljump"


def manhattan_dist(x1: pre.Number, y1: pre.Number, x2: pre.Number, y2: pre.Number) -> pre.Number:
    return abs(x1 - x2) + abs(y1 - y2)


# You don't need to use the build-in Sprite or Group classes. see  https://www.pygame.org/docs/tut/newbieguide.html
# More fun and intuitive (and fun) to wrote your own game's core logic and classes from scratch.
class PhysicalEntity:
    def __init__(self, game: Game, entity_kind: pre.EntityKind, pos: pg.Vector2, size: pg.Vector2) -> None:
        self.game = game
        self.kind = entity_kind
        self.pos: pg.Vector2 = pos.copy()
        self.size = size

        self.animation_assets = self.game.assets.animations_entity[self.kind.value]
        self.velocity = pg.Vector2(0, 0)
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)

        # terminal velocity for Gravity limiter return min of (max_velocity, cur_velocity.) positive velocity is downwards (y-axis)
        self._terminal_velocity_y: Final = 5
        # if max: 0.1333333333.. (makes jumping possible to 3x player height)
        # else use min for easy floaty feel
        self._terminal_limiter_air_friction: Final = max(0.1, ((pre.TILE_SIZE * 0.5) / (pre.FPS_CAP)))

        self.anim_offset = pg.Vector2(-3, 0)  # | Workaround for padding used in animated sprites states like run jump
        # Note: should be an int                 | to avoid collisions or rendering overflows outside of hit-box for entity

        self.action: Optional[Action] = None
        self.set_action(Action.IDLE)

        self.flip = False

        self.last_movement = pg.Vector2(0, 0)

    @property
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

        # ===--------Simulate Collisions-------=== #

        # Reset collision state at start of each frame
        self.collisions = pre.Collisions(up=False, down=False, left=False, right=False)

        # X-axis movement
        self.pos.x += frame_movement.x
        entity_rect = self.rect
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
        entity_rect = self.rect
        for rect in tilemap.physics_rects_around((int(self.pos.x), int(self.pos.y))):
            if entity_rect.colliderect(rect):
                if frame_movement.y > 0:  # traveling down
                    entity_rect.bottom = rect.top
                    self.collisions.down = True

                if frame_movement.y < 0:  # traveling up
                    entity_rect.top = rect.bottom
                    self.collisions.up = True

                self.pos.y = entity_rect.y

        # ===--------Movement Quirks-------=== #
        if movement.x < 0:
            self.flip = True

        if movement.x > 0:
            self.flip = False

        self.last_movement = movement

        # Update velocity
        self.velocity.y = min(self._terminal_velocity_y, self.velocity.y + self._terminal_limiter_air_friction)

        # Handle velocity based on collisions
        if self.collisions.down or self.collisions.up:
            self.velocity.y = 0

        self.animation.update()

        return True

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        surf.blit(pg.transform.flip(self.animation.img(), self.flip, False), (self.pos - offset + self.anim_offset))


class Enemy(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(game, pre.EntityKind.ENEMY, pos, size)
        self.gun_surf = self.game.assets.misc_surf["gun"]

        self._can_die: Final = False

        # Aiming for alert for 5 seconds as if the enemy stops moving the agitation isn't shown for that time period?
        self._max_alert_time: Final = (pre.FPS_CAP * 2.5) * (0.5 or 2)  # 20240528053139UTC
        self.alert_boost_factor: Final = 2 * 10  # Sun Apr 28 04:02:12 PM IST 2024
        self._alertness_enabled: Final = True

        self.alert_timer = 0
        self.walking_timer = 0
        self.walking_timer_reset_probability = 0.05  # or  0.01

        self._lookahead_x: Final = 7  # (-7px west or 7px east) from center
        self._lookahead_y: Final = 23  # 23px south
        self._moveby_x: Final = 0.5  # -0.5px if flip(facing left) else 0.5px
        self._maxlen_movement_history: Final[int] = pre.TILE_SIZE  # or pre.FPS_CAP
        self._bullet_speed: Final = 7

        self.movement_history_x: deque[float] = deque(maxlen=self._maxlen_movement_history)
        self.movement_history_y: deque[float] = deque(maxlen=self._maxlen_movement_history)
        # self.history_contact_with_player: _TDeque = deque(maxlen=pre.FPS_CAP * 2)
        self.is_collected_by_player = False

        self.is_player_close_by = False

        self.max_sleep_time = pre.FPS_CAP * 5
        self.sleep_timer = 0
        self.dashed_by_player = False
        self.dashed_by_player_counter = 0

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        # Pre-calculations before inheriting PhysicalEntity update
        prev_movement = movement.copy()

        if self.walking_timer > 0:
            lookahead_x = (-1) * self._lookahead_x if self.flip else self._lookahead_x
            lookahead = pg.Vector2(self.rect.centerx + lookahead_x, self.pos.y + self._lookahead_y)

            solid_ahead = tilemap.maybe_solid_gridtile_bool(lookahead)

            match solid_ahead, self.collisions.left, self.collisions.right:
                case (True, True, _) | (True, _, True):
                    self.flip = not self.flip
                case (True, False, False):  # turn
                    dx = (-1) * self._moveby_x if self.flip else self._moveby_x

                    movement.x = movement.x + dx
                    movement.y = movement.y

                    # Calculate moving average for smooth/erratic movement
                    if self._alertness_enabled and self.alert_timer:
                        # Shoot opposite sides
                        # ------------------------------------------------------
                        boost_x = 3.28 + 2  # 3.28
                        avg_mvmt_x = 0.1 * round(
                            # PERF(Lloyd): Hard code the length of movement history
                            10 * sum(self.movement_history_x) / len(self.movement_history_x)
                            if self.movement_history_x
                            else 0
                        )
                        movement.x += 0.1 * round(avg_mvmt_x * boost_x)
                        # ------------------------------------------------------
                        extra_crazy = math.sin(self.alert_timer) * randint(0, 2)  # Agitated little hops ^_^
                        movement.y -= extra_crazy  # NOTE(Lloyd): We can remove extra_crazy if required

                    if self._alertness_enabled:
                        self.movement_history_x.append(dx)
                case _:
                    self.flip = not self.flip

            self.walking_timer = max(0, self.walking_timer - 1)

            self.sleep_timer = max(0, self.sleep_timer - 1)

            if self._alertness_enabled:
                self.alert_timer = max(0, self.alert_timer - 1)

            if not self.walking_timer:
                # Calculate distance between player and enemy
                dist_pe = pg.Vector2(self.game.player.pos.x - self.pos.x, self.game.player.pos.y - self.pos.y)

                if abs(dist_pe.y) < 2 * pre.TILE_SIZE:
                    player_left_of_enemy, player_right_of_enemy = (dist_pe.x < 0, dist_pe.x > 0)
                    enemy_is_facing_left, enemy_is_facing_right = self.flip, not self.flip

                    if self.action != Action.SLEEPING:
                        if (enemy_is_facing_left and player_left_of_enemy) or (
                            enemy_is_facing_right and player_right_of_enemy
                        ):
                            self.spawn_projectile_with_sparks()

                if self._alertness_enabled and self.alert_timer:
                    # Only alerted enemies can be boosted for more alertness. and not everyone in the game.
                    # 20% chance increase to get more alert
                    if (self.walking_timer <= self._max_alert_time) and (random() < 0.01 * self.alert_boost_factor):
                        prev_timer = self.alert_timer
                        next_timer = randint(30 * 2, 120 * 2)
                        self.alert_timer = next_timer

                        if pre.DEBUG_GAME_ASSERTS:
                            if self.alert_timer != 0:
                                err_context = f"{prev_timer,next_timer,self.alert_timer,self._max_alert_time = }"

                                if next_timer > prev_timer:
                                    assert self.alert_timer >= prev_timer, err_context

        elif random() < self.walking_timer_reset_probability:  # refill timer one in every 0.67 seconds
            self.walking_timer = randint(30, 120)  # 0.5s to 2.0s random duration for walking
        else:
            if (_tmp_feature_sleeping := 1) and _tmp_feature_sleeping:
                threat_dist = pre.TILE_SIZE * 12
                player_distance_to_enemy = self.game.player.pos.distance_to(self.pos)
                self.is_player_close_by = abs(player_distance_to_enemy) < threat_dist

        if self.action == Action.SLEEPING:
            super().update(tilemap, prev_movement)
        else:
            super().update(tilemap, movement)

        if self.sleep_timer == 0:
            if not self.is_player_close_by:
                self.set_action(Action.SLEEPING)
            elif movement.x != 0:  # Action: handles animation state
                self.set_action(Action.RUN)
            else:
                self.set_action(Action.IDLE)

        # Enemy: sleepy slumber like death!
        self.dashed_by_player = False  # reset each loop
        player_invincible = abs(self.game.player.dash_timer) > self.game.player.dash_burst_2

        if player_invincible and self.game.player.rect.colliderect(self.rect):
            if self._can_die:  # todo: do sparky stuff
                return True  # enemy death

            # Dash makes enemies sleep
            self.set_action(Action.SLEEPING)
            self.sleep_timer = self.max_sleep_time

            # Update HUD stats
            if not self.dashed_by_player_counter:
                self.dashed_by_player_counter += 1
                self.game.player_dash_enemy_collision_count += 1

            # Pushed by player
            if not self.dashed_by_player:
                player = self.game.player
                # Avoid sticking to player -_-
                self.pos = player.pos.copy()

                self.velocity.y = player.velocity.y / 4
                self.velocity.x = 1.5 if self.flip else -1.5

            return False

        # Normalize horizontal velocity (copied from Player.update())
        self.velocity.x = max(0, self.velocity.x - 0.1) if (self.velocity.x > 0) else min(0, self.velocity.x + 0.1)

        return False  # Enemy: alive

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        super().render(surf, offset)

        if self.dashed_by_player_counter:
            center = (self.rect.centerx - offset[0], self.rect.top - 4 - offset[1])
            radius = 1
            pg.draw.circle(surf, pg.Color("gold"), center=center, radius=radius)
            pg.draw.circle(surf, pg.Color("yellow"), center=center, radius=radius + 2, width=1)

    def get_flip_dir(self) -> Literal[-1, 1]:
        return -1 if self.flip else 1

    def spawn_projectile_with_sparks(self):
        ANGLE_SPARK = 0.5
        COUNT_BULLET_SPARK = 4
        SIZE_GUN = (7, 4)  # self.gun_surf.get_size()
        SPEED_BULLET = uniform(1.618, 2.00)
        SPEED_SPARK = uniform(1.328, 1.618)

        direction = -1 if self.flip else 1

        self.game.projectiles.append(
            pre.Projectile(
                pos=pg.Vector2((self.rect.centerx + direction * SIZE_GUN[0]), (self.rect.centery + SIZE_GUN[1] // 2)),
                velocity=(direction * SPEED_BULLET),
                timer=0,
            ),
        )

        self.game.sparks.extend(
            Spark(
                self.game.projectiles[-1].pos.copy(),
                angle=(random() - ANGLE_SPARK + (math.pi if direction == -1 else 0)),
                speed=(SPEED_SPARK + random()),
            )
            for _ in range(COUNT_BULLET_SPARK)
        )

        if self._alertness_enabled:
            self.alert_timer = self._max_alert_time

        self.game.sfx.shoot.play()

    def make_enemy_go_after_player(self, movement: pg.Vector2) -> pg.Vector2:
        max_distance = self._lookahead_x * 2
        tmp_movement = self.pos.move_towards(self.game.player.pos, max_distance)

        if abs(tmp_movement.y) < pre.TILE_SIZE:
            next_movement = tmp_movement

            if not (self.get_flip_dir() == abs(next_movement.x) // next_movement.x):
                self.flip = not self.flip
            else:
                pass

            accum = 0
            rushing = True

            while rushing:
                if self.collisions.left or self.collisions.right:
                    rushing = False
                    break

                if accum >= max_distance:
                    rushing = False
                    break

                next_movement.x += min(self._moveby_x, tmp_movement.x) or self.get_flip_dir()
                accum += tmp_movement.x

            movement.x += next_movement.x

        return movement


class Player(PhysicalEntity):
    def __init__(self, game: Game, pos: pg.Vector2, size: pg.Vector2) -> None:
        super().__init__(
            game, pre.EntityKind.PLAYER, pos, size
        )  # NOTE: allow entity kind to be passed to Player class, to use switchable player mid games

        # Constants
        self._air_time_freefall_death: Final = 2.5 * pre.FPS_CAP  # 120 or 2 seconds
        self._coyote_timer_hi: Final = 0.2  # 0.2 sec
        self._coyote_timer_lo: Final = 0.0
        self._dash_force: Final = 8
        self._jump_force: Final = 3
        self._jumps: Final = 1
        self._max_dash_time: Final = 60  # directional velocity vector
        self._wallslide_velocity_cap_y: Final = 0.5

        self.dash_burst_1: Final = self._max_dash_time
        self.dash_burst_2: Final = 50
        self.jump_force = self._jump_force
        self.max_air_time: Final = 5
        self.max_dead_hit_skipped_counter: Final = 1  # extra lives before last checkpoint respawn

        # Timers
        self.air_timer = 0
        self.coyote_timer = self._coyote_timer_lo
        self.dash_timer = 0
        self.deltatime_jump_keydownup: Optional[float] = None
        self.jump_buffer_interval = 0.1
        self.jumps = self._jumps
        self.time_jump_keydown: Optional[float] = None
        self.time_jump_keyup: Optional[float] = None

        # Flags
        self.did_jump = False
        self.did_land = False
        self.wallslide = False

        self.keyup_history: List[Dict[str, Tuple[float, float]]] = []
        self.player_dash_enemy_collision_count = 0

        # Partial functions
        self._drawcircle_starfn = partial(pg.draw.circle, color=pre.COLOR.PLAYERSTAR)

    def update(self, tilemap: Tilemap, movement: pg.Vector2 = pg.Vector2(0, 0)) -> bool:
        super().update(tilemap, movement)

        self.air_timer += 1

        if self.game.dead:
            # HACK: Avoid dashing into spikes if auto rewind checkpoint after death
            self.velocity.x *= 0.1
            self.velocity.y *= 0.1
            self.dash_timer = 0

            if (not self.player_gcs_pos_before_death) and self.game.gcs_deque:
                self.player_gcs_pos_before_death = pg.Vector2(self.game.gcs_deque.popleft().player_position)

        # Handle death by air fall
        if self.air_timer > self._air_time_freefall_death:
            if not self.game.dead:
                self.game.screenshake = max(self.game.tilemap.tilesize, self.game.screenshake - 1)

            self.game.dead += 1  # Increment dead timer

        # Reset times when touch ground
        self.did_land = False

        if self.collisions.down:
            if self.air_timer > self.max_air_time:  # Credit: mrc
                self.game.sfx.jumplanding.play()
                self.did_land = True

            self.air_timer = 0
            self.coyote_timer = self._coyote_timer_hi
            self.jumps = self._jumps
        else:
            self.coyote_timer -= 1 / pre.FPS_CAP
            # self.air_time += self.game.clock_dt

        self.wallslide = False
        if (self.collisions.left or self.collisions.right) and (self.air_timer > self.max_air_time - 1):
            self.wallslide = True
            self.velocity.y = min(self.velocity.y, self._wallslide_velocity_cap_y)
            self.air_timer = self.max_air_time  # FIX: trying to avoid player death while sliding for too long

            if 1:  # requires wall_slide animation, todo
                if (flip_enabled := 1) and flip_enabled:
                    self.flip = False if self.collisions.right else True

                self.set_action(Action.WALLSLIDE)

        # JUMP BUFFERING
        if self.time_jump_keydown:
            if (
                self.jumps in {0, 1}
                and self.collisions.down
                and (time.time() - self.time_jump_keydown <= self.jump_buffer_interval)
            ):
                if not self.wallslide:
                    self.velocity.y = -self.jump_force
                    self.jumps -= 1
                    self.air_timer = self.max_air_time
                    self.coyote_timer = self._coyote_timer_lo  # ensure no multiple jumps
                else:
                    try:
                        assert 0, f"unreachable logic. jump should not have buffered input if wall sliding is active"
                    except AssertionError as e:
                        print(f"AssertionError while updating player's buffered jumping: {e}")
                        pass

        # Update action based on player state
        if not self.wallslide:
            if self.air_timer > self.max_air_time - 1:
                self.set_action(Action.JUMP)
            elif movement.x != 0:
                self.set_action(Action.RUN)
            else:
                self.set_action(Action.IDLE)

        # Handle dash
        if (abs_dash_t := abs(self.dash_timer)) in (self.dash_burst_1, self.dash_burst_2):
            is_burst1 = abs_dash_t == self.dash_burst_1
            self.game.particles.extend(
                Particle(
                    self.game,
                    pre.ParticleKind.PARTICLE,
                    pg.Vector2(self.rect.center),
                    pg.Vector2(velocity * dir_x, velocity * decay_y),
                    frame=randint(0, 7),
                )
                for i in range(1, 17)
                if (
                    angle := (random() * (math.pi * 2)),
                    speed := (random() * 0.5 + 0.5 - (1 / i)),
                    velocity := (math.cos(angle) * speed),
                    dir_x := (-1 if self.flip else 1),
                    decay_y := (0.618 - math.cos(self.velocity.y)) if is_burst1 else 1,
                )
            )

        if self.dash_timer > 0:  # 0..60
            self.dash_timer = max(0, self.dash_timer - 1)

        if self.dash_timer < 0:  # -60..0
            self.dash_timer = min(0, self.dash_timer + 1)

        if abs(self.dash_timer) > 50:  # at first ten frames of dash abs(60 -> 50)
            self.velocity.x = self._dash_force * (abs(self.dash_timer) / self.dash_timer)

            if abs(self.dash_timer) == 51:
                self.velocity.x *= 0.1  # Deceleration also acts as a cooldown for next trigger

            self.game.particles.extend(  # spawn dash streeam particles
                Particle(
                    self.game,
                    pre.ParticleKind.PARTICLE,
                    pg.Vector2(self.rect.center),
                    pg.Vector2(
                        (abs(self.dash_timer) / self.dash_timer) * random() * 3, -(0.5 / i) * math.sin(self.dash_timer)
                    ),
                    frame=randint(0, 7),
                )
                for i in range(1, 4)
            )

        # Normalize horizontal velocity
        self.velocity.x = max(0, self.velocity.x - 0.1) if (self.velocity.x > 0) else min(0, self.velocity.x + 0.1)

        return True

    def jump(self) -> bool:
        """Returns True if player jumps successfully"""
        self.did_jump = True
        # if not self.time_jump_keyup:
        #     assert 0

        if self.wallslide:
            if self.flip and self.last_movement.x < 0:  # jump away from wall
                self.velocity.x = 3.5
                self.velocity.y = -2.5
                self.air_timer = self.max_air_time
                self.jumps = max(0, self.jumps - 1)
                self.jump_force = self._jump_force
            elif (not self.flip) and self.last_movement.x > 0:
                self.velocity.x = -3.5
                self.velocity.y = -2.5
                self.air_timer = self.max_air_time
                self.jumps = max(0, self.jumps - 1)
                self.jump_force = self._jump_force
        elif self.jumps:
            if self.coyote_timer > self._coyote_timer_lo:
                self.velocity.y = -self.jump_force  # Go up in -y direction
                self.jumps -= 1
                self.air_timer = self.max_air_time
                self.coyote_timer = self._coyote_timer_lo  # ensure no multiple jumps
                self.jump_force = self._jump_force
        else:
            self.did_jump = False

        return self.did_jump  # hack: play jump sound at the caller

    def dash(self) -> bool:
        """Initiate a dash action

        Dash with particles burst and stream:
        |  idle ---> burst ---> stream ---> burst ---> idle
        |  0         60                  51 50         0
        """
        dash = True

        match self.dash_timer, self.flip:
            case 0, True:
                self.dash_timer = -self._max_dash_time
            case 0, False:
                self.dash_timer = self._max_dash_time
            case _:
                dash = False
        if dash:
            self.game.sfx.dashbassy.play()
            self.game.screenshake = max(self.game.tilemap.tilesize, self.game.screenshake - 0.05)
            return dash

        return dash

    def calculate_bezier_particle_radius(self) -> float:
        """Example:: 0.68 1.37 2.08 2.80 3.52 4 4 4 4 4"""
        pstar_radius: Final = pre.SIZE.PLAYERSTARDASHRADIUS[0]
        dash_amount: Final = abs(self.dash_timer)
        t = 1.0 - (dash_amount / self._max_dash_time)  # Calculate the Bezier curve parameter t

        # Calculate the radius based on the Bezier curve quadratic formula
        radius = ((1 - t) ** 2 * 0) + (2 * t * (1 - t) * 1) + (t**2 * 3)

        radius *= pstar_radius * 0.5  # Scale the radius based on the maximum dash time and the playersstar dash size
        radius = min(pstar_radius, 2 * math.pi * (radius * 1.618))  # Keep radius in bounds

        if radius >= pstar_radius:  # shrink
            radius = radius * 0.618 / ((1 + dash_amount) * math.pi)

        return radius

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        """Render player sprite or star particle based on game conditions.

        - Hide the player during initial dash burst for 10 frames.
        - Render burst of particles before and after dash.
        - Render a stream of particles during the dash.
        - Render a star particle if the player is falling offscreen with 15 frames left before death or during a dash burst.
        """
        near_freefall_death = self.air_timer + self.max_air_time + pre.FPS_CAP // 4 >= self._air_time_freefall_death

        if (not (abs(self.dash_timer) <= self.dash_burst_2)) or near_freefall_death:
            # self._drawcircle_starfn(surface=surf, center=(self.pos - offset), radius=self.calculate_bezier_particle_radius() * 1.328)
            # if near_freefall_death and (is_mid_air := not any(self.collisions.__dict__.values())) and is_mid_air: # note: is_mid_air seems unreliable as it constantly flips on off since it listens to keyup and keydown movements
            #     self._drawcircle_starfn(surface=surf, center=(self.pos - offset), radius=self.calculate_bezier_particle_radius() * 1.328)
            # if not self.game.screen.get_rect().contains(self.rect) and self.air_timer >= self._air_time_freefall_death:  # dying
            #     self._drawcircle_starfn(surface=surf, center=(self.pos - offset), radius=pre.SIZE.PLAYERSTARDASHRADIUS[0])
            pass
        else:  # if not dashing ^_^
            if self.did_land:  # temporary makeshift dust particles
                dust_offset = (1, 2)
                dust_center = pg.Vector2(
                    (self.rect.midbottom[0] + dust_offset[0], self.rect.midbottom[1] + dust_offset[1])
                    if self.flip  # ===-----====
                    else (self.rect.midbottom[0] - dust_offset[0], self.rect.midbottom[1] + dust_offset[1])
                )

                pg.draw.circle(surf, pg.Color("cyan"), dust_center - offset, 3, 1)
                pg.draw.circle(surf, pg.Color("gray"), dust_center - (1, 1) - offset, 3, 1)
                pg.draw.circle(surf, pg.Color("cyan"), dust_center + (3, -2) - offset, 2, 1)
                pg.draw.circle(surf, pg.Color("gray"), dust_center + (4, -3) - offset, 1, 1)
                pg.draw.circle(surf, pg.Color("silver"), dust_center - (3, 3) - offset, 2, 1)

            super().render(surf, offset)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
