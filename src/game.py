from __future__ import annotations


"""
# TODO:
    - [ ] create fallthrough platform ramps

"""

import itertools as it
import math
import queue
import sys
import threading
import time
import tracemalloc
from collections import deque
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from os import listdir, path
from pathlib import Path
from random import randint, random, uniform
from typing import List  # pyright:ignore
from typing import Final, NoReturn, Optional, Set  # pyright: ignore

import pygame as pg


try:
    from memory_profiler import profile  # pyright: ignore
except ImportError as e:
    print(f"failed to import dev package in {__file__}:\n\t{e}")
    exit(2)

import internal.prelude as pre
from internal.assets import Assets
from internal.camera import SimpleCamera
from internal.entities import Action, Enemy, Player
from internal.hud import render_debug_hud
from internal.particle import Particle
from internal.spark import Spark
from internal.spawner import Portal
from internal.stars import Stars
from internal.tilemap import Tilemap


if pre.DEBUG_GAME_TRACEMALLOC:
    tracemalloc.start()


def quit_exit(context: str = "") -> NoReturn:
    if pre.DEBUG_GAME_CACHEINFO:  # lrucache etc...
        print(f"{pre.hsl_to_rgb.cache_info() = }")

    if pre.DEBUG_GAME_TRACEMALLOC:
        snapshot = tracemalloc.take_snapshot()
        stat_key_type = ("traceback", "filename", "lineno")
        top_stats = snapshot.statistics(stat_key_type[0])

        print("Top memory allocations:")
        for stat in top_stats[:30]:
            print(stat)

    if context:
        print(f"{context}")

    pg.quit()
    sys.exit()


class AppState(Enum):
    GAMESTATE = auto()
    MENUSTATE = auto()


class GameState(Enum):
    PLAY = auto()
    PAUSE = auto()
    EXIT = auto()
    NEXTLEVEL = auto()


# NOTE(lloyd): Use In StartScreen
class MenuItemType(IntEnum):
    PLAY = auto(0)
    OPTIONS = auto()
    CREDITS = auto()
    EXIT = auto()


# PERF: Can just use an array initialized
MENU_ITEMS: List[str] = [
    "PLAY",
    "OPTIONS",
    "CREDITS",
    "EXIT",
]
# MENU_ITEMS: Dict[MenuItemType] = {
#     MenuItemType.PLAY: "PLAY",
#     MenuItemType.OPTIONS: "OPTIONS",
#     MenuItemType.CREDITS: "CREDITS",
#     MenuItemType.EXIT: "EXIT",
# }

MAX_MENU_ITEMS = len(MENU_ITEMS)  # MenuItemType enumerations


@dataclass
class GameCheckpointState:
    player_position: tuple[float, float]
    enemy_positions: list[tuple[float, float]]


@dataclass
class Background:
    depth: Final[float]
    pos: pg.Vector2  # topleft
    speed: float


@dataclass
class SFX:
    """Sound Effects"""

    ambienceheartbeatloop: pg.mixer.Sound
    dash: pg.mixer.Sound
    dashbassy: pg.mixer.Sound
    hit: pg.mixer.Sound
    hitmisc: pg.mixer.Sound
    hitwall: pg.mixer.Sound
    jump: pg.mixer.Sound
    jumplanding: pg.mixer.Sound
    playerspawn: pg.mixer.Sound
    portaltouch: pg.mixer.Sound
    shoot: pg.mixer.Sound
    shootmiss: pg.mixer.Sound
    teleport: pg.mixer.Sound


def get_user_config(filepath: Path) -> pre.UserConfig:
    config: Optional[dict[str, str]] = pre.UserConfig.read_user_config(filepath=filepath)

    if not config:
        print("error while reading configuration file at", repr(filepath))
        return pre.UserConfig.from_dict({})

    return pre.UserConfig.from_dict(config)


