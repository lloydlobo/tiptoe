from __future__ import annotations

import itertools as it
import math
import queue
import sys
import threading
import time
import tracemalloc
from collections import deque
from copy import deepcopy
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


class FontType(IntEnum):
    XS = auto(0)
    SM = auto()
    BASE = auto()


# NOTE(lloyd): Use In StartScreen
class MenuItemType(IntEnum):
    PLAY = auto(0)
    SETTINGS = auto()
    CREDITS = auto()
    EXIT = auto()


# PERF: Can just use an array initialized
MENU_ITEMS: List[str] = [
    "PLAY",
    "SETTINGS",
    "CREDITS",
    "EXIT",
]

MAX_MENU_ITEMS = len(MENU_ITEMS)  # MenuItemType enumerations


# NOTE(lloyd): Use in SettingsScreen
class SettingsNavitemType(IntEnum):
    MUTE_MUSIC = auto(0)
    MUTE_SOUND = auto()
    DISABLE_SCREENSHAKE = auto()
    GO_BACK = auto()


# PERF: Can just use an array initialized
SETTINGS_NAVITEMS: List[str] = [
    "MUSIC",  # + " OFF" or + " ON"
    "SOUND",  # + " OFF" or + " ON"
    "SCREENSHAKE",  # + " OFF" or + " ON"
    "GO BACK",  # + " OFF" or + " ON"
]