class Game:
    @profile
    def __init__(self) -> None:
        """
        |tags:init,game,gameloop|
        """
        pg.init()

        self.mainscreen = None  # menu | loading | game

        display_flag = pg.DOUBLEBUF | pg.RESIZABLE | pg.NOFRAME | pg.HWSURFACE  # SCLAED | FULLSCREEN
        # HWSURFACE flag does nothing in pygameg ver2.0+, DOUBLEBUF has some use, but not a magic speed up flag.
        # See https://www.pygame.org/docs/tut/newbieguide.html

        self.screen = pg.display.set_mode(pre.DIMENSIONS, display_flag)

        pg.display._set_autoresize(False)  # pyright: ignore |> see github:pygame/examples/resizing_new.py
        pg.display.set_caption(pre.CAPTION)

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        # font author suggest using font size in multiples of 9
        self.fontface_path = pre.FONT_PATH / "8bit_wonder" / "8-BIT WONDER.TTF"
        self.font = pg.font.Font(self.fontface_path, 18)
        self.font_sm = pg.font.Font(self.fontface_path, 12)
        self.font_xs = pg.font.Font(self.fontface_path, 9)

        if pre.DEBUG_GAME_HUD:
            self.font_hud = pg.font.SysFont(name=("monospace"), size=7, bold=True)

        self.clock = pg.time.Clock()
        self.dt: float = 0.0  # delta time == 1 / framerate(fps) or pygame.clock.tick() / 1000

        if pre.DEBUG_GAME_HUD:
            self.clock_dt_recent_values: deque[pre.Number] = deque([self.dt, self.dt])

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        self.config_handler: pre.UserConfig = get_user_config(pre.CONFIG_PATH)

        self.assets = Assets.initialize_assets()

        _sfxpath = pre.SFX_PATH
        _sound = pg.mixer.Sound

        self.sfx = SFX(
            ambienceheartbeatloop=_sound(_sfxpath / "ambienceheartbeatloop.wav"),
            dash=_sound(_sfxpath / "dash.wav"),
            dashbassy=_sound(_sfxpath / "dash.wav"),
            hit=_sound(_sfxpath / "hit.wav"),
            hitmisc=_sound(_sfxpath / "hitmisc.wav"),
            hitwall=_sound(_sfxpath / "hitwall.wav"),
            jump=_sound(_sfxpath / "jump.wav"),
            jumplanding=_sound(_sfxpath / "jumplanding.wav"),
            playerspawn=_sound(_sfxpath / "playerspawn.wav"),
            portaltouch=_sound(_sfxpath / "portaltouch.wav"),
            shoot=_sound(_sfxpath / "shoot.wav"),
            shootmiss=_sound(_sfxpath / "shootmiss.wav"),
            teleport=_sound(_sfxpath / "teleport.wav"),
        )

        self.sfx.ambienceheartbeatloop.set_volume(0.1)
        self.sfx.dash.set_volume(0.2)
        self.sfx.dashbassy.set_volume(0.2)
        self.sfx.hit.set_volume(0.2)
        self.sfx.hitmisc.set_volume(0.2)
        self.sfx.hitwall.set_volume(0.2)
        self.sfx.jump.set_volume(0.4)
        self.sfx.jumplanding.set_volume(0.3)
        self.sfx.playerspawn.set_volume(0.2)
        self.sfx.portaltouch.set_volume(0.2)
        self.sfx.shoot.set_volume(0.1)
        self.sfx.shootmiss.set_volume(0.2)
        self.sfx.teleport.set_volume(0.2)

        self._player_starting_pos: Final = pg.Vector2(50, 50)
        self.player = Player(self, self._player_starting_pos.copy(), pg.Vector2(pre.SIZE.PLAYER))
        self.player_spawner_pos: Optional[pg.Vector2] = None

        self.gcs_deque: deque[GameCheckpointState] = deque([])
        # self.player_gcs_pos_before_death: Optional[pg.Vector2] = None

        self._star_count: Final[int] = min(64, max(16, int(self.config_handler.star_count) or pre.TILE_SIZE * 2))
        self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.screenshake = 0
        self.gameover = False

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        self.scroll_ease: Final = pg.Vector2(1 / 30, 1 / 30)
        self.camerasize = self.display.get_size()
        self.camera = SimpleCamera(size=self.camerasize)

        # when abs transition is 30 -> opaque screen see nothing
        # and when transition is 0  -> see everything so load level when all black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        self._max_screenshake: Final = pre.TILE_SIZE

        self._level_map_count: Final[int] = len(listdir(pre.MAP_PATH))

        # Edit level manually for quick feedback gameplay iterations
        ################################################################################################
        self.level = 5
        self.levels_space_theme = {0, 1, 2, 3, 4, 5}  # ^_^ so all levels??!!!
        ################################################################################################

        # seedling: Mon May 13 08:20:31 PM IST 2024
        self.player_dash_enemy_collision_count = 0  # possible to farm this by dying repeatedly but that's alright for now

        self.running = True

    # @profile
    def reset_state_on_gameover(self) -> None:
        if pre.DEBUG_GAME_PRINTLOG:
            print(f"resetting after gameover...")

        self.camera.reset()

        if 0:
            self.clock = pg.time.Clock()
            self.dt = 0

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        if self.level in self.levels_space_theme:
            self.player = Player(self, self._player_starting_pos.copy(), pg.Vector2(pre.SIZE.PLAYER))
            self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)
            # self.tilemap = Tilemap(self, pre.TILE_SIZE)
        self.screenshake = 0
        self.gcs_deque.clear()
        self.level = 0
        self.player_dash_enemy_collision_count = 0

        if pre.DEBUG_GAME_PRINTLOG:
            print(f"resetting completed")

    # @profile
    def run(self) -> None:
        """This game loop runs continuously until the player opts out via inputs.

        Each iteration, computes user input non-blocking events, updates state
        of the game, and renders the game.
        """

        level_music_filename = "intro_loop.wav"

        match self.level:
            case 0:
                level_music_filename = "level_0.wav"

            case 1:
                level_music_filename = "theme_2.wav"

            case 2:
                level_music_filename = "level_2.wav"

            case 3:
                level_music_filename = "level_2.wav"

            case 4:
                level_music_filename = "level_2.wav"

            case 5:
                level_music_filename = "level_2.wav"

            case _:
                # NOTE: use a prev variable to hold last level music played if
                # we want to let it followthrough and avoid playing via pg.mixer.play()
                assert level_music_filename == "intro_loop.wav" and "expected default level music filename"
                pass

        if self.level != 5:
            pg.mixer.music.load((pre.SRC_DATA_PATH / "music" / level_music_filename).__str__())
            pg.mixer.music.set_volume(0.2)
            pg.mixer.music.play(-1)

        if self.level == 0:
            self.sfx.playerspawn.play()

        # gc.freeze()
        while self.running:
            self.dt = self.clock.tick(pre.FPS_CAP) * 0.001

            self.display.fill((0, 0, 0, 0))

            if self.level in self.levels_space_theme:
                self.display_2.fill((30, 30, 30))

            self.events()
            self.update()
            self.render()
        # gc.unfreeze()

    def events(self) -> None:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                quit_exit("Exiting...")
            if event.type == pg.KEYDOWN and event.key == pg.K_F4:
                quit_exit("Exiting...")
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.running = False

            if event.type == pg.VIDEORESIZE:
                self.screen = pg.display.get_surface()

            if event.type == pg.KEYDOWN:
                if event.key in (pg.K_LEFT,):  # pg.K_a):
                    self.movement.left = True

                if event.key in (pg.K_RIGHT,):  # pg.K_d):
                    self.movement.right = True

                if event.key in (pg.K_SPACE, pg.K_c):  # check jump keydown
                    if self.player.time_jump_keyup:  # reset manually
                        self.player.time_jump_keyup = None

                    self.player.time_jump_keydown = time.time()

                    if self.player.jump():
                        self.sfx.jump.play()

                if event.key in (pg.K_x, pg.K_v):
                    self.player.dash()

                if event.key == pg.K_s:  # WASD like S | K
                    self.gcs_record_checkpoint()
                if event.key == pg.K_a:  # WASD like A | J
                    self.gcs_rewind_recent_checkpoint()
                if event.key == pg.K_d:  # WASD like D | L
                    self.gcs_rewind_checkpoint()
                if event.key == pg.K_q:  # WASD like Q | E
                    self.gcs_remove_recent_checkpoint()
                if event.key == pg.K_e:  # WASD like E | O
                    self.gcs_remove_checkpoint()

            if event.type == pg.KEYUP:
                if event.key in (pg.K_LEFT,):  # pg.K_a):
                    self.movement.left = False

                if event.key in (pg.K_RIGHT,):  # pg.K_d):
                    self.movement.right = False

                if event.key in (pg.K_SPACE, pg.K_c):  # check jump keyup
                    if self.player.time_jump_keydown and not self.player.time_jump_keyup:
                        self.player.time_jump_keyup = time.time()
                        self.player.delta_time_jump_keydown_keyup = self.player.time_jump_keyup - self.player.time_jump_keydown

                        if (
                            self.player.delta_time_jump_keydown_keyup < self.player.jump_buffer_interval
                            and self.player.air_timer <= self.player.max_air_time * 5
                            and not self.player.wallslide
                            and not self.player.collisions.left
                            and not self.player.collisions.right
                            and -self.player.jump_force <= self.player.velocity.y < 0
                            and abs(self.player.velocity.x) <= 0.1
                        ):
                            if self.player.dash_timer and self.player.velocity.y <= 0.1:
                                self.player.velocity.y = -3.0

                                if self.player.last_movement.x:
                                    self.player.velocity.x = -2.00 if self.player.flip else 2.00

                            elif self.player.coyote_timer and self.player.air_timer <= self.player.max_air_time * 3:  # 3 -> jump force
                                self.player.velocity.y += 1.35

                                if self.player.last_movement.x:
                                    self.player.velocity.x = -2.25 if self.player.flip else 2.25

                                    if 1 < abs(self.player.velocity.x) < 2:
                                        self.player.velocity.x *= 1.618
                                    elif 0 < abs(self.player.velocity.x) <= 1:
                                        self.player.velocity.x *= 0.5

    def render(self) -> None:
        """Render display."""
        # ===-Create background buffer--------------------------------------===
        # ===---------------------------------------------------------------===
        if self.level in self.levels_space_theme:
            pass
        else:
            self.display_2.blit(self.bg_blue_sky_surf, (0, 0))
            self.display_2.blit(self.bg_cloud_surf, self.bg_cloud.pos)
            self.display_2.blit(self.bg_cloud_surf, (self.bg_cloud.pos + (self.bg_display_w, 0)))  # wrap around
            self.display_2.blit(self.bg_mountain_surf, self.bg_mountain.pos)
            self.display_2.blit(self.bg_mountain_surf, (self.bg_mountain.pos + (self.bg_display_w, 0)))  # wrap around
        # ===---------------------------------------------------------------===

        # ===-Create a transition surface with a circular cutout------------===
        # ===---------------------------------------------------------------===
        if self.transition and (
            transition := abs(self.transition),
            tilesize := self.tilemap.tilesize,
            displaysize := self.display.get_size(),
            surf := pg.Surface(displaysize).convert(),
            # Declare and Initialize Variables
            speed := 16 + 1 / self.transition,
            radius := (tilesize - 1 - transition) * speed,
            center := (displaysize[0] // 2, displaysize[1] // 2),
        ):
            # Update Surface
            if not self.gcs_deque and not self.dead:
                center = self.player.rect.center
                entering = self._transition_lo < self.transition < self._transition_lo // 2

                radius = (tilesize * 2 + 4) if entering else ((tilesize * 2 - transition) * speed * 0.8)
            else:
                speed /= 2.0

            # Draw Surface
            pg.draw.circle(surf, (255, 255, 255), center, radius)  # white color on screen acts as transparant mask
            surf.set_colorkey((255, 255, 255))  # ... and now anything outside of mask is opaque black
            self.display.blit(surf, (0, 0))
        # ===---------------------------------------------------------------===

        # ===-Final buffer swap 3-stage rendering---------------------------===
        # ===---------------------------------------------------------------===
        self.display_2.blit(self.display, (0, 0))

        dest = (
            ((shake * random()) - halfshake, (shake * random()) - halfshake)
            if (shake := self.screenshake, halfshake := shake * 0.5) and self.config_handler.screenshake
            else (0.0, 0.0)
        )

        self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), dest)

        pg.display.flip()
        # ===---------------------------------------------------------------===

    def _increment_player_dead_timer(self):
        if pre.DEBUG_GAME_PRINTLOG:
            print(f"{Path(__file__).name}: [{time.time():0.4f}] {self.dead = }")

        self.dead += 1

    def update(self) -> None:
        # Camera: update and parallax
        _target = self.player.rect
        snapy = _target.centery % self.level_map_dimension[1]

        if snapy < self.camerasize[1]:  # snap camera to top floor of map area
            snapy = _target.centery // 4
        elif snapy > (self.level_map_dimension[1] - self.camerasize[1]) + (self.player.size.y * 2):  # snap camera to ground floor of map area
            snapy = _target.centery + self.camerasize[1] // 2

        self.camera.update((_target.centerx, snapy), map_size=self.level_map_dimension, dt=self.dt)

        render_scroll = self.camera.render_scroll

        if pre.DEBUG_GAME_CAMERA:
            self.camera.debug(surf=self.display, target_pos=(int(_target.x), int(_target.y)))

        self.bg_cloud.pos.x -= math.floor(math.floor(uniform(2, 3) * 100 * self.bg_cloud.speed * self.bg_cloud.depth) / 10) / 10

        if self.bg_cloud.pos.x < -self.bg_display_w:  # <-480
            self.bg_cloud.pos.x = 0

        self.bg_mountain.pos.x = math.floor(math.floor(self.bg_mountain.pos.x - self.camera.render_scroll[0]) * self.bg_mountain.depth * self.bg_mountain.speed)  # works

        if self.bg_mountain.pos.x < -self.bg_display_w:
            self.bg_mountain.pos.x = 0

        # Mouse: cursor position with offset
        raw_mouse_pos = pg.Vector2(pg.mouse.get_pos()) / pre.RENDER_SCALE
        mouse_pos: pg.Vector2 = raw_mouse_pos + render_scroll

        if 0:  # Render mouse blog
            if (mouse_surf := self.assets.misc_surf.get("mouse")) and mouse_surf:
                mask = pg.mask.from_surface(mouse_surf)
                silhouette = mask.to_surface(setcolor=(20, 20, 21, math.floor(255 / 2)), unsetcolor=(0, 0, 0, 0))
                dest = raw_mouse_pos - pg.Vector2(mouse_surf.get_size()) // 2

                for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    self.display.blit(silhouette, (dest - (pg.Vector2(offset) * pre.TILE_SIZE)))

        self.screenshake = max(0, self.screenshake - 1)

        # Check for game level transitions
        # Win condition
        if self.collected_enemies and self.touched_portal:
            self.transition += 1

            # Check if transition to the next level is required
            if self.transition > self._transition_hi:
                if self.lvl_no_more_levels_left():
                    self.gameover = True  # LoadingScreen will reset this later
                    self.reset_state_on_gameover()
                else:
                    self.lvl_increment_level()

                # Trigger loading screen
                self.running = False

        if self.transition < self._transition_mid:
            self.transition += 1

        if self.dead:
            self._increment_player_dead_timer()  # self.dead += 1

            # ease into incrementing for level change till _hi
            if self.dead >= self._dead_mid:
                self.transition = min(self._transition_hi, self.transition + 1)

            if self.dead >= self._dead_hi:
                self.lvl_load_level(self.level)

        # replenish health and revert to last checkpoint instead of "death"
        if self.dead_hit_skipped_counter == 0 and self.respawn_death_last_checkpoint:
            if 0:
                self.gcs_rewind_checkpoint(record_current=False)
            else:
                self.gcs_rewind_recent_checkpoint(record_current=False)

            self.respawn_death_last_checkpoint = False

        # Flametorch: particle animation
        if 0:
            # fmt: off
            odds_of_flame: float = (6 * 0.001) * 49_999  # note: big number 49_999 controls spawn rate

            self.particles.extend(Particle( game=self, p_kind=pre.ParticleKind.FLAME, pos=pg.Vector2((rect.x - random() * rect.w), (rect.y - random() * rect.h - 4)), velocity=pg.Vector2(uniform(-0.03, 0.03), uniform(0.0, -0.03)), frame=randint(0, 20),)
                for rect in self.ftorch_spawners.copy() if (random() * odds_of_flame) < (rect.w * rect.h))

            self.particles.extend(Particle( game=self, p_kind=pre.ParticleKind.FLAMEGLOW, pos=pg.Vector2((rect.x - random() * rect.w), (rect.y - random() * rect.h - 4)), velocity=pg.Vector2(uniform(-0.2, 0.2), uniform(0.1, 0.3)), frame=randint(0, 20),)
                for rect in self.ftorch_spawners.copy() if (random() * odds_of_flame * 8) < (rect.w * rect.h))
            # fmt: on

        # Stars: backdrop update and render
        if self.level in self.levels_space_theme:
            self.stars.update()  # stars drawn behind everything else
            self.stars.render(self.display_2, render_scroll)  # display_2 blitting avoids masks depth

        # Tilemap: render
        self.tilemap.render(self.display, render_scroll)

        # ===---------------------------------------------------------------===
        # ===-Update and Draw drop-point location zones---------------------===
        if not self.dead and (spawner_position := self.player_spawner_pos) and spawner_position:
            success_width, success_height = 48, 6
            rect_value = (spawner_position.x - success_width / 2 - render_scroll[0], (spawner_position.y - render_scroll[1]) + 16 - success_height, success_width, success_height)
            pg.draw.rect(self.display, pre.hex_to_rgb("13c299"), rect_value)

            enemy_count = len(self.enemies)

            for enemy in self.enemies:
                if abs(enemy.pos.y - self.player_spawner_pos.y) < 32:
                    enemy_count -= 1

                    if enemy not in self.collected_enemies_seen:
                        self.collected_enemies_counter += 1
                        self.collected_enemies_seen.add(enemy)

            if enemy_count == 0:
                rect_value = (spawner_position.x - success_width / 2 - render_scroll[0], (spawner_position.y - render_scroll[1]) + success_height, success_width, success_height)
                pg.draw.rect(self.display, pre.hex_to_rgb("cc1299"), rect_value)
                self.collected_enemies = True
        # ===---------------------------------------------------------------===

        # ===-Portal: detect and render-------------------------------------===
        # ===---------------------------------------------------------------===
        if not self.touched_portal:  # <- note: this disappears very fast
            for i, portal in enumerate(self.portal_spawners):

                if self.collected_enemies and self.player.rect.colliderect(portal.rect()):
                    self.touched_portal = True

                    if self.level != self._level_map_count:
                        self.sfx.portaltouch.play()

                self.display.blit(portal.assets[i], portal.pos - render_scroll)
        # ===---------------------------------------------------------------===

        # ===Enemy: update and render0--------------------------------------===
        # ===---------------------------------------------------------------===
        for enemy in self.enemies.copy():
            kill_animation = enemy.update(self.tilemap, pg.Vector2(0, 0))
            enemy.render(self.display, render_scroll)

            if kill_animation:
                self.enemies.remove(enemy)
        # ===---------------------------------------------------------------===

        # ===-Update Interactive Spawners-----------------------------------===
        # ===---------------------------------------------------------------===
        for rect_spike in self.spike_spawners:
            if self.player.rect.colliderect(rect_spike):
                self._increment_player_dead_timer()  # self.dead += 1

        for rect_bp in self.bouncepad_spawners:
            if self.player.rect.colliderect(rect_bp):
                did_jump = self.player.jump()

                # HACK: Avoid triggering freefall death and allow infinite jumps

                if did_jump:
                    self.player.air_timer = 0
                    self.player.velocity.y = -5

                    self.sfx.jump.play()

            for enemy in self.enemies:
                if enemy.rect.colliderect(rect_bp):
                    enemy.velocity.y -= 3

                    # HACK: Avoid infinite jump at the same spot

                    if enemy.rect.left < rect_bp.left:
                        enemy.velocity.x -= 2.0
                    elif enemy.rect.right > rect_bp.right:
                        enemy.velocity.x += 2.0
                    else:
                        enemy.velocity.x += randint(-3, 3)

                    self.sfx.jump.play()

            if 0:  # debug
                self.display.blit(pg.Surface(rect_bp.size), (rect_bp.x - render_scroll[0], rect_bp.y - render_scroll[1]))  # for debugging
        # ===---------------------------------------------------------------===

        # ===-Update and Draw GameCheckpoints ------------------------------===
        # ===---------------------------------------------------------------===
        for i, state in enumerate(self.gcs_deque):
            _r = 2 * (1 + 1 / (1 + i))  # radius -> 2
            center = (int(state.player_position[0] - render_scroll[0]), int(state.player_position[1] - render_scroll[1]))

            pg.draw.circle(self.display, pre.GREENGLOW, center, radius=(_r + 1))
            pg.draw.circle(self.display, pre.GREENBLURB, center, radius=_r)

            if 0:  # debugging
                self.draw_text(int(state.player_position[0] - render_scroll[0]), int(state.player_position[1] - render_scroll[1]), self.font_xs, pre.COLOR.FLAMEGLOW, f"{i+1}")
        # ===---------------------------------------------------------------===

        # ===-Player: update and render-------------------------------------===
        # ===---------------------------------------------------------------===
        if not self.dead:
            self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
            self.player.render(self.display, render_scroll)
        # ===---------------------------------------------------------------===

        # ===-Gun: projectiles and sparks-----------------------------------===
        # ===---------------------------------------------------------------===
        for projectile in self.projectiles:
            projectile.pos[0] += projectile.velocity
            projectile.timer += 1

            img = self.assets.misc_surf["projectile"]
            dest = (projectile.pos[0] - (img.get_width() // 2) - render_scroll[0], projectile.pos[1] - (img.get_height() // 2) - render_scroll[1])

            self.display.blit(img, dest)

            # Projectile post render: update
            projectile_x, projectile_y = int(projectile.pos[0]), int(projectile.pos[1])  # int -> precision for grid system

            if self.tilemap.maybe_solid_gridtile_bool(pg.Vector2(projectile_x, projectile_y)):
                self.projectiles.remove(projectile)

                # Wall sparks bounce opposite to projectile's direction
                spark_speed, spark_direction = 0.5, math.pi if (projectile.velocity > 0) else 0  # note: unit circle direction (0 left, right math.pi)
                self.sparks.extend(Spark(projectile.pos, angle=(random() - spark_speed + spark_direction), speed=(2 + random())) for _ in range(4))

                self.sfx.hitwall.play()
            elif projectile.timer > 360:
                self.projectiles.remove(projectile)
            elif abs(self.player.dash_timer) < self.player.dash_burst_2:  # vulnerable player

                if self.player.rect.collidepoint(projectile_x, projectile_y):

                    # Player looses health but still alive if idle/still
                    if (self.player.action == Action.IDLE) and (self.dead_hit_skipped_counter < self.player.max_dead_hit_skipped_counter):
                        self.screenshake = max(self._max_screenshake, self.screenshake - 0.5)

                        self.projectiles.remove(projectile)
                        self.sparks.extend(Spark(pg.Vector2(self.player.rect.center), angle, speed) for _ in range(30) if (angle := random() * math.pi * 2, speed := 2 + random()))

                        self.sfx.hitmisc.play()

                        self.dead_hit_skipped_counter += 1  # Todo: should reset this if players action state changes from idle to something else
                    else:
                        # Player death OR send back in time(checkpoint)
                        self.screenshake = max(self._max_screenshake, self.screenshake - 1)

                        self.projectiles.remove(projectile)
                        self.sparks.extend(
                            Spark(pg.Vector2(self.player.rect.center), angle, speed, pg.Color("cyan"))
                            for _ in range(30)
                            if (angle := random() * math.pi * 2, speed := 2 + random())
                        )
                        self.particles.extend(
                            Particle(self, pre.ParticleKind.PARTICLE, pg.Vector2(self.player.rect.center), velocity, frame)
                            for _ in range(30)
                            if (angle := (random() * math.pi * 2), speed := (random() * 5), velocity := pg.Vector2(math.cos(angle + math.pi) * speed / 2), frame := randint(0, 7))
                        )

                        self.sfx.hit.play()

                        # Note: Next iteration, when counter is 0 player pos is reverted to last checkpoint instead of death.
                        if (_death_by_projectile_enabled := 0) and _death_by_projectile_enabled:
                            self._increment_player_dead_timer()
                        else:
                            self.dead_hit_skipped_counter = 0  # replenish health
                            self.respawn_death_last_checkpoint = True
        # ===---------------------------------------------------------------===

        # ===-Update Sparks-------------------------------------------------===
        # ===---------------------------------------------------------------===
        for spark in self.sparks.copy():
            kill_animation = spark.update()
            spark.render(self.display, offset=render_scroll)

            if kill_animation:
                self.sparks.remove(spark)
        # ===---------------------------------------------------------------===

        # ===-Display Mask: Drop Shadow Trick-------------------------------===
        # ===---------------------------------------------------------------===
        if 0:
            display_mask = pg.mask.from_surface(self.display)
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))

            for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.display_2.blit(display_silhouette, offset)
        # ===---------------------------------------------------------------===

        # ===-Update particles----------------------------------------------===
        # ===---------------------------------------------------------------===
        for particle in self.particles.copy():
            kill_animation = particle.update()
            particle.render(self.display, render_scroll)

            if kill_animation:
                match particle.kind:
                    case pre.ParticleKind.PARTICLE:
                        if self.level in self.levels_space_theme:  # note: frame count is static after kill_animation
                            amplitude_clamp = 0.328
                            decay_initial_value, decay_factor, decay_iterations = (1, 0.95, particle.animation.frame)
                            decay = decay_initial_value * (decay_factor**decay_iterations)
                            chaos = amplitude_clamp * math.sin(particle.animation.frame * 0.035)
                            particle.velocity.x -= math.copysign(1, particle.velocity.x) * chaos * decay * uniform(8, 16)
                            particle.velocity.y -= math.copysign(1, particle.velocity.y) * chaos * decay * uniform(8, 16)
                            if random() < uniform(0.01, 0.025):
                                self.particles.remove(particle)
                        else:
                            self.particles.remove(particle)
                    case _:
                        self.particles.remove(particle)
        # ===---------------------------------------------------------------===

        # ===-Update HUD----------------------------------------------------===
        # ===---------------------------------------------------------------===
        if (_flag_show_hud := 0) and _flag_show_hud:
            hud_size = (200, 48)
            hud_pad = pg.Vector2(self.font_xs.size("0")[0] / 2, self.font_xs.size("0")[1] / 2)
            hud_dest = pg.Vector2(0, 0)

            hud_bg_surf = pg.Surface(hud_size, flags=pg.SRCALPHA).convert_alpha()
            hud_bg_surf.set_colorkey(pg.Color("black"))
            hud_bg_surf.fill(pre.CHARCOAL)
            hud_bg_surf.set_alpha(10)

            def hud_draw_text(surf: pg.SurfaceType, x: int, y: int, font: pg.font.Font, color: pg.Color | pre.ColorValue | pre.ColorKind, text: str) -> pg.Rect:
                surf_ = font.render(text, True, color)
                rect = surf_.get_rect()
                rect.midtop = (x, y)
                return surf.blit(surf_, rect)

            hud_surf = pg.Surface(hud_size, flags=pg.SRCALPHA).convert_alpha()
            hud_surf.blit(hud_bg_surf, (0, 0))

            _ = hud_surf.blit(self.assets.entity["player"], hud_dest + (0, hud_pad.y))
            label = f"{math.ceil(100*(self.player.max_dead_hit_skipped_counter -  self.dead_hit_skipped_counter)/self.player.max_dead_hit_skipped_counter)}"
            hud_rect = hud_draw_text(hud_surf, 40, int(hud_pad.y), self.font_xs, pg.Color("purple"), label)

            _ = hud_surf.blit(self.assets.entity["enemy"], hud_dest + (50 + hud_rect.x + hud_rect.w + hud_pad.x, hud_pad.y))
            # label = f"{len(self.enemies) - self.collected_enemies_counter}"
            label = f"{self.player_dash_enemy_collision_count}"
            hud_rect = hud_draw_text(hud_surf, 80, int(hud_pad.y), self.font_xs, pg.Color("yellow"), label)

            _ = hud_surf.blit(self.assets.entity["enemy"], hud_dest + (100 + hud_rect.x + hud_rect.w + hud_pad.x, hud_pad.y))
            label = f"{len(self.enemies) - self.collected_enemies_counter}"
            hud_rect = hud_draw_text(hud_surf, 150, int(hud_pad.y), self.font_xs, pg.Color("cyan"), label)

            _ = self.display.blit(hud_surf, hud_dest, special_flags=pg.BLEND_ALPHA_SDL2)

            if pre.DEBUG_GAME_HUD:
                try:
                    mousepos = [math.floor(mouse_pos.x), math.floor(mouse_pos.y)]
                    render_debug_hud(self, self.display_2, render_scroll, (mousepos[0], mousepos[1]))
                    self.clock_dt_recent_values.appendleft(self.dt)
                    if len(self.clock_dt_recent_values) is pre.FPS_CAP:
                        self.clock_dt_recent_values.pop()
                except Exception as e:
                    print(f"exception during rendering debugging HUD: {e}")
        # ===---------------------------------------------------------------===

    # @profile
    def set_mainscreen(self, scr: Optional["StartScreen | LoadingScreen | CreditsScreen | Game"]):
        # delete existing screen
        if self.mainscreen != None:
            del self.mainscreen
            self.mainscreen = None

        # show new screen
        self.mainscreen = scr

        if self.mainscreen != None:
            self.mainscreen.run()

        if self.gameover:
            return AppState.MENUSTATE, GameState.EXIT
        elif not self.running:  # note: we could just set gamestate form keyevent or update loop
            return AppState.GAMESTATE, GameState.NEXTLEVEL

    def lvl_no_more_levels_left(self) -> bool:
        return self.level + 1 >= self._level_map_count

    def lvl_increment_level(self):
        self.gcs_deque.clear()
        self.camera.reset()
        prev = self.level
        self.level = min(self.level + 1, self._level_map_count - 1)
        return dict(prev=prev, next=self.level)

    def _lvl_load_level_map(self, map_id: int):
        self.tilemap.load(path=path.join(pre.MAP_PATH, f"{map_id}.json"))

    # @profile
    def lvl_load_level(self, map_id: int, progressbar: Optional[queue.Queue[int]] = None) -> None:
        progress = 0

        if progressbar:
            progressbar.put(progress)

        self._lvl_load_level_map(map_id)
        self.level_map_dimension = self.tilemap.cur_level_map_dimension  # 1470 approx for level1, 480 for leve12

        if pre.DEBUG_GAME_PRINTLOG:
            print(f"{Path(__file__).name}: [{time.time():0.4f}] {self.level_map_dimension = }")  # FIX: dual loading at game over

        progress += 5

        if progressbar:
            progressbar.put(progress)

        self.projectiles: list[pre.Projectile] = []
        self.sparks: list[Spark] = []

        bg_blue_sky_surf = self.assets.misc_surf["bg1"]
        bg_blue_sky_surf_yflipped = pg.transform.flip(bg_blue_sky_surf.copy(), 0, 1)
        self.bg_blue_sky_surf = pg.transform.average_surfaces((bg_blue_sky_surf, bg_blue_sky_surf_yflipped))

        bg_cloud_surf = self.assets.misc_surf["bg2"]
        self.bg_cloud_surf = bg_cloud_surf

        bg_mountain_surf = self.assets.misc_surf["bg3"]
        self.bg_mountain_surf = bg_mountain_surf

        if self.level in self.levels_space_theme:
            self.grid_surf = pre.create_surface(self.display.get_size(), colorkey=(0, 0, 0), fill_color=(0, 0, 0)).convert()
            grid_surf_pixels = pg.surfarray.pixels3d(self.grid_surf)  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]

            for x in range(0, pre.DIMENSIONS_HALF[0], self.tilemap.tilesize):
                grid_surf_pixels[x, :] = (26, 27, 26)
            for y in range(0, pre.DIMENSIONS_HALF[1], self.tilemap.tilesize):
                grid_surf_pixels[:, y] = (26, 27, 26)
            # Convert the pixel array back to a surface
            del grid_surf_pixels  # Unlock the pixel array

        self.bg_display_w = pre.DIMENSIONS_HALF[0]  # 480
        self.bg_cloud = Background(depth=0.1 or 0.2, pos=pg.Vector2(0, 0), speed=0.5)
        self.bg_mountain = Background(depth=0.6, pos=pg.Vector2(0, 0), speed=0.4)  # note: higher speed causes janky wrapping of bg due to render scroll ease by 1 or 2 tilesize

        progress += 10

        if progressbar:
            progressbar.put(progress)

        self.ftorch_spawners = [
            pg.Rect(
                max(4, pre.SIZE.FLAMETORCH[0] // 2) + torch.pos.x,
                max(4, pre.SIZE.FLAMETORCH[1] // 2) + torch.pos.y,
                pre.SIZE.FLAMETORCH[0],
                pre.SIZE.FLAMETORCH[1],
            )
            for torch in self.tilemap.extract([("decor", 2)], keep=True)
        ]
        self.bouncepad_spawners = [
            pg.Rect(tileitem.pos.x, tileitem.pos.y + 32 - 8, pre.TILE_SIZE, pre.TILE_SIZE)  # 8 thickness  # actual w 16  # actual h 64
            for tileitem in self.tilemap.extract([("bouncepad", 0), ("bouncepad", 1), ("bouncepad", 2), ("bouncepad", 3)], keep=True)
        ]
        self.spike_spawners = list(self.tilemap.spawn_spikes(self.tilemap.extract([("spike", 0), ("spike", 1), ("spike", 2), ("spike", 3)], keep=True)))

        progress += 10

        if progressbar:
            progressbar.put(progress)

        self.portal_spawners: list[Portal] = []
        self.enemies: list[Enemy] = []

        spawner_kinds: Final = (pre.SpawnerKind.PLAYER.value, pre.SpawnerKind.ENEMY.value, pre.SpawnerKind.PORTAL.value)
        increment = math.floor((70 - progress) / len(spawner_kinds))

        for spawner in self.tilemap.extract(list(zip(it.repeat(str(pre.TileKind.SPAWNERS.value), len(spawner_kinds)), spawner_kinds)), False):
            match pre.SpawnerKind(spawner.variant):
                case pre.SpawnerKind.PLAYER:  # coerce to a mutable list if pos is a tuple
                    self.player_spawner_pos = spawner.pos.copy()

                    if self.gcs_deque:
                        self.gcs_rewind_recent_checkpoint(record_current=False)
                    else:
                        self.player.pos = spawner.pos.copy()

                    self.player.air_timer = 0  # Reset time to avoid multiple spawns during fall
                case pre.SpawnerKind.ENEMY:
                    self.enemies.append(Enemy(self, spawner.pos, pg.Vector2(pre.SIZE.ENEMY)))
                case pre.SpawnerKind.PORTAL:
                    self.portal_spawners.append(Portal(self, pre.EntityKind.PORTAL, spawner.pos, pg.Vector2(pre.TILE_SIZE)))

            progress += increment

            if progressbar:
                progressbar.put(progress)

        if pre.DEBUG_GAME_ASSERTS:
            assert self.player is not None, f"want a spawned player. got {self.player}"
            assert (val := len(self.enemies)) > 0, f"want atleast 1 spawned enemy. got {val}"
            assert (val := len(self.portal_spawners)) > 0, f"want atleast 1 spawned portal. got {val}"

        self.particles: list[Particle] = []

        self.scroll = pg.Vector2(0.0, 0.0)  # note: seems redundant now

        self.dead = 0  # tracks if the player died -> 'reloads level'
        self.respawn_death_last_checkpoint = False
        self.dead_hit_skipped_counter = 0  # if player is invincible while idle and hit, count amout of shield that is being hit on

        self.touched_portal = False
        self.collected_enemies = False
        # self.collected_enemies_seen: List[Enemy] = []
        self.collected_enemies_seen: Set[Enemy] = set()
        self.collected_enemies_counter = 0

        self.transition = self._transition_lo

        if self.level != 0:
            self.sfx.playerspawn.play()

        progress = 100

        if progressbar:
            progressbar.put(progress)

        if 1:  # HACK: emulate loading heavy resources
            time.sleep(uniform(0.100, 0.250))

    def gcs_remove_recent_checkpoint(self) -> None:
        if not self.gcs_deque:
            return

        self.gcs_deque.popleft()

    def gcs_remove_checkpoint(self) -> None:
        if not self.gcs_deque:
            return

        self.gcs_deque.pop()

    def gcs_record_checkpoint(self, max_checkpoints: int = 3) -> None:
        self.gcs_deque.appendleft(
            GameCheckpointState(
                player_position=(self.player.pos.x, self.player.pos.y),
                enemy_positions=list((e.pos.x, e.pos.y) for e in self.enemies),
            )
        )

        match self.level:
            case 2 | 3:
                if self.gcs_deque.__len__() > 5:
                    self.gcs_deque.pop()

            case _:
                if self.gcs_deque.__len__() > max_checkpoints:
                    self.gcs_deque.pop()

    def gcs_rewind_checkpoint(self, record_current: bool = True) -> None:
        if not self.gcs_deque and self.player_spawner_pos:
            self.gcs_deque.appendleft(
                GameCheckpointState(
                    player_position=(self.player_spawner_pos.x, self.player_spawner_pos.y),
                    enemy_positions=list((e.pos.x, e.pos.y) for e in self.enemies),
                )
            )

        if not self.gcs_deque:
            return

        prev_gts = self.gcs_deque.pop()

        if record_current:
            self.gcs_record_checkpoint()

        next_pos = pg.Vector2(prev_gts.player_position)
        player_rect = self.player.rect

        for enemy in self.enemies:
            if player_rect.colliderect(enemy.rect):
                enemy.pos = next_pos.copy()

                if 0:
                    enemy.flip = not enemy.flip

                enemy.sleep_timer = enemy.max_sleep_time
                enemy.set_action(Action.SLEEPING)  # Note: if enemy was sleeping already, won't work

        self.player.pos = next_pos.copy()
        self.sfx.teleport.play()

    def gcs_rewind_recent_checkpoint(self, record_current: bool = True) -> None:
        if not self.gcs_deque and self.player_spawner_pos:
            self.gcs_deque.appendleft(
                GameCheckpointState(
                    player_position=(self.player_spawner_pos.x, self.player_spawner_pos.y),
                    enemy_positions=list((e.pos.x, e.pos.y) for e in self.enemies),
                )
            )

        if not self.gcs_deque:
            return

        prev_gcs = self.gcs_deque.popleft()

        if record_current:
            self.gcs_record_checkpoint()

        next_pos = pg.Vector2(prev_gcs.player_position)
        player_rect = self.player.rect

        for enemy in self.enemies:
            if player_rect.colliderect(enemy.rect):
                enemy.pos = next_pos.copy()

                if 0:
                    enemy.flip = not enemy.flip

                enemy.sleep_timer = enemy.max_sleep_time
                # Note: if enemy was sleeping already, won't work
                enemy.set_action(Action.SLEEPING)

        self.player.pos = next_pos.copy()
        self.sfx.teleport.play()

    def draw_text(self, x: int, y: int, font: pg.font.Font, color: pg.Color | pre.ColorValue | pre.ColorKind, text: str):
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        rect.midtop = (x, y)
        return self.display.blit(surf, rect)


class LoadingScreen:
    # @profile
    def __init__(self, game: Game, level: int) -> None:
        self.game = game
        self.level = level

        self.queue: queue.Queue[int] = queue.Queue()
        self.queue.put(0)
        self.progress: int = self.queue.get()  # 0% initially

        if pre.DEBUG_GAME_ASSERTS:  # self.queue.join()
            assert self.queue.qsize() == 0 or self.queue.empty()

        self.w, self.h = pre.DIMENSIONS_HALF
        self.fontsize = 18  # 9*2
        self.font = self.game.font_sm

        self.clock = pg.time.Clock()  # or use game's clock?

    # @profile
    def run(self) -> None:
        running = True
        self.bgcolor = pre.COLOR.BACKGROUND
        # ^^^^ todo: remove this, not used in the game but in other screens

        while running:
            loading_thread: Optional[threading.Thread] = None

            match self.level:
                case _:
                    loading_thread = threading.Thread(target=self.game.lvl_load_level, args=(self.level, self.queue))
                    loading_thread.start()
                # case _:
                #     # todo: load the next level/levels
                #     pass

            while True:
                # self.clock.tick(pre.FPS_CAP)
                self.events()
                self.update()
                self.render()

                if loading_thread and not loading_thread.is_alive():
                    _ = self.game.set_mainscreen(self.game)

                    if not self.game.running:
                        break

            # sync state changes
            if not self.game.running:
                self.game.running = True
                self.level = self.game.level

                if self.game.gameover:
                    running = False
                    # NOTE: placeholdere to impl a GameoverScreen

                    if 1:
                        self.game.gameover = False

    def events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()

            if event.type == pg.QUIT:
                self.running = False
                quit_exit()

    def update(self):
        if not self.queue.empty() or not self.queue.qsize() == 0:
            self.progress = self.queue.get()

    def render(self):
        # clear screen and render background
        self.game.display.fill(self.bgcolor)

        pbar_h = 30 // 6
        pbar_w = (self.w - self.w / 4) // 3

        x = self.w / 2 - pbar_w / 2
        y = self.h / 2

        pcounter = self.progress / 100

        if pcounter >= 1:
            pcounter = 1

        pbar_fill = pcounter * pbar_w
        pbar_outline_rect = pg.Rect(x - 10 / 2, y - 10 / 2, pbar_w + 20 / 2, pbar_h + 20 / 2)
        pbar_fill_rect = pg.Rect(x, y, pbar_fill, pbar_h)

        # draw bar
        pg.draw.rect(self.game.display, pre.WHITE, pbar_fill_rect)
        pg.draw.rect(self.game.display, pre.WHITE, pbar_outline_rect, 1)

        # draw text
        self.game.draw_text(
            self.w // 2 - self.fontsize // 2,
            self.h // 2 - self.fontsize // 2 - pbar_h - 50,
            self.font,
            pre.WHITE,
            f"World {self.game.level}",
        )

        dispmask: pg.Mask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))

        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)

        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))

        # *flip* the display
        pg.display.flip()


class CreditsScreen:
    def __init__(self, game: Game, level: int) -> None:
        # NOTE(lloyd): using this as Game.set_screen(screen: 'CreditsScreen |
        # Game | ...') requires each args passed to __init__ to have game and
        # level. doing this via manual inheritance. sigh OOP -_-
        self.game = game
        self.level = level

        self.w, self.h = pre.DIMENSIONS_HALF

        self.start_font = self.game.font_sm
        self.title_font = self.game.font

        self.bgcolor = pre.DARKCHARCOAL

        self.clock = pg.time.Clock()  # or use game's clock?
        self.running = True

        self.fps = self.clock.get_fps()

        self.creditroll_y = self.h  # start credit roll from bottom
        _offset_x = 32
        self.creditroll_x = (self.w // 2) - _offset_x  # start credit roll from bottom

        self.previous_credit = -1
        self.current_credit = 0
        self.can_switch_to_next_credit = False

        self.credit_item_offset_y = 20  # temp
        self.prev_daw_timer = 970

        # (endtime, content)
        # using non-floats value for index to emulate DAWs
        self.credits = [
            (1000, "TIP", pg.Color("maroon")),  # 50
            (1019, "TOE", pg.Color("maroon")),  # 69
            (1050, "2024", pg.Color("white")),  # 100
            (1080, "DESIGN * CODE * ETC * BY LLOYD LOBO", pg.Color("cyan")),  # 130
            (1110, "MUSIC * SOUNDS * SFX * BY LLOYD LOBO", pg.Color("cyan")),  # 160
            (1140, "GAME LIBRARY * BY PYGAME", pg.Color("cyan")),  # 190
        ]

        self.MAX_CREDITS_COUNT = len(self.credits)

        self.daw_timer = self.credits[0][0]
        #
        # Observed logs when 4 credits with time intervals ( 1000, 1060, 1120, 1200,  ) -> 60, 80
        #
        self.daw_timer_markers_offset = self.daw_timer - self.prev_daw_timer  # e.g. (1060 - 1000).
        assert self.daw_timer_markers_offset > 0

    def run(self) -> None:
        self.bgcolor = pre.COLOR.BACKGROUND

        loop_counter = 0
        MAX_LOOP_COUNTER = pre.FPS_CAP * 60  # 60 seconds

        # play background music
        if 0:
            pg.mixer.music.load(pre.SRC_DATA_PATH / "music" / "intro_loop.wav")
            pg.mixer.music.set_volume(0.3)
            pg.mixer.music.play(loops=-1)

        while self.running:
            loop_counter += 1

            if loop_counter >= MAX_LOOP_COUNTER:
                self.running = False
                break

            self.clock.tick(pre.FPS_CAP // 2)  # play at half-speed

            self.events()
            self.update()
            self.render()

    def events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()

            if event.type == pg.QUIT:
                self.running = False
                quit_exit()

    def update(self):
        # clear screen and render background
        self.game.display.fill(self.bgcolor)

        self.fps = self.clock.get_fps()

        if self.previous_credit == self.current_credit:
            self.prev_daw_timer = self.daw_timer

        self.creditroll_y -= 1
        self.daw_timer += 1

        if self.current_credit == (self.MAX_CREDITS_COUNT - 1):
            last_item_has_reached_top = self.creditroll_y + (self.current_credit * self.credit_item_offset_y) <= (-(self.h // 4) + self.credit_item_offset_y)
            if last_item_has_reached_top:  # NOTE: should use modulus?
                self.running = False

        cur_time_marker = 0
        next_time_marker = 10

        if self.current_credit < (self.MAX_CREDITS_COUNT - 1):
            cur_time_marker = self.credits[self.current_credit][0]
            next_time_marker = self.credits[self.current_credit + 1][0]

            assert next_time_marker > cur_time_marker

            if self.daw_timer > cur_time_marker:
                self.daw_timer_markers_offset = next_time_marker - cur_time_marker
        if 0:
            if self.creditroll_y <= self.h // 2:
                if self.current_credit < (self.MAX_CREDITS_COUNT - 1):
                    self.current_credit += 1
        elif 1 and self.current_credit > 0:

            if self.current_credit < (self.MAX_CREDITS_COUNT - 1):
                if cur_time_marker < self.daw_timer <= next_time_marker:

                    if self.daw_timer >= cur_time_marker:

                        if self.current_credit < (self.MAX_CREDITS_COUNT - 1):

                            if self.previous_credit != self.current_credit:
                                self.previous_credit = self.current_credit
                                self.current_credit += 1
                                # print(f" self.can_switch_to_next_credit = True ")
                                self.can_switch_to_next_credit = True
                else:
                    self.can_switch_to_next_credit = False
        else:  # simplest version
            if self.current_credit < (self.MAX_CREDITS_COUNT - 1):

                if self.current_credit < (self.MAX_CREDITS_COUNT - 1):
                    self.previous_credit = self.current_credit
                    self.current_credit += 1
                    self.can_switch_to_next_credit = True

    def render(self):
        pos_y = self.creditroll_y
        offset_y = self.credit_item_offset_y  # default offset_y
        for i, credit in enumerate(self.credits):
            text: str = credit[1]
            if i <= self.current_credit:
                if i != 0:
                    offset_y = self.credits[i][0] - self.credits[i - 1][0]
                self.game.draw_text(
                    x=(self.w // 2),
                    #
                    # either change offset_y or add to it or lerp it also consider creditroll_y
                    #
                    # y=pos_y + (i * (offset_y * 1 + self.daw_timer_markers_offset)),
                    # y=pos_y + (i * (self.daw_timer_markers_offset)),
                    y=pos_y + (i * offset_y),
                    font=self.start_font,
                    # color=(pg.Color("maroon") if (i == self.current_credit) else self.credits[i][2]),
                    color=(self.credits[i][2]),
                    text=text,
                    #
                    # DEBUG:
                    #
                    # text=f"{text} {round(self.daw_timer)} {credit[0]} {self.daw_timer_markers_offset} {round(self.creditroll_y)}",
                )

        # draw mask outline for all
        # ---------------------------------------------------------------------
        dispmask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))

        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)
        # ---------------------------------------------------------------------

        # render display
        # ---------------------------------------------------------------------
        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))

        pg.display.flip()
        # ---------------------------------------------------------------------