MAX_SETTINGS_NAVITEMS = len(SETTINGS_NAVITEMS)


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

        self.config_handler: Final[pre.UserConfig] = get_user_config(pre.CONFIG_PATH)
        self.settings_handler: pre.UserConfig = deepcopy(self.config_handler)
        # self.settings_handler.screenshake = False

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
        self.level = 0  # 20240623122916UTC: level 3 has a lovely color palette
        self.levels_space_theme = {0, 1, 2, 3, 4, 5, 6}  # ^_^ so all levels??!!!
        ################################################################################################

        # seedling: Mon May 13 08:20:31 PM IST 2024
        self.player_dash_enemy_collision_count = 0  # possible to farm this by dying repeatedly but that's alright for now

        self.running = False

    # @profile
    def reset_state_on_gameover(self) -> None:
        if pre.DEBUG_GAME_PRINTLOG:
            print(f"resetting after gameover...")

        self.camera.reset()

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        if self.level in self.levels_space_theme:
            self.player = Player(self, self._player_starting_pos.copy(), pg.Vector2(pre.SIZE.PLAYER))
            self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)

        self.screenshake = 0

        self.gcs_deque.clear()

        self.level = 0

        self.player_dash_enemy_collision_count = 0

        if pre.DEBUG_GAME_PRINTLOG:
            print("[INFO]: resetting completed")

    # @profile
    def run(self) -> None:
        """This game loop runs continuously until the player opts out via inputs.

        Each iteration, computes user input non-blocking events, updates state
        of the game, and renders the game.
        """

        game_level_music_fname = "intro_loop.wav"  # fmt: skip
        game_level_bg_color = pre.hex_to_rgb("121607")

        def recolor_tiles(color: pre.ColorValue, border_color: pre.ColorValue):
            for i, tile in enumerate(self.assets.tiles["granite"].copy()):
                self.assets.tiles["granite"][i].fill(border_color)

                rect_16_0 = tile.get_rect()
                rect_15_9 = pg.Rect(0.1, 0.1, rect_16_0.w - 0.1, rect_16_0.h - 0.1)

                self.assets.tiles["granite"][i].fill(color=color, rect=rect_15_9)

        recolor_tiles(color=pre.hex_to_rgb("597119" or "425238"), border_color=pre.hex_to_rgb("384510" or "18260f" or "4c5c1d"))

        match self.level:
            case 0:
                game_level_music_fname = "level_0.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(color=pre.hex_to_rgb("425238"), border_color=pre.hex_to_rgb("597119"))

            case 1:
                game_level_music_fname = "theme_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(color=pre.hex_to_rgb("425238"), border_color=pre.hex_to_rgb("597119"))

            case 2:
                game_level_music_fname = "level_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(color=pre.hex_to_rgb("425238"), border_color=pre.hex_to_rgb("597119"))

            case 3:
                game_level_music_fname = "level_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(color=pre.hex_to_rgb("425238"), border_color=pre.hex_to_rgb("384510"))

            case 4:
                game_level_music_fname = "level_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(color=pre.hex_to_rgb("597119"), border_color=pre.hex_to_rgb("384510"))

            case 5:
                game_level_music_fname = "level_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(color=pre.hex_to_rgb("597119"), border_color=pre.hex_to_rgb("384510"))

            case _:
                # NOTE(lloyd): Use a prev variable to hold last level music played
                # if we want to let it followthrough and avoid playing via pg.mixer.play()
                assert (game_level_music_fname == "intro_loop.wav") and "expected default level music filename"

        pg.mixer.music.load((pre.SRC_DATA_PATH / "music" / game_level_music_fname).__str__())

        #
        # Set individual music volume
        #
        # NOTE(lloyd): SettingsScreen is setting volume to 0 @ location of "MUTE_MUSIC" case in update().
        # We are not setting it here to avoid hassle of dynamic update via SettingsScreen in mid-gameplay,
        # maybe there is a better way??
        #
        # NOTE(lloyd): Also is mute different from music-disabled? (In that case, avoid playing music???)
        #
        # NOTE(lloyd): We could just pre-render audio files with similar LUFS using ay simple VU meter in a DAW.
        #
        if not self.settings_handler.music_muted:
            pg.mixer.music.set_volume(0.2)

        pg.mixer.music.play(-1)

        if 0:
            if self.level == 0:
                self.sfx.playerspawn.play()
        self.sfx.playerspawn.play()

        self.running = True  # NOTE(lloyd): at init running is False. ensure load and reset keep it as false
        # gc.freeze()

        while self.running:
            self.dt = self.clock.tick(pre.FPS_CAP) * 0.001

            self.display.fill((0, 0, 0, 0))

            if self.level in self.levels_space_theme:
                if 0:
                    self.display_2.fill((30, 30, 30))
                else:
                    self.display_2.fill(game_level_bg_color)  # BIY theme

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

            if event.type == pg.VIDEORESIZE:
                self.screen = pg.display.get_surface()

            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                # Avoid glitchy stuck movement after resuming
                self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)
                # Bring up main menu without reseting the game
                self.set_mainscreen(StartScreen(game=self))

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

        # MAYBE: - Assign precedence to this
        #        - Or, preset settings_handler members from config_handler
        #          at load player config file
        #
        # and (self.config_handler.screenshake or self.settings_handler.screenshake)
        #
        # TODO(lloyd): Enable toggling from Gameplay to Menu screen with Esc.
        #           - Rename setting items to present the state. e.g. `SCREENSHAKE: OFF`
        dest = (
            ((shake * random()) - halfshake, (shake * random()) - halfshake)
            if (
                shake := self.screenshake,
                halfshake := shake * 0.5,
            )
            and self.settings_handler.screenshake
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
        if not self.dead and (position_ := self.player_spawner_pos) and position_:
            success_width, success_height = 48, 6
            surf_color = pre.hex_to_rgb("ece187" or "13c299")

            rect_value = (
                position_.x - success_width / 2 - render_scroll[0],
                (position_.y - render_scroll[1]) + 16 - success_height,
                success_width,
                success_height,
            )

            surf = self.assets.tiles["portal"][1].copy()  # NOTE(Lloyd): Copying sanity check
            anim_offset_y = 3
            surf_w = surf.get_width()
            surf_h = surf.get_height()

            dest_position = (
                (position_.x - (surf.get_width() / 2) - render_scroll[0]),
                (position_.y - (surf.get_height() / 2) + anim_offset_y - render_scroll[1]),
            )

            # This is on victory.. sparks around flags to signify SUCESS state.
            # And signal player to go to flag_end
            # ---------------------------------------------------------------------
            enemy_count = len(self.enemies)

            for enemy in self.enemies:
                if abs(enemy.pos.y - self.player_spawner_pos.y) < 32:
                    enemy_count -= 1

                    if enemy not in self.collected_enemies_seen:
                        self.collected_enemies_counter += 1
                        self.collected_enemies_seen.add(enemy)

            # TODO: Use flag_start asset portal
            if enemy_count == 0:
                self.collected_enemies = True

                radius = 1
                colors = (pre.hex_to_rgb("cac063"), pre.hex_to_rgb("acc167"))
                offset_y_ = pre.TILE_SIZE / 8
                center = [(dest_position[0] + surf_w // 2), (dest_position[1] + surf_h)]
                dy = 0.0

                for i in range(0, (surf_h * 2)):
                    if dy > (surf_h // 1.618):
                        break

                    if random() < 0.8:
                        for j in range(0, surf_w // 4):
                            pg.draw.circle(self.display, colors[0], (center[0] + (4 * j), center[1] - dy), radius)
                            pg.draw.circle(self.display, colors[0], (center[0] - (4 * j), center[1] - dy), radius)
                    else:
                        for j in range(0, surf_w // 4):
                            pg.draw.circle(self.display, colors[1], (center[0] + (4 * j), center[1] - dy), radius)
                            pg.draw.circle(self.display, colors[1], (center[0] - (4 * j), center[1] - dy), radius)

                    dy += offset_y_
            # ---------------------------------------------------------------------

            # Update and Draw start drop location
            # ---------------------------------------------------------------------
            # NOTE(Lloyd): success_width/height are for a rectangular slab for prototyping.
            # Might want to get correct dimension based of the asset
            self.display.blit(surf, dest_position)
            # ---------------------------------------------------------------------

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
                        self.sparks.extend(Spark(pg.Vector2(self.player.rect.center), angle, speed, pg.Color("cyan")) for _ in range(30) if (angle := random() * math.pi * 2, speed := 2 + random()))
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
    def set_mainscreen(self, scr: Optional["StartScreen | LoadingScreen | SettingsScreen | CreditsScreen | Game"]):
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

        if 0:
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
        # TODO: if time permits work on animating start and end times declaratively
        # `worse is better`
        self.credits_marque = [
            (0, 3000, "TIP TOE"),
            (3000, 6000, "CREATED BY LLOYD LOBO"),
        ]

        self.MAX_CREDITS_COUNT = len(self.credits)
        self.daw_timer = self.credits[0][0]
        self.daw_timer_markers_offset = self.daw_timer - self.prev_daw_timer

        assert self.daw_timer_markers_offset > 0

    def run(self) -> None:
        self.bgcolor = pre.COLOR.BACKGROUND

        loop_counter = 0  # GAME_SLOW=0 :: safety feature
        MAX_LOOP_COUNTER = pre.FPS_CAP * 60  # 60 seconds

        while self.running:
            if loop_counter >= MAX_LOOP_COUNTER:
                self.running = False
                break

            self.clock.tick(pre.FPS_CAP // 2)  # play at half-speed

            self.events()
            self.update()
            self.render()

            loop_counter += 1

    def events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()

            if event.type == pg.QUIT:
                self.running = False
                quit_exit()

    def update(self):
        self.game.display.fill(self.bgcolor)  # Clear screen and render background

        if self.current_credit == (self.MAX_CREDITS_COUNT - 1):
            last_position = self.creditroll_y + (self.current_credit * self.credit_item_offset_y)
            last_item_is_above_fold = last_position <= ((-1 * (self.h // 4)) + self.credit_item_offset_y)

            if last_item_is_above_fold:
                self.running = False  # Exit current screen

        self.fps = self.clock.get_fps()

        if self.previous_credit == self.current_credit:
            self.prev_daw_timer = self.daw_timer

        self.creditroll_y -= 1
        self.daw_timer += 1

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
        """
        # either change offset_y or add to it or lerp it also consider creditroll_y
        # y=pos_y + (i * (offset_y * 1 + self.daw_timer_markers_offset)),

        # DEBUG:
        # text=f"{text} {round(self.daw_timer)} {credit[0]} {self.daw_timer_markers_offset} {round(self.creditroll_y)}",
        """

        # draw credits vertical marque
        # ---------------------------------------------------------------------
        offset_y = self.credit_item_offset_y

        pos_y = self.creditroll_y

        for i, credit in enumerate(self.credits):
            if i > self.current_credit:
                continue

            if i > 0:
                offset_y = self.credits[i][0] - self.credits[i - 1][0]

            self.game.draw_text(
                x=(self.w // 2),
                y=(pos_y + (i * offset_y)),
                font=self.start_font,
                color=(self.credits[i][2]),
                text=credit[1],
            )
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


class SettingsScreen:
    """Implements SettingsScreen that provide game settings.
    It is accessed via StartScreen main menu.
    """

    def __init__(self, game: Game, level: int) -> None:
        # NOTE(lloyd): using this as Game.set_screen(screen: 'CreditsScreen |
        # Game | ...') requires each args passed to __init__ to have game and
        # level. doing this via manual inheritance. sigh OOP -_-
        self.game = game
        self.level = level

        self.w, self.h = pre.DIMENSIONS_HALF

        self.clock = pg.time.Clock()  # or use game's clock?
        self.running = True

        # TODO: Add required members here
        # ---------------------------------------------------------------------
        # ...

        self.FONT_TYPES = [self.game.font_xs, self.game.font_sm, self.game.font]

        position_x, position_y = self.w // 2, self.h // 2
        offset_x, offset_y = 0, 16

        self.settings = [
            ((position_x + offset_x), (position_y + (0 * offset_y)), FontType.SM, pg.Color("white"), SETTINGS_NAVITEMS[0]),
            ((position_x + offset_x), (position_y + (1 * offset_y)), FontType.SM, pg.Color("white"), SETTINGS_NAVITEMS[1]),
            ((position_x + offset_x), (position_y + (2 * offset_y)), FontType.SM, pg.Color("white"), SETTINGS_NAVITEMS[2]),
            # NOTE(lloyd): This must always be at the end.
            # Please adjust index accordingly.
            ((position_x), (position_y + (3 * offset_y)), FontType.SM, pg.Color("white"), SETTINGS_NAVITEMS[3]),
        ]
        assert ((want := MAX_SETTINGS_NAVITEMS, got := len(self.settings)) and (want == got)) and f"want settings array length to be {repr(want)}. got {repr(got)}"
        assert ((want := "GO BACK", got := self.settings[-1][4]) and (want == got)) and f"want the last SettingsScreen navitem to have text {repr(want)}. got {repr(got)}"

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)
        self.is_key_pressed_key_enter = False

        self.navitem_offset = 0
        self.selected_navitem = SettingsNavitemType.MUTE_MUSIC
        assert (want := 0, got := self.selected_navitem) and (got == want) and f"want selected_navitem to be initialized with the zero value enumeration. got {repr(got)}"
        # ...
        # ---------------------------------------------------------------------

    def run(self) -> None:
        self.bgcolor = pre.COLOR.BACKGROUND

        loop_counter = 0  # GAME_SLOW=0 :: safety feature
        MAX_LOOP_COUNTER = pre.FPS_CAP * 60  # 60 seconds

        while self.running:
            if loop_counter >= MAX_LOOP_COUNTER:
                self.running = False
                break

            self.clock.tick(pre.FPS_CAP // 2)  # play at half-speed

            self.events()  # Process events this frame
            self.update()  # Update data this frame
            self.render()  # Draw updated data this frame

            loop_counter += 1

    def events(self):
        # Resets
        # ------
        # NOTE(lloyd): this resets self.movement each frame to avoid navigating on key down at 60fps 0_0
        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)
        self.is_key_pressed_key_enter = False
        # ------

        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()

            if event.type == pg.QUIT:
                self.running = False
                quit_exit()

            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.running = False
                # NOTE: See if we need to de-init or unload assets/flags/variables etc

            if event.type == pg.KEYDOWN:
                if event.key in (pg.K_UP, pg.K_w):
                    self.movement.top = True
                elif event.key in (pg.K_DOWN, pg.K_s):
                    self.movement.bottom = True
                elif event.key in (pg.K_LEFT, pg.K_a):
                    self.movement.left = True
                elif event.key in (pg.K_RIGHT, pg.K_d):
                    self.movement.right = True

            elif event.type == pg.KEYUP:
                if event.key in (pg.K_UP, pg.K_w):
                    self.movement.top = False
                elif event.key in (pg.K_DOWN, pg.K_s):
                    self.movement.bottom = False
                elif event.key in (pg.K_LEFT, pg.K_a):
                    self.movement.left = False
                elif event.key in (pg.K_RIGHT, pg.K_d):
                    self.movement.right = False

            if event.type == pg.KEYDOWN and event.key == pg.K_RETURN:
                self.is_key_pressed_key_enter = True
            elif event.type == pg.KEYUP and event.key == pg.K_RETURN:
                self.is_key_pressed_key_enter = False

            # TODO: if esc go back to menu

    # TODO: use left/right for incr/decr music/sound levels
    def update(self):
        # Clear screen and render background
        # ---------------------------------------------------------------------
        self.game.display.fill(self.bgcolor)
        # ---------------------------------------------------------------------

        # TODO: update Settings content here
        # ---------------------------------------------------------------------

        # update movement parameters
        # ---------------------------------------------------------------------
        if self.movement.top:
            self.navitem_offset -= 1
        elif self.movement.bottom:
            self.navitem_offset += 1
        # ---------------------------------------------------------------------

        # wrap around negative index for MenuItemType Enumerations
        # ---------------------------------------------------------------------
        if self.navitem_offset < 0:
            self.navitem_offset = MAX_MENU_ITEMS - 1  # set to last item

        if self.navitem_offset >= MAX_MENU_ITEMS:
            self.navitem_offset = 0  # set to first item

        assert (self.navitem_offset in range(0, MAX_SETTINGS_NAVITEMS)) and f"expected valid offset for menu items while navigating in StartScreen"
        self.selected_navitem = SettingsNavitemType(self.navitem_offset)
        # ---------------------------------------------------------------------

        if self.is_key_pressed_key_enter:
            match self.selected_navitem:
                case SettingsNavitemType.MUTE_MUSIC:  # TODO:
                    print(f"{self.selected_navitem = }")
                    self.game.settings_handler.music_muted = not self.game.settings_handler.music_muted

                    if self.game.settings_handler.music_muted:
                        pg.mixer.music.set_volume(0.0)
                    else:
                        pg.mixer.music.set_volume(0.4)

                case SettingsNavitemType.MUTE_SOUND:  # TODO:
                    print(f"{self.selected_navitem = }")
                    self.game.settings_handler.sound_muted = not self.game.settings_handler.sound_muted

                    if self.game.settings_handler.sound_muted:
                        self.game.sfx.ambienceheartbeatloop.set_volume(0)
                        self.game.sfx.dash.set_volume(0)
                        self.game.sfx.dashbassy.set_volume(0)
                        self.game.sfx.hit.set_volume(0)
                        self.game.sfx.hitmisc.set_volume(0)
                        self.game.sfx.hitwall.set_volume(0)
                        self.game.sfx.jump.set_volume(0)
                        self.game.sfx.jumplanding.set_volume(0)
                        self.game.sfx.playerspawn.set_volume(0)
                        self.game.sfx.portaltouch.set_volume(0)
                        self.game.sfx.shoot.set_volume(0)
                        self.game.sfx.shootmiss.set_volume(0)
                        self.game.sfx.teleport.set_volume(0)
                    else:
                        self.game.sfx.ambienceheartbeatloop.set_volume(0.1)
                        self.game.sfx.dash.set_volume(0.2)
                        self.game.sfx.dashbassy.set_volume(0.2)
                        self.game.sfx.hit.set_volume(0.2)
                        self.game.sfx.hitmisc.set_volume(0.2)
                        self.game.sfx.hitwall.set_volume(0.2)
                        self.game.sfx.jump.set_volume(0.4)
                        self.game.sfx.jumplanding.set_volume(0.3)
                        self.game.sfx.playerspawn.set_volume(0.2)
                        self.game.sfx.portaltouch.set_volume(0.2)
                        self.game.sfx.shoot.set_volume(0.1)
                        self.game.sfx.shootmiss.set_volume(0.2)
                        self.game.sfx.teleport.set_volume(0.2)

                case SettingsNavitemType.DISABLE_SCREENSHAKE:  # TODO:
                    print(f"{self.selected_navitem = }")

                    self.game.settings_handler.screenshake = not self.game.settings_handler.screenshake

                case SettingsNavitemType.GO_BACK:
                    self.running = False  # Exit SettingsScreen and return to caller i.e. StartScreen

                case _:  # pyright: ignore [reportUnnecessaryComparison]
                    """# If using left and right. for sound music level fine controls
                    match (self.movement.left, self.movement.right, self.movement.top, self.movement.bottom):
                        case (True, _, _, _):
                            pass
                        case (_, True, _, _):
                            pass
                        case (_, _, True, _):
                            pass
                        case (_, _, _, True):
                            pass
                        case _:  # pyright: ignore [reportUnnecessaryComparison]
                            pass
                    """
                    pass
        # ...
        # ---------------------------------------------------------------------

    def render(self):
        # TODO: render Settings content here
        # ---------------------------------------------------------------------
        # ...

        # Text VFX
        shake_x = (0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0.0
        shake_y = (0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0.0

        # Draw screen name
        # ---------------------------------------------------------------------
        text_xpos: int = int((self.w // 2) + shake_x)
        text_ypos: int = int(69 - shake_y)

        self.game.draw_text(text_xpos, text_ypos, self.FONT_TYPES[FontType.BASE], pg.Color("maroon"), text="SETTINGS")
        # ---------------------------------------------------------------------

        # Draw navigation items
        # ---------------------------------------------------------------------
        shake_x = math.floor(shake_x)
        shake_y = math.floor(shake_y)

        for i, option in enumerate(self.settings):
            assert (0 <= self.navitem_offset < MAX_SETTINGS_NAVITEMS) and f"want valid navitem offset ranging from {repr(0)}..={repr(MAX_SETTINGS_NAVITEMS-1)}. got {repr( self.navitem_offset )}"

            is_active = (self.navitem_offset == i)  # fmt: skip

            pos_x = (option[0] - shake_x) if is_active else option[0]
            pos_y = (option[1] - shake_y) if is_active else option[1]
            color = pg.Color("maroon")    if is_active else option[3]  # fmt: skip

            text: str
            match SettingsNavitemType(i):
                # fmt: off
                case SettingsNavitemType.MUTE_MUSIC:          text = (option[4] + " OFF") if self.game.settings_handler.music_muted       else (option[4] + " ON")
                case SettingsNavitemType.MUTE_SOUND:          text = (option[4] + " OFF") if self.game.settings_handler.sound_muted       else (option[4] + " ON")
                case SettingsNavitemType.DISABLE_SCREENSHAKE: text = (option[4] + " OFF") if not self.game.settings_handler.screenshake   else (option[4] + " ON")
                case SettingsNavitemType.GO_BACK:             text = (option[4])
                # fmt: on
                case _:  # pyright: ignore [reportUnnecessaryComparison]
                    msg = f"want valid SettingsNavitemType while drawing text in SettingsScreen. got {repr(SettingsNavitemType(i))} while iterating over item at index {repr(i)}."
                    raise ValueError(msg)

            self.game.draw_text(pos_x, pos_y, self.FONT_TYPES[option[2]], color, text)
        # ---------------------------------------------------------------------

        # ...
        # ---------------------------------------------------------------------

        # DEBUG: HUD
        # ---------------------------------------------------------------------
        if pre.DEBUG_GAME_HUD:
            dbg_posy = 16
            dbg_posx = 64
            dbg_gapy = 16

            self.game.draw_text(
                dbg_posx,
                dbg_posy,
                self.FONT_TYPES[0],
                pg.Color("cyan"),
                text=f"UP*{1 if self.movement.top else 0} DOWN*{1 if self.movement.bottom else 0}",
            )
            dbg_posy += dbg_gapy

            self.game.draw_text(
                dbg_posx + 10,
                dbg_posy,
                self.FONT_TYPES[0],
                pg.Color("cyan"),
                text=f"LEFT*{1 if self.movement.left else 0} RIGHT*{1 if self.movement.right else 0}",
            )
            dbg_posy += dbg_gapy

            self.game.draw_text(
                dbg_posx + 20,
                dbg_posy,
                self.FONT_TYPES[0],
                pg.Color("maroon"),
                text=f"NAVITEM OFFSET*{self.navitem_offset}",
            )
            dbg_posy += dbg_gapy
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


class StartScreen:
    """Main Menu Screen."""

    # @profile
    def __init__(self, game: "Game") -> None:
        self.game = game
        self.w, self.h = pre.DIMENSIONS_HALF
        self.bgcolor = pre.CHARCOAL
        self.title_str = "Menu"
        self.instruction_str = f"return* to enter game or q*uit to exit"
        self.font_sm = self.game.font_sm
        self.font_base = self.game.font

        self._title_textz_offy = 4 * pre.TILE_SIZE

        self.selected_menuitem = MenuItemType.PLAY  # current item
        self.event_selected_menuitem: Optional[MenuItemType] = None  # current item
        self.menuitem_offset = 0

        self.clock = pg.time.Clock()  # or use game's clock?
        self.running = True

    # @profile
    def run(self) -> None:
        # play background music
        pg.mixer.music.load(pre.SRC_DATA_PATH / "music" / "level_2.wav")
        pg.mixer.music.set_volume(0.3)  # NOTE: Player can toggle this in SettingsScreen
        pg.mixer.music.play(loops=-1)

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        while self.running:
            self.clock.tick(pre.FPS_CAP)

            self.events()
            self.update()
            self.render()

    def events(self):
        # NOTE(lloyd): this resets self.movement each frame to avoid navigating on key down at 60fps 0_0
        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()

            if event.type == pg.QUIT:
                self.running = False
                quit_exit()

            if event.type == pg.KEYDOWN and event.key == pg.K_RETURN:
                match self.selected_menuitem:
                    # FIXME: Ensure that on keydown ESCAPE during gameplay, we end up here and show the player the 'main menu'
                    case MenuItemType.PLAY:
                        pg.mixer.music.fadeout(1000)

                        if self.game.level == 0:
                            print(f"selected menuitem {self.game.level =}")
                        elif self.game.level == 6:
                            print(f"selected menuitem {self.game.level =}")

                        if not self.game.running:
                            self.game.set_mainscreen(LoadingScreen(game=self.game, level=self.game.level))
                        else:
                            self.game.set_mainscreen(self.game)

                    case MenuItemType.SETTINGS:
                        self.game.set_mainscreen(SettingsScreen(game=self.game, level=self.game.level))
                        pass  # TODO: [ DOING ] : 20240614090235UTC

                    case MenuItemType.CREDITS:
                        self.game.set_mainscreen(CreditsScreen(game=self.game, level=self.game.level))

                    case MenuItemType.EXIT:
                        pg.mixer.music.fadeout(1000)
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
            self.menuitem_offset -= 1
        elif self.movement.bottom:
            self.menuitem_offset += 1
        # ---------------------------------------------------------------------

        # wrap around negative index for MenuItemType Enumerations
        # ---------------------------------------------------------------------
        if self.menuitem_offset < 0:
            self.menuitem_offset = MAX_MENU_ITEMS - 1  # set to last item

        if self.menuitem_offset >= MAX_MENU_ITEMS:
            self.menuitem_offset = 0  # set to first item

        assert (self.menuitem_offset in range(0, MAX_MENU_ITEMS)) and f"expected valid offset for menu items while navigating in StartScreen"
        self.selected_menuitem = MenuItemType(self.menuitem_offset)
        # ---------------------------------------------------------------------

        # DEBUG: update menu item behavior
        # ---------------------------------------------------------------------
        if 0:
            # fmt: off
            match self.selected_menuitem:
                case MenuItemType.PLAY:     self.game.draw_text(100, 100, self.font_sm, pg.Color("purple"), f"{self.selected_menuitem}")
                case MenuItemType.SETTINGS: self.game.draw_text(100, 100, self.font_sm, pg.Color("purple"), f"{self.selected_menuitem}")
                case MenuItemType.CREDITS:  self.game.draw_text(100, 100, self.font_sm, pg.Color("purple"), f"{self.selected_menuitem}")
                case MenuItemType.EXIT:     self.game.draw_text(100, 100, self.font_sm, pg.Color("purple"), f"{self.selected_menuitem}")
                case _:                     quit_exit("invalid MenuItemType passed to StartScreen update procedure") # pyright: ignore [reportUnnecessaryComparison]
            # fmt: on
        # ---------------------------------------------------------------------

    def render(self):
        # DEBUG: events
        # ---------------------------------------------------------------------
        if 0:
            self.game.draw_text(100, 100, self.font_sm, pg.Color("purple"), f"{self.movement}")
        # ---------------------------------------------------------------------

        # draw game logo
        # ---------------------------------------------------------------------
        shake_x = math.floor(0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0
        shake_y = math.floor(0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0

        self.game.draw_text((self.w // 2) + shake_x, 50 - shake_y, self.font_base, pg.Color("maroon"), "TIP")
        self.game.draw_text((self.w // 2) - shake_x, 69 + shake_y, self.font_base, pre.WHITE, "TOE")
        # ---------------------------------------------------------------------

        # draw menu items instructions
        # ---------------------------------------------------------------------
        offset_y = 24

        pos_x = self.w // 2
        pos_y = math.floor((self.h // 2) - (offset_y * 0.618))

        for i, val in enumerate(MENU_ITEMS):
            if i == MenuItemType(0):  # PLAY
                assert MENU_ITEMS[i] == "PLAY"

                if self.game.running:
                    val = "RESUME"

            if i == self.selected_menuitem:
                assert (i == self.menuitem_offset) and f"expected exact selected menu item type while rendering in StartScreen. got {i, val, self.selected_menuitem =}"
                self.game.draw_text((pos_x - shake_x), (pos_y - shake_y), self.font_sm, pg.Color("maroon"), val)
            else:
                self.game.draw_text(pos_x, pos_y, self.font_sm, pre.WHITE, f"{val}")

            pos_y += offset_y
        # ---------------------------------------------------------------------

        # draw instructions
        # ---------------------------------------------------------------------
        # if 0
        if 0:
            self.game.draw_text((self.w // 2), (self.h - 100), self.font_sm, pre.WHITE, "Press enter to start")
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