class StartScreen:
    """Main Menu Screen."""

    # @profile
    def __init__(self, game: "Game") -> None:
        self.game = game

        self.w, self.h = pre.DIMENSIONS_HALF

        self.bgcolor = pre.CHARCOAL
        self.title_str = "Menu"
        self.instruction_str = f"return* to enter game or q*uit to exit"
        self.start_font = self.game.font_sm
        self.title_font = self.game.font

        self.clock = pg.time.Clock()  # or use game's clock?
        self.running = True

        self._title_textz_offy = 4 * pre.TILE_SIZE

        self.todo_menu_item_offset = 0

        self.todo_selected_menu_item = MenuItemType.PLAY  # current item
        self.event_selected_menu_item: Optional[MenuItemType] = None  # current item

    # @profile
    def run(self) -> None:
        # play background music
        pg.mixer.music.load(pre.SRC_DATA_PATH / "music" / "intro_loop.wav")
        pg.mixer.music.set_volume(0.3)
        pg.mixer.music.play(loops=-1)

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        while self.running:
            self.clock.tick(pre.FPS_CAP)

            self.events()
            self.update()
            self.render()

    def events(self):
        # RESET
        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()

            if event.type == pg.QUIT:
                self.running = False
                quit_exit()

            # to replace with menu item navigation ( 20240613050437UTC )
            if event.type == pg.KEYDOWN and event.key == pg.K_RETURN:
                pg.mixer.music.fadeout(1000)

                match self.todo_selected_menu_item:
                    case MenuItemType.PLAY:
                        self.game.set_mainscreen(LoadingScreen(game=self.game, level=self.game.level))

                    case MenuItemType.OPTIONS:
                        pass  # TODO:

                    case MenuItemType.CREDITS:
                        self.game.set_mainscreen(CreditsScreen(game=self.game, level=self.game.level))
                        pass  # TODO: [ DOING ] 20240613104012UTC

                    case MenuItemType.EXIT:
                        self.running = False
                        quit_exit()

                    case _:  # pyright: ignore [reportUnnecessaryComparison]
                        quit_exit("invalid MenuItemType selected to StartScreen events procedure")

            if event.type == pg.KEYDOWN:
                if event.key in (pg.K_UP, pg.K_w):
                    self.movement.top = True
                elif event.key in (pg.K_DOWN, pg.K_s):
                    self.movement.bottom = True
            elif event.type == pg.KEYUP:
                if event.key in (pg.K_UP, pg.K_w):
                    self.movement.top = False
                elif event.key in (pg.K_DOWN, pg.K_s):
                    self.movement.bottom = False

    def update(self):
        # clear screen and render background
        self.game.display.fill(self.bgcolor)

        # update movement parameters
        # ---------------------------------------------------------------------
        if self.movement.top:
            self.todo_menu_item_offset -= 1
        elif self.movement.bottom:
            self.todo_menu_item_offset += 1
        # ---------------------------------------------------------------------

        # wrap around negative index for MenuItemType Enumerations
        # ---------------------------------------------------------------------
        if self.todo_menu_item_offset < 0:
            self.todo_menu_item_offset = MAX_MENU_ITEMS - 1  # set to last item

        if self.todo_menu_item_offset >= MAX_MENU_ITEMS:
            self.todo_menu_item_offset = 0  # set to first item

        assert (self.todo_menu_item_offset in range(0, MAX_MENU_ITEMS)) and f"expected valid offset for menu items while navigating in StartScreen"

        self.todo_selected_menu_item = MenuItemType(self.todo_menu_item_offset)
        # ---------------------------------------------------------------------

        # DEBUG: update menu item behavior
        # ---------------------------------------------------------------------
        match self.todo_selected_menu_item:
            case MenuItemType.PLAY:
                self.game.draw_text(100, 100, self.start_font, pg.Color("purple"), f"{self.todo_selected_menu_item}")
                pass

            case MenuItemType.OPTIONS:
                self.game.draw_text(100, 100, self.start_font, pg.Color("purple"), f"{self.todo_selected_menu_item}")
                pass

            case MenuItemType.CREDITS:
                self.game.draw_text(100, 100, self.start_font, pg.Color("purple"), f"{self.todo_selected_menu_item}")
                pass

            case MenuItemType.EXIT:
                self.game.draw_text(100, 100, self.start_font, pg.Color("purple"), f"{self.todo_selected_menu_item}")
                pass

            case _:  # pyright: ignore [reportUnnecessaryComparison]
                quit_exit("invalid MenuItemType passed to StartScreen update procedure")
        # ---------------------------------------------------------------------

    def render(self):
        # DEBUG: events
        # ---------------------------------------------------------------------
        if 0:
            self.game.draw_text(100, 100, self.start_font, pg.Color("purple"), f"{self.movement}")
        # ---------------------------------------------------------------------

        # draw game logo
        # ---------------------------------------------------------------------
        shake_x = (0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0.0
        shake_y = (0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0.0

        self.game.draw_text((self.w // 2) + shake_x, 50 - shake_y, self.title_font, pg.Color("maroon"), "TIP")
        self.game.draw_text((self.w // 2) - shake_x, 69 + shake_y, self.title_font, pre.WHITE, "TOE")
        # ---------------------------------------------------------------------

        # draw menu items instructions
        # ---------------------------------------------------------------------
        offset_y = 24

        pos_x = self.w // 2
        pos_y = (self.h // 2) - (offset_y * 0.618)

        for i, val in enumerate(MENU_ITEMS):
            if i == self.todo_selected_menu_item:
                assert (i == self.todo_menu_item_offset) and f"expected exact selected menu item type while rendering in StartScreen. got {i, val, self.todo_selected_menu_item =}"
                self.game.draw_text((pos_x - shake_x), (pos_y - shake_y), self.start_font, pg.Color("maroon"), val)
            else:
                self.game.draw_text(pos_x, pos_y, self.start_font, pre.WHITE, f"{val}")

            pos_y += offset_y
        # ---------------------------------------------------------------------

        # draw instructions
        # ---------------------------------------------------------------------
        # if 0
        if 0:
            self.game.draw_text((self.w // 2), (self.h - 100), self.start_font, pre.WHITE, "Press enter to start")
        # endif
        # ---------------------------------------------------------------------

        # draw mask outline for all
        # ---------------------------------------------------------------------
        dispmask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))

        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)
        # ---------------------------------------------------------------------

        # render display
        # ---------------------------------------------------------------------
        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))

        pg.display.flip()
        # ---------------------------------------------------------------------
