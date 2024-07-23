# file: game.py


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
from os import listdir
from pathlib import Path
from random import randint, random, uniform
from typing import (
    Counter,
    Final,
    Generator,
    List,
    Literal,
    NoReturn,
    Optional,
    Set,
    Tuple,
)

import pygame as pg


if 0:
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

if pre.DDEBUG:
    __import__('pprint').pprint(
        dict(
            debug_mode=pre.DDEBUG,
        )
    )

# ------------------------------------------------------------------------------
# GLOBAL CONSTANTS (module)
# ------------------------------------------------------------------------------
MENU_ITEMS: List[str] = ["PLAY", "SETTINGS", "CREDITS", "EXIT"]
MAX_MENU_ITEMS = len(MENU_ITEMS)  # MenuItemType enumerations
SETTINGS_NAVITEMS: List[str] = ["MUSIC", "SOUND", "SCREENSHAKE", "GO BACK"]
MAX_SETTINGS_NAVITEMS = len(SETTINGS_NAVITEMS)

# ------------------------------------------------------------------------------
# DATA STRUCTURES, TYPES AND ENUMS
# ------------------------------------------------------------------------------


@dataclass
class GameLevelTimer:
    levelid: Optional[int]
    start: Optional[float]
    end: Optional[float]
    elapsed: Optional[float]
    current: Optional[float]


@dataclass
class GameCheckpointState:
    player_position: tuple[float, float]
    enemy_positions: list[tuple[float, float]]


@dataclass
class Background:
    depth: Final[float]
    pos: pg.Vector2  # topleft
    speed: float


@dataclass(slots=True)
class SFX:
    """Sound Effects"""

    dashbassy: pg.mixer.Sound
    hit: pg.mixer.Sound
    hitmisc: pg.mixer.Sound
    hitwall: pg.mixer.Sound
    jump: pg.mixer.Sound
    jumplanding: pg.mixer.Sound
    playerspawn: pg.mixer.Sound
    portaltouch: pg.mixer.Sound
    shoot: pg.mixer.Sound
    teleport: pg.mixer.Sound

    dash: Optional[pg.mixer.Sound] = None  # @Unused
    shootmiss: Optional[pg.mixer.Sound] = None  # @Unused


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


# Implemented in StartScreen
class MenuItemType(IntEnum):
    PLAY = auto(0)
    SETTINGS = auto()
    CREDITS = auto()
    EXIT = auto()


# Implemented in SettingsScreen
class SettingsNavitemType(IntEnum):
    MUTE_MUSIC = auto(0)
    MUTE_SOUND = auto()
    DISABLE_SCREENSHAKE = auto()
    GO_BACK = auto()


# ------------------------------------------------------------------------------
# MODULE FUNCTION DEFINITIONS
# ------------------------------------------------------------------------------


def quit_exit(context: str = "") -> NoReturn:
    if pre.DEBUG_GAME_CACHEINFO:  # lrucache etc...
        print(f"{pre.hsl_to_rgb.cache_info() = }")
    if pre.DEBUG_GAME_TRACEMALLOC:
        snapshot: tracemalloc.Snapshot = tracemalloc.take_snapshot()
        stat_key_type = ("traceback", "filename", "lineno")
        top_stats: List[tracemalloc.Statistic] = snapshot.statistics(stat_key_type[0])
        print("Top memory allocations:")
        for stat in top_stats[:30]:
            print(stat)
    if not pg.get_init():
        if pre.DDEBUG:
            __import__('logging').error(
                "cannot quit pygame as it is not initialized.  Did you forget to call pygame.init()?",
                (pg, __file__, pre.get_current_line()),
            )
        raise RuntimeError("pygame.error: pygame is not initialized")
    if context:
        print(f"{context}")
    pg.quit()
    sys.exit()


def get_user_config(filepath: Path) -> pre.UserConfig:
    """Returns UserConfig default empty stub instead of panicking"""
    config: Optional[dict[str, str]]
    config = pre.UserConfig.read_user_config(filepath=filepath)
    if not config:
        print("error while reading configuration file at", repr(filepath))
        return pre.UserConfig.from_dict({})
    return pre.UserConfig.from_dict(config)


# @profile # @Disabled
def set_mainscreen(
    game: "Game",
    scr: Optional["StartScreen | LoadingScreen | SettingsScreen | CreditsScreen | Game"],
):
    # Delete existing screen
    if game.mainscreen != None:
        del game.mainscreen
        game.mainscreen = None

    # Show new screen
    game.mainscreen = scr

    if game.mainscreen != None:
        game.mainscreen.run()
    if game.gameover:
        return AppState.MENUSTATE, GameState.EXIT
    elif not game.running:
        # NOTE(Lloyd): Can just set gamestate form key-event/update loop
        return AppState.GAMESTATE, GameState.NEXTLEVEL


# -----------------------------------------------------------------------------
# GAME
# -----------------------------------------------------------------------------


class Game:
    # @profile
    def __init__(self) -> None:
        pg.init()

        self.mainscreen = None  # Choices: StartScreen, Game, LoadingScreen, CreditsScreen, SettingsScreen, None
        # More choices: SCLAED | FULLSCREEN
        #   HWSURFACE flag does nothing in pygameg ver2.0+, DOUBLEBUF has some use, but not a magic speed up flag.
        #   See https://www.pygame.org/docs/tut/newbieguide.html
        display_flag = pg.DOUBLEBUF | pg.RESIZABLE | pg.NOFRAME | pg.HWSURFACE  # BITFLAGS

        self.screen = pg.display.set_mode(pre.DIMENSIONS, display_flag)

        # See github:pygame/examples/resizing_new.py
        pg.display._set_autoresize(False)  # pyright: ignore
        pg.display.set_caption(pre.CAPTION)

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        # Font: The author suggests using font size in multiples of 9
        # ---------------------------------------------------------------------
        self.fontface_path = pre.FONT_PATH / "8bit_wonder" / "8-BIT WONDER.TTF"
        self.font = pg.font.Font(self.fontface_path, 18)
        self.font_sm = pg.font.Font(self.fontface_path, 12)
        self.font_xs = pg.font.Font(self.fontface_path, 9)
        if pre.DEBUG_GAME_HUD:
            self.font_hud = pg.font.SysFont(name=("Julia Mono"), size=7, bold=False)
        # ---------------------------------------------------------------------

        self.clock = pg.time.Clock()
        self.dt: float = 0.0
        if pre.DEBUG_GAME_HUD:
            self.clock_dt_recent_values: deque[pre.Number] = deque([self.dt, self.dt])

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        self.config_handler: Final[pre.UserConfig] = get_user_config(pre.CONFIG_PATH)
        self.settings_handler: pre.UserConfig = deepcopy(self.config_handler)

        self.assets = Assets.initialize_assets()

        _sfx_path = pre.SFX_PATH
        _load_sound = pre.load_sound

        self.sfx = SFX(
            dashbassy=_load_sound(_sfx_path / "dashbassy.wav"),
            hit=_load_sound(_sfx_path / "hit.wav"),
            hitmisc=_load_sound(_sfx_path / "hitmisc.wav"),
            hitwall=_load_sound(_sfx_path / "hitwall.wav"),
            jump=_load_sound(_sfx_path / "jump.wav"),
            jumplanding=_load_sound(_sfx_path / "jumplanding.wav"),
            playerspawn=_load_sound(_sfx_path / "playerspawn.wav"),
            portaltouch=_load_sound(_sfx_path / "portaltouch.wav"),
            shoot=_load_sound(_sfx_path / "shoot.wav"),
            teleport=_load_sound(_sfx_path / "teleport.wav"),
            dash=None,  # _load_sound(_sfx_path / "dash.wav"),
            shootmiss=None,  # _load_sound(_sfx_path / "shootmiss.wav"),
        )

        self.sfx.dashbassy.set_volume(0.2)
        self.sfx.hit.set_volume(0.2)
        self.sfx.hitmisc.set_volume(0.2)  # Player looses health but still alive if idle or still
        self.sfx.hitwall.set_volume(0.2)
        self.sfx.jump.set_volume(0.4)
        self.sfx.jumplanding.set_volume(0.3)
        self.sfx.playerspawn.set_volume(0.2)
        self.sfx.portaltouch.set_volume(0.2)
        self.sfx.shoot.set_volume(0.1)
        self.sfx.teleport.set_volume(0.2)
        if self.sfx.dash:
            self.sfx.dash.set_volume(0.2)
        if self.sfx.shootmiss:
            self.sfx.shootmiss.set_volume(0.2)

        self._player_starting_pos: Final = pg.Vector2(50, 50)
        self.player = Player(
            self,  # pyright: ignore [reportArgumentType]
            self._player_starting_pos.copy(),
            pg.Vector2(pre.SIZE.PLAYER),
        )
        self.player_spawner_pos: Optional[pg.Vector2] = None

        self.gcs_deque: deque[GameCheckpointState] = deque([])

        self._star_count: Final[int] = min(64, max(16, int(self.config_handler.star_count) or pre.TILE_SIZE * 2))
        self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)

        self.tilemap = Tilemap(
            self,  # pyright: ignore [reportArgumentType]
            pre.TILE_SIZE,
        )

        self.screenshake = 0
        self.gameover = False
        self.gamecompleted = False
        self.gameleveltimer = GameLevelTimer(None, None, None, None, None)

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        # B.I.Y. Inspired Color Scheme
        self.colorscheme_green3 = pre.hex_to_rgb("425238")
        self.colorscheme_green4 = pre.hex_to_rgb("597119")
        self.colorscheme_green5 = pre.hex_to_rgb("6a822a")

        self.scroll_ease: Final[pg.Vector2] = pg.Vector2(1 / 30, 1 / 30)
        self.camerasize = self.display.get_size()
        self.camera = SimpleCamera(size=self.camerasize)

        # When abs transition is 30 -> opaque screen see nothing
        # And when transition is 0  -> see everything so load level when all black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        self._max_screenshake: Final = pre.TILE_SIZE

        level_map_path: Path = pre.MAP_PATH
        self._level_map_count: Final[int] = len(listdir(level_map_path))

        ## Edit level manually for quick feedback gameplay iterations
        ##{#############################################################################
        self.level: int = 0
        self.levelids = {0, 1, 2, 3, 4, 5, 6, 7}  # ^_^ so all levels??!!!
        self.levelnames = {
            0: "WHERE AM I",
            1: "IS THAT IT",
            2: "WHAT GOES UP COMES DOWN",
            3: "BOXED IN",
            4: "WHAT AM I",
            5: "I USH GN EF",
            6: "I",
            7: "END OF THE BEGINNING",
        }
        ###############################################################################}

        # NOTE(Lloyd): Possible to farm this by dying repeatedly but that's alright for now
        self.player_dash_enemy_collision_count = 0

        self.running = False

    # @profile
    def set_mainscreen(
        self,
        scr: Optional["StartScreen | LoadingScreen | SettingsScreen | CreditsScreen | Game"],
    ):
        # Delete existing screen
        if self.mainscreen != None:
            del self.mainscreen
            self.mainscreen = None

        # Show new screen
        self.mainscreen = scr

        if self.mainscreen != None:
            self.mainscreen.run()
        if self.gameover:
            return AppState.MENUSTATE, GameState.EXIT
        elif not self.running:  # NOTE(Lloyd): Can just set gamestate form key-event/update loop
            return AppState.GAMESTATE, GameState.NEXTLEVEL

    # @profile
    def reset_state_on_game_completion(self) -> None:
        self.camera.reset()
        self.movement = pre.Movement(False, False, False, False)

        if self.level in self.levelids:
            self.player = Player(
                self,  # pyright: ignore [reportArgumentType]
                self._player_starting_pos.copy(),
                pg.Vector2(pre.SIZE.PLAYER),
            )
            self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)

        self.screenshake = 0
        self.gcs_deque.clear()
        self.level = 0
        self.player_dash_enemy_collision_count = 0

    # @profile
    def run(self) -> None:
        """This game loop runs continuously until the player opts out via inputs.

        Each iteration, computes user input non-blocking events, updates state
        of the game, and renders the game.
        """

        game_level_music_fname = "intro_loop.wav"
        game_level_bg_color = pre.hex_to_rgb("121607")

        def recolor_tiles(color: pre.ColorValue, border_color: pre.ColorValue):
            for i, tile in enumerate(self.assets.tiles["granite"].copy()):
                self.assets.tiles["granite"][i].fill(border_color)
                self.assets.tiles["granite"][i].fill(color=color, rect=tile.get_rect())

        recolor_tiles(self.colorscheme_green3, pre.hex_to_rgb("384510"))  # Love this color ^_^

        match self.level:
            case 0:
                game_level_music_fname = "level_0.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(pre.hex_to_rgb("425238"), pre.hex_to_rgb("597119"))
            case 1:
                game_level_music_fname = "theme_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(pre.hex_to_rgb("425238"), pre.hex_to_rgb("597119"))
            case 2:
                game_level_music_fname = "level_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(self.colorscheme_green4, pre.hex_to_rgb("384510"))
            case 3 | 4 | 5 | 6 | 7:
                game_level_music_fname = "level_2.wav"
                game_level_bg_color = pre.hex_to_rgb("121607")
                recolor_tiles(self.colorscheme_green3, pre.hex_to_rgb("384510"))  # Love this ^_^
            # NOTE(lloyd): Use a prev variable to hold last level music played
            # If we want to let it followthrough and avoid playing via pg.mixer.play()
            case _:
                assert (game_level_music_fname == "intro_loop.wav") and "expected default level music filename"

        if (
            (music_path := (pre.SRC_DATA_PATH / "music" / game_level_music_fname))
            and music_path.exists()
            and not music_path.is_dir()
        ):
            pre.load_music_to_mixer(music_path)

        # Set individual music volume
        # ---------------------------------------------------------------------
        # NOTE(lloyd): SettingsScreen is setting volume to 0 @ location of "MUTE_MUSIC" case in update().
        # We are not setting it here to avoid hassle of dynamic update via SettingsScreen in mid-gameplay,
        # maybe there is a better way??
        # NOTE(lloyd): Also is mute different from music-disabled? (In that case, avoid playing music???)
        # NOTE(lloyd): We could just pre-render audio files with similar LUFS using ay simple VU meter in a DAW.
        if not self.settings_handler.music_muted:
            pg.mixer.music.set_volume(0)
            # FIXME(Lloyd): Is this the correct API? Want music.is_playing() or .is_loaded() etc
            if pg.mixer.music.get_busy():
                pg.mixer.music.stop()
            # pg.mixer.music.play(-1)
        if not self.settings_handler.sound_muted:
            self.sfx.playerspawn.play()
        # ---------------------------------------------------------------------

        if pre.DDEBUG:
            __import__('pprint').pprint(sorted(list(pre.global_files_visited.items())), compact=True)

            paths_: Generator[str | Path, None, None] = (values[1] for values in pre.global_files_visited.values())
            cntr_ = Counter(paths_)
            __import__('pprint').pprint(cntr_)

        # On __init__ running is False. Ensure ..load(self,...) and
        # ..reset(self,...) also set it to False
        self.running = True

        while self.running:

            self.dt = self.clock.tick(pre.FPS_CAP) * 0.001
            self.display.fill((0, 0, 0, 0))
            if self.level in self.levelids:
                self.display_2.fill(game_level_bg_color)  # B.I.Y. theme
            self.events()
            self.update()
            self.render()

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
                # Bring up main menu without resetting the game
                set_mainscreen(game=self, scr=StartScreen(game=self))
            if event.type == pg.KEYDOWN:
                if event.key in (pg.K_LEFT, pg.K_a):
                    self.movement.left = True
                if event.key in (pg.K_RIGHT, pg.K_d):
                    self.movement.right = True
                if event.key in (pg.K_SPACE, pg.K_v):  # Check jump keydown and manually reset if jump keyup did occur.
                    self.player.time_jump_keyup = None if self.player.time_jump_keyup else self.player.time_jump_keyup
                    self.player.time_jump_keydown = time.time()
                    if (isjump := self.player.jump()) and isjump:
                        self.sfx.jump.play()
                if event.key in (pg.K_c, pg.K_k):
                    self.player.dash()
                if event.key in (pg.K_x, pg.K_f):
                    self.gcs_record_checkpoint()
                if event.key in (pg.K_z, pg.K_g):
                    self.gcs_rewind_recent_checkpoint()
                # if event.key in( pg.K_h,pg.K_h,): self.gcs_rewind_checkpoint()
                if event.key in (pg.K_b, pg.K_j):
                    self.gcs_remove_recent_checkpoint()
                # if event.key in( pg.K_y,pg.K_y,): self.gcs_remove_checkpoint()
            if event.type == pg.KEYUP:
                if event.key in (pg.K_LEFT, pg.K_a):
                    self.movement.left = False
                if event.key in (pg.K_RIGHT, pg.K_d):
                    self.movement.right = False
                if event.key in (pg.K_SPACE, pg.K_v):  # Check jump keyup
                    if self.player.time_jump_keydown and not self.player.time_jump_keyup:
                        self.player.time_jump_keyup = time.time()
                        self.player.deltatime_jump_keydownup = (
                            self.player.time_jump_keyup - self.player.time_jump_keydown
                        )
                        if (
                            self.player.deltatime_jump_keydownup < self.player.jump_buffer_interval
                            and self.player.air_timer <= 5 * self.player.max_air_time
                            and not self.player.wallslide
                            and not self.player.collisions.left
                            and not self.player.collisions.right
                            and -self.player.jump_force <= self.player.velocity.y < 0
                            and abs(self.player.velocity.x) <= 0.1
                        ):
                            if self.player.dash_timer and self.player.velocity.y <= 0.1:
                                self.player.velocity.y = -3.0

                                if self.player.last_movement.x and (player_dir := (-1 if self.player.flip else 1)):
                                    self.player.velocity.x = player_dir * 2.00
                            # Where 3 is jump force                                                                vvv
                            elif self.player.coyote_timer and (self.player.air_timer <= (self.player.max_air_time * 3)):
                                self.player.velocity.y += 1.35
                                if self.player.last_movement.x and (player_dir := (-1 if self.player.flip else 1)):
                                    self.player.velocity.x = player_dir * 2.25
                                    self.player.velocity.x *= (
                                        1.328
                                        if 1 < abs(self.player.velocity.x) < 2
                                        else 0.5 if 0 < abs(self.player.velocity.x) <= 1 else 1.0
                                    )

    def render(self) -> None:
        """Render display."""

        # Create background buffer---------------------------------------------
        # ---------------------------------------------------------------------
        if self.level in self.levelids:
            pass
        else:
            if self.bg_blue_sky_surf:
                self.display_2.blit(self.bg_blue_sky_surf, (0, 0))
            if self.bg_cloud_surf:
                self.display_2.blit(self.bg_cloud_surf, self.bg_cloud.pos)
            if self.bg_cloud_surf:
                self.display_2.blit(self.bg_cloud_surf, (self.bg_cloud.pos + (self.bg_display_w, 0)))  # Wrap around
            if self.bg_mountain_surf:
                self.display_2.blit(self.bg_mountain_surf, self.bg_mountain.pos)
            if self.bg_mountain_surf:  # Wrap around
                self.display_2.blit(self.bg_mountain_surf, (self.bg_mountain.pos + (self.bg_display_w, 0)))
        # ---------------------------------------------------------------------

        # Create a transition surface with a circular cutout-------------------
        # ---------------------------------------------------------------------
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
            pg.draw.circle(surf, (255, 255, 255), center, radius)  # White color on screen acts as transparent mask
            surf.set_colorkey((255, 255, 255))  # And now anything outside of mask is opaque black
            self.display.blit(surf, (0, 0))
        # ---------------------------------------------------------------------

        # Final buffer swap 3-stage rendering
        # ---------------------------------------------------------------------
        # Display Mask: Drop Shadow Trick
        display_mask = pg.mask.from_surface(self.display)
        display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))

        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.display_2.blit(display_silhouette, offset)

        self.display_2.blit(self.display, (0, 0))
        # TODO(Lloyd):  - Enable toggling from Gameplay to Menu screen with Esc.
        #               - Rename setting items to present the state. e.g. `SCREENSHAKE: OFF`
        # MAYBE(Lloyd): - Assign precedence to this
        #               - Or, preset settings_handler members from config_handler
        #                 at load player config file
        #                 and (self.config_handler.screenshake or self.settings_handler.screenshake)
        dest = (
            ((shake * random()) - halfshake, (shake * random()) - halfshake)
            if (shake := self.screenshake, halfshake := (shake * 0.5)) and self.settings_handler.screenshake
            else (0.0, 0.0)
        )
        self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), dest)
        pg.display.flip()
        # ---------------------------------------------------------------------

    def _increment_player_dead_timer(self):
        if pre.DEBUG_GAME_PRINTLOG:
            print(f"{Path(__file__).name}: [{time.time():0.4f}] {self.dead = }")  # fmt: skip
        self.dead += 1

    def update(self) -> None:
        self.gameleveltimer.current = time.perf_counter()

        # Camera: Update and Parallax
        # ---------------------------------------------------------------------
        plyr_rect = self.player.rect
        snapy = plyr_rect.centery % self.level_map_dimension[1]

        # Either snap camera to top floor of map area
        # Or snap camera to ground floor of map area
        if snapy < self.camerasize[1]:
            snapy = plyr_rect.centery // 4  # fmt: skip
        elif snapy > (self.level_map_dimension[1] - self.camerasize[1]) + (self.player.size.y * 2):
            snapy = plyr_rect.centery + self.camerasize[1] // 2  # fmt: skip

        self.camera.update((plyr_rect.centerx, snapy), self.level_map_dimension, self.dt)
        render_scroll: tuple[Literal[0], Literal[0]] | tuple[int, int] = self.camera.render_scroll
        if pre.DEBUG_GAME_CAMERA:
            self.camera.debug(surf=self.display, target_pos=(int(plyr_rect.x), int(plyr_rect.y)))  # fmt: skip

        self.bg_cloud.pos.x -= (
            math.floor(math.floor(uniform(2, 3) * 100 * self.bg_cloud.speed * self.bg_cloud.depth) / 10) / 10
        )
        if self.bg_cloud.pos.x < -self.bg_display_w:  # <- 480
            self.bg_cloud.pos.x = 0

        self.bg_mountain.pos.x = math.floor(
            math.floor(self.bg_mountain.pos.x - self.camera.render_scroll[0])
            * self.bg_mountain.depth
            * self.bg_mountain.speed
        )
        if self.bg_mountain.pos.x < -self.bg_display_w:
            self.bg_mountain.pos.x = 0

        self.screenshake = max(0, self.screenshake - 1)
        # ---------------------------------------------------------------------

        # Check for game level transitions
        # ---------------------------------------------------------------------
        if self.collected_all_enemies and self.touched_portal:  # Win condition
            self.transition += 1
            if self.transition > self._transition_hi:  # Check if transition to the next level is required
                lvl_no_more_levels_left: bool = (self.level + 1) >= self._level_map_count
                if lvl_no_more_levels_left:
                    self.gameover = True  # LoadingScreen will reset this later
                    self.gamecompleted = True
                    self.reset_state_on_game_completion()
                else:
                    self.lvl_increment_level()

                self.gameleveltimer.end = time.perf_counter()
                assert (
                    self.gameleveltimer.start is not None
                ), "expected game level timer start time to be initialized before calculating elapsed"
                self.gameleveltimer.elapsed = self.gameleveltimer.end - self.gameleveltimer.start
                self.running = False  # Trigger loading screen
        if self.transition < self._transition_mid:
            self.transition += 1
        if self.dead:
            self._increment_player_dead_timer()  # Expands to `self.dead += 1`
            if self.dead >= self._dead_mid:  # Ease into incrementing for level change till _hi
                self.transition = min(self._transition_hi, self.transition + 1)
            if self.dead >= self._dead_hi:
                self.lvl_load_level(self.level)
        # ---------------------------------------------------------------------

        # Replenish health and revert to last checkpoint instead of "death"
        if self.dead_hit_skipped_counter == 0 and self.respawn_death_last_checkpoint:
            self.gcs_rewind_recent_checkpoint(record_current=False)
            self.respawn_death_last_checkpoint = False

        # Stars: Backdrop update and render
        if self.level in self.levelids:
            # Stars drawn behind everything else
            self.stars.update()
            # Blitting display_2 avoids masks depth
            self.stars.render(self.display_2, render_scroll)

        # Tilemap: render
        self.tilemap.render(self.display, render_scroll)

        # Update(HACK: ...and Draw) drop-point location zones
        # ----------------------------------------------------------------------
        if not self.dead and (position_ := self.player_spawner_pos) and position_:
            surf = self.assets.tiles["portal"][1].copy()  # NOTE(Lloyd): Copying sanity check
            surf_w = surf.get_width()
            surf_h = surf.get_height()
            anim_offset_y: Final = 3
            dest_position: Final[Tuple[float, float]] = (
                (position_.x - (surf.get_width() / 2) - render_scroll[0]),
                (position_.y - (surf.get_height() / 2) + anim_offset_y - render_scroll[1]),
            )
            # On victory, draw spark lines around flags to signify SUCCESS state.
            # This lets the player realize to go to flag_end
            # ---------------------------------------------------------------------
            for enemy in self.enemies:
                if enemy.is_collected_by_player and enemy in self.collected_enemies_seen:
                    if not abs(enemy.pos.y - self.player_spawner_pos.y) < 32:
                        self.collected_enemies_seen.remove(enemy)
                        enemy.is_collected_by_player = False

                if abs(enemy.pos.y - self.player_spawner_pos.y) < 32:
                    if enemy not in self.collected_enemies_seen:
                        self.collected_enemies_seen.add(enemy)
                        enemy.is_collected_by_player = True  # This flag is used to indicate success capture in the HUD.
            ###################################################################
            # TODO: REMEMBER TO CLEAR THIS AT END OF LEVEL
            # self.collected_enemies_seen.clear()
            ###################################################################

            # Flag win condition
            self.collected_all_enemies = len(self.collected_enemies_seen) == len(self.enemies)
            if self.collected_all_enemies:
                # Draw flag success sparks
                if pre.DDEBUG:
                    MAX_DY = math.ceil(surf_h // 1.618)
                    CLR0, CLR1 = pre.hex_to_rgb("cac063"), pre.hex_to_rgb("acc167")
                    _ssurf: pg.SurfaceType = self.display
                    _scenter: Tuple[float, float] = ((dest_position[0] + surf_w // 2), (dest_position[1] + surf_h))
                    color = None
                    _dy = 0.0
                    for i in range(0, (surf_h * 2)):
                        if _dy > MAX_DY:
                            break
                        color = CLR0 if random() < 0.8 else CLR1
                        for j in range(0, surf_w // 4):
                            pg.draw.circle(_ssurf, color, (_scenter[0] + (4 * j), (_scenter[1] - _dy)), 1)
                            pg.draw.circle(_ssurf, color, (_scenter[0] - (4 * j), (_scenter[1] - _dy)), 1)
                        _dy += pre.TILE_SIZE / 8

            # Draw start drop location
            self.display.blit(surf, dest_position)
            # ------------------------------------------------------------------
        # ----------------------------------------------------------------------

        # Portal: Detect and Render
        # ----------------------------------------------------------------------
        if not self.touched_portal:
            # NOTE(Lloyd): This disappears very fast
            for i, portal in enumerate(self.portal_spawners):
                if self.collected_all_enemies and self.player.rect.colliderect(portal.rect()):
                    self.touched_portal = True
                    if self.level != self._level_map_count:
                        self.sfx.portaltouch.play()
                self.display.blit(portal.assets[i], portal.pos - render_scroll)
        # ---------------------------------------------------------------------

        # Enemy: update and render
        # ---------------------------------------------------------------------
        for enemy in self.enemies.copy():
            kill_animation = enemy.update(self.tilemap, pg.Vector2(0, 0))
            enemy.render(self.display, render_scroll)
            if kill_animation:
                self.enemies.remove(enemy)
        # ---------------------------------------------------------------------

        # Update Interactive Spawners
        # ---------------------------------------------------------------------
        for rect_spike in self.spike_spawners:
            if self.player.rect.colliderect(rect_spike):
                self._increment_player_dead_timer()  # self.dead += 1

        for rect_bp in self.bouncepad_spawners:
            if self.player.rect.colliderect(rect_bp):
                if self.player.jump():
                    # HACK(Lloyd): Avoid freefall death & allow infinite jumps
                    self.player.air_timer = 0
                    self.player.velocity.y = -5
                    self.sfx.jump.play()

            for enemy in self.enemies:
                if enemy.rect.colliderect(rect_bp):
                    enemy.velocity.y -= 3
                    # HACK(Lloyd): Avoid infinite jump at the same spot
                    if enemy.rect.left < rect_bp.left:
                        enemy.velocity.x -= 2.0
                    elif enemy.rect.right > rect_bp.right:
                        enemy.velocity.x += 2.0
                    else:
                        enemy.velocity.x += randint(-3, 3)

                    self.sfx.jump.play()
        # ---------------------------------------------------------------------

        # Update and Draw GameCheckpoints
        # ---------------------------------------------------------------------
        for i, state in enumerate(self.gcs_deque):
            radius_: int = math.ceil(2 * (1 + 1 / (1 + i)))  # radius -> 2
            checkpoint_center: Tuple[int, int] = (
                math.ceil(state.player_position[0] - render_scroll[0]),
                math.ceil(state.player_position[1] - render_scroll[1]),
            )
            pg.draw.circle(self.display, self.colorscheme_green3, checkpoint_center, radius=(radius_ + 2))
            pg.draw.circle(self.display, self.colorscheme_green5, checkpoint_center, radius=radius_)
            if pre.DDEBUG:
                self.draw_text(
                    checkpoint_center[0],
                    (checkpoint_center[1] - math.floor(2 * math.pi * radius_)),
                    self.font_xs,
                    self.colorscheme_green3,
                    f"{i+1}",
                )
        # ---------------------------------------------------------------------

        # Player: update and render
        # ---------------------------------------------------------------------
        if not self.dead:
            self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
            self.player.render(self.display, render_scroll)
        # ---------------------------------------------------------------------

        # Gun: projectiles and sparks
        # ---------------------------------------------------------------------
        for projectile in self.projectiles:
            projectile.pos[0] += projectile.velocity
            projectile.timer += 1

            img: pg.SurfaceType = self.assets.misc_surf["projectile"]
            img_offset_w: Final[int] = img.get_width() // 2
            dest = (
                projectile.pos[0] - img_offset_w - render_scroll[0],
                projectile.pos[1] - img_offset_w - render_scroll[1],
            )
            self.display.blit(img, dest)

            # Projectile post render: update. int -> precision for grid system
            projectile_x, projectile_y = int(projectile.pos[0]), int(projectile.pos[1])
            if self.tilemap.maybe_solid_gridtile_bool(pg.Vector2(projectile_x, projectile_y)):
                self.projectiles.remove(projectile)  # Wall sparks bounce opposite to projectile's direction
                spark_speed, spark_direction = 0.5, (
                    math.pi if (projectile.velocity > 0) else 0
                )  # NOTE(Lloyd): unit circle direction (0 left, right math.pi)
                self.sparks.extend(
                    Spark(projectile.pos, angle, speed)
                    for _ in range(4)
                    if (angle := (random() - spark_speed + spark_direction), speed := (2 + random()))
                )
                self.sfx.hitwall.play()
            elif projectile.timer > 360:
                self.projectiles.remove(projectile)
            elif abs(self.player.dash_timer) < self.player.dash_burst_2:
                if self.player.rect.collidepoint(projectile_x, projectile_y):  # Player is vulnerable
                    # Player looses health but still alive if idle or still
                    if (self.player.action == Action.IDLE) and (
                        self.dead_hit_skipped_counter < self.player.max_dead_hit_skipped_counter
                    ):
                        self.screenshake = max(self._max_screenshake, self.screenshake - 0.5)
                        self.projectiles.remove(projectile)
                        self.sparks.extend(
                            Spark(pg.Vector2(self.player.rect.center), angle, speed)
                            for _ in range(30)
                            if (angle := random() * math.pi * 2, speed := 2 + random())
                        )
                        self.sfx.hitmisc.play()
                        # NOTE(Lloyd): Should reset this if players action
                        # state changes from idle to something else
                        self.dead_hit_skipped_counter += 1
                    # Player death OR send back in time(checkpoint)
                    else:
                        self.screenshake = max(self._max_screenshake, self.screenshake - 1)
                        self.projectiles.remove(projectile)
                        self.sparks.extend(
                            Spark(pg.Vector2(self.player.rect.center), angle, speed, pg.Color("cyan"))
                            for _ in range(30)
                            if (angle := random() * math.pi * 2, speed := 2 + random())
                        )
                        self.particles.extend(
                            Particle(
                                self,  # pyright: ignore [reportArgumentType]
                                pre.ParticleKind.PARTICLE,
                                pg.Vector2(self.player.rect.center),
                                velocity,
                                frame,
                            )
                            for _ in range(30)
                            if (
                                angle := (random() * math.pi * 2),
                                speed := (random() * 5),
                                velocity := pg.Vector2(math.cos(angle + math.pi) * speed / 2),
                                frame := randint(0, 7),
                            )
                        )
                        self.sfx.hit.play()
                        # NOTE(Lloyd): Next iteration, when counter is 0 player
                        # pos is reverted to last checkpoint instead of death.
                        if (_death_by_projectile_enabled := 0) and _death_by_projectile_enabled:
                            self._increment_player_dead_timer()
                        # Replenish health
                        else:
                            self.dead_hit_skipped_counter = 0
                            self.respawn_death_last_checkpoint = True
        # ---------------------------------------------------------------------

        # Update Sparks
        # ---------------------------------------------------------------------
        for spark in self.sparks.copy():
            kill_animation: bool = spark.update()
            spark.render(self.display, offset=render_scroll)
            if kill_animation:
                self.sparks.remove(spark)
        # ---------------------------------------------------------------------

        # Update particles
        # ---------------------------------------------------------------------
        for particle in self.particles.copy():
            kill_animation: bool = particle.update()
            particle.render(self.display, render_scroll)
            if not kill_animation:
                continue

            match particle.kind:
                case pre.ParticleKind.PARTICLE:
                    if not (self.level in self.levelids):
                        self.particles.remove(particle)
                    else:
                        # NOTE(Lloyd): Frame count is static after kill_animation
                        decay_initial_value, decay_factor, decay_iterations = 1, 0.95, particle.animation.frame
                        decay = decay_initial_value * (decay_factor**decay_iterations)
                        amplitude_clamp = 0.328
                        chaos = amplitude_clamp * math.sin(particle.animation.frame * 0.035)
                        particle.velocity.x -= math.copysign(1, particle.velocity.x) * chaos * decay * uniform(8, 16)
                        particle.velocity.y -= math.copysign(1, particle.velocity.y) * chaos * decay * uniform(8, 16)

                        if random() < uniform(0.01, 0.025):
                            self.particles.remove(particle)

                case _:
                    self.particles.remove(particle)
        # ---------------------------------------------------------------------

        # Update(and HACK: Draw) Game Stats HUD
        # TODO: <<<< MOVE RENDERING INSTRUCTIONS TO `render()` >>>>
        # ---------------------------------------------------------------------
        hud_dest: Final[Tuple[int, int]] = (self.bg_display_w // 2 - pre.TILE_SIZE, 0)

        # Draw enemy icons.
        icon_offset_x: Final[int] = 8
        icon_offset_y: Final[int] = 4
        icon_status_radius: Final[float] = 0.618 * (pre.TILE_SIZE / math.pi)
        accum_offset_x: Final[int] = math.ceil(1.618 * pre.TILE_SIZE)  # Icon spacing
        accum_x: int = 0
        for enemy in self.enemies:
            # Draw icons.
            icon_dest: Final[Tuple[int, int]] = (hud_dest[0] + icon_offset_x + accum_x, hud_dest[1] + icon_offset_y)
            rec = self.hud_surf.blit(self.hud_enemy_icon_surf, icon_dest)
            accum_x -= accum_offset_x
            # Draw status indicator.
            status_center: Tuple[int, int] = (rec.x, (rec.y + (rec.h // 2) + int(icon_status_radius)))

            # First clear circle. to avoid barely visible outlined circle on top of solid circle
            pg.draw.circle(self.hud_surf, (0, 0, 0, 0), status_center, icon_status_radius, 0)
            if enemy.is_collected_by_player:
                pg.draw.circle(self.hud_surf, (222, 222, 222), status_center, icon_status_radius, 0)
            else:
                pg.draw.circle(self.hud_surf, (255, 255, 255), status_center, icon_status_radius, 1)

        def _is_last_framecountdown_for_interval(timediff: int, interval: int = 10, framecount: int = 4) -> bool:
            """framecount should not be less than interval. for a period of 10 seconds, expect the last 4 count 7.8.9.10"""
            return True if interval <= framecount else any(((timediff + i) % interval) == 0 for i in range(framecount))

        # Draw timer
        if self.gameleveltimer.start and (
            elapsed_time := math.floor(self.gameleveltimer.current - self.gameleveltimer.start)
        ):
            tlabel = f"{elapsed_time}"
            self.draw_text(
                int(hud_dest[0] + self.bg_display_w // 2),
                int(hud_dest[1] + 32),
                self.font_xs,
                (255, 255, 255),
                tlabel,
            )

        # Draw HUD with pre-rendered buffer on display.
        self.display.blit(self.hud_surf, hud_dest, special_flags=pg.BLEND_ALPHA_SDL2)
        # ---------------------------------------------------------------------

        # Update (and HACK: Draw) Debugging HUD
        # ---------------------------------------------------------------------
        if pre.DEBUG_GAME_HUD and (
            raw_mouse_pos := (pg.Vector2(pg.mouse.get_pos()) / pre.RENDER_SCALE),
            mouse_position := (raw_mouse_pos + render_scroll),
            mouse_pos_ints := (math.floor(mouse_position.x), math.floor(mouse_position.y)),
        ):
            render_debug_hud(self, self.display, render_scroll, mouse_pos_ints)
            # Update clock values.
            self.clock_dt_recent_values.appendleft(self.dt)
            if len(self.clock_dt_recent_values) == pre.FPS_CAP:
                self.clock_dt_recent_values.pop()
        # ---------------------------------------------------------------------

    def lvl_increment_level(self):
        self.gcs_deque.clear()
        self.camera.reset()

        prev = self.level

        # Avoid game level reseting to (0+1) after player completes game and wants
        # to start over again
        if self.gamecompleted:
            self.level, self.gamecompleted = 0, not self.gamecompleted
        else:
            self.level = min(self.level + 1, self._level_map_count - 1)

        return dict(prev=prev, next=self.level)

    def _lvl_load_level_map(self, map_id: int):
        map_path = pre.MAP_PATH / f"{map_id}.json"  # map_path: str = path.join(pre.MAP_PATH, f"{map_id}.json")
        pre.global_files_visited_update(map_path, opts=dict(file_=__file__, line_=pre.get_current_line()))
        self.tilemap.load(path=map_path)

    # @profile
    def lvl_load_level(self, map_id: int, progressbar: Optional[queue.Queue[int]] = None) -> None:
        progress = 0
        if progressbar:
            progressbar.put(progress)

        self._lvl_load_level_map(map_id)
        self.level_map_dimension = self.tilemap.cur_level_map_dimension  # 1470 approx for level1, 480 for level2

        if pre.DEBUG_GAME_PRINTLOG:  # FIX: Dual loading at game over
            print(f"{Path(__file__).name}: [{time.time():0.4f}] {self.level_map_dimension = }")

        progress += 5
        if progressbar:
            progressbar.put(progress)

        self.projectiles: list[pre.Projectile] = []
        self.sparks: list[Spark] = []

        # Create HUD surface.
        self.hud_size: Tuple[int, int] = (256, 48)
        self.hud_surf = pg.Surface(self.hud_size, flags=pg.SRCALPHA).convert_alpha()
        self.hud_enemy_icon_surf: pg.SurfaceType = self.assets.entity["enemy"].copy()

        # Add semi-transparent background to HUD.
        self.hud_bg_surf: Optional[pg.SurfaceType]
        if 0:
            self.hud_bg_surf = pg.Surface(self.hud_size, flags=pg.SRCALPHA).convert_alpha()
            if self.hud_bg_surf:  # @Redundant
                self.hud_bg_surf.set_colorkey(pg.Color("black"))
                self.hud_bg_surf.fill(pre.CHARCOAL)
                self.hud_bg_surf.set_alpha(127)
                self.hud_surf.blit(self.hud_bg_surf, (0, 0))

        # Background parallax layers
        if skyimg := self.assets.misc_surf.get("bg1"):
            img_flip_y = pg.transform.flip(skyimg.copy(), 0, 1)
            self.bg_blue_sky_surf: Optional[pg.SurfaceType] = pg.transform.average_surfaces((skyimg, img_flip_y))
        if cloudimg := self.assets.misc_surf.get("bg2"):
            self.bg_cloud_surf: Optional[pg.SurfaceType] = cloudimg
        if mountainimg := self.assets.misc_surf.get("bg3"):
            self.bg_mountain_surf: Optional[pg.SurfaceType] = mountainimg

        self.grid_surf: Optional[pg.SurfaceType] = None
        if 0:
            if self.level in self.levelids:
                self.grid_surf = pre.create_surface(
                    self.display.get_size(), colorkey=(0, 0, 0), fill_color=(0, 0, 0)
                ).convert()
                grid_surf_pixels = (  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]
                    pg.surfarray.pixels3d(  # pyright: ignore [reportUnknownMemberType, reportUnknownVariableType]
                        self.grid_surf
                    )
                )
                for x in range(0, pre.DIMENSIONS_HALF[0], self.tilemap.tilesize):
                    grid_surf_pixels[x, :] = (26, 27, 26)
                for y in range(0, pre.DIMENSIONS_HALF[1], self.tilemap.tilesize):
                    grid_surf_pixels[:, y] = (26, 27, 26)
                # Convert the pixel array back to a surface
                del grid_surf_pixels  # Unlock the pixel array

        self.bg_display_w = pre.DIMENSIONS_HALF[0]  # 480
        self.bg_cloud = Background(depth=0.1 or 0.2, pos=pg.Vector2(0, 0), speed=0.5)
        # NOTE(Lloyd): Higher speed causes janky wrapping of bg due to render scroll ease by 1 or 2 tilesize
        self.bg_mountain = Background(depth=0.6, pos=pg.Vector2(0, 0), speed=0.4)

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

        # 8 thickness  # actual w 16  # actual h 64
        self.bouncepad_spawners = [
            pg.Rect(tileitem.pos.x, tileitem.pos.y + 32 - 8, pre.TILE_SIZE, pre.TILE_SIZE)
            for tileitem in self.tilemap.extract(
                [("bouncepad", 0), ("bouncepad", 1), ("bouncepad", 2), ("bouncepad", 3)], keep=True
            )
        ]
        self.spike_spawners = list(
            self.tilemap.spawn_spikes(
                self.tilemap.extract([("spike", 0), ("spike", 1), ("spike", 2), ("spike", 3)], keep=True)
            )
        )

        progress += 10
        if progressbar:
            progressbar.put(progress)

        # Handle spawners
        # ---------------------------------------------------------------------
        spawner_kinds: Final = (pre.SpawnerKind.PLAYER.value, pre.SpawnerKind.ENEMY.value, pre.SpawnerKind.PORTAL.value)
        progress_increment = math.floor((70 - progress) / len(spawner_kinds))

        self.portal_spawners: list[Portal] = []
        self.enemies: list[Enemy] = []

        for spawner in self.tilemap.extract(
            list(zip(it.repeat(str(pre.TileKind.SPAWNERS.value), len(spawner_kinds)), spawner_kinds)),
            False,
        ):
            match pre.SpawnerKind(spawner.variant):
                case pre.SpawnerKind.PLAYER:  # Coerce to a mutable list if pos is a tuple
                    self.player_spawner_pos = spawner.pos.copy()
                    if self.gcs_deque:
                        self.gcs_rewind_recent_checkpoint(record_current=False)
                    else:
                        self.player.pos = spawner.pos.copy()
                    self.player.air_timer = 0  # Reset time to avoid multiple spawns during fall
                case pre.SpawnerKind.ENEMY:
                    self.enemies.append(
                        Enemy(
                            game=self,  # pyright: ignore [reportArgumentType]
                            pos=spawner.pos,
                            size=pg.Vector2(pre.SIZE.ENEMY),
                        )
                    )
                case pre.SpawnerKind.PORTAL:
                    self.portal_spawners.append(
                        Portal(
                            game=self,  # pyright: ignore [reportArgumentType]
                            ekind=pre.EntityKind.PORTAL,
                            pos=spawner.pos,
                            size=pg.Vector2(pre.TILE_SIZE),
                        )
                    )

            progress += progress_increment
            if progressbar:
                progressbar.put(progress)
        # ---------------------------------------------------------------------

        if pre.DEBUG_GAME_ASSERTS:
            assert self.player is not None, f"want a spawned player. got {self.player}"
            assert (val := len(self.enemies)) > 0, f"want atleast 1 spawned enemy. got {val}"
            assert (val := len(self.portal_spawners)) > 0, f"want atleast 1 spawned portal. got {val}"

        self.particles: list[Particle] = []

        self.scroll = pg.Vector2(
            0.0, 0.0
        )  # NOTE(Lloyd): This seems redundant now after adding self.camera that handles scroll and render_scroll.

        self.dead = 0  # Tracks if the player died -> 'reloads level'

        self.respawn_death_last_checkpoint = False

        self.dead_hit_skipped_counter = (
            0  # If player is invincible while idle and hit. Also count amount of shield that is being hit on.
        )

        # Win Condition Checkers
        # ---------------------------------------------------------------------
        self.touched_portal = False

        self.collected_all_enemies = False
        self.collected_enemies_seen: Set[Enemy] = set()
        # self.collected_enemies_counter = 0
        # ---------------------------------------------------------------------

        self.transition = self._transition_lo

        if pre.DEBUG_GAME_ASSERTS:
            if (tlevel_id := self.gameleveltimer.levelid) and self.level != 0 and tlevel_id:
                assert tlevel_id == (self.level - 1)
        self.gameleveltimer.levelid = self.level
        self.gameleveltimer.start = time.perf_counter()
        self.gameleveltimer.end = None  # Cleanup old data
        self.gameleveltimer.elapsed = None  # Cleanup old data

        progress = 100  # Done
        if progressbar:
            progressbar.put(progress)

        if 1:  # HACK(Lloyd): Emulate loading heavy resources.
            # Context: Players may not like sudden level changes.
            time.sleep(uniform(0.500, 0.750))

    def draw_text(
        self,
        x: int,
        y: int,
        font: pg.font.Font,
        color: pre.ColorValue,
        text: str,
        antialias: bool = True,
    ) -> pg.Rect:
        surf = font.render(text, antialias, color)
        rect: pg.Rect = surf.get_rect()
        rect.midtop = (x, y)
        return self.display.blit(surf, rect)

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
                enemy.sleep_timer = enemy.max_sleep_time
                enemy.set_action(Action.SLEEPING)  # NOTE(Lloyd): If enemy was sleeping already, this may not work

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
                enemy.sleep_timer = enemy.max_sleep_time
                # NOTE(Lloyd): If enemy was sleeping already, this may not work
                enemy.set_action(Action.SLEEPING)

        self.player.pos = next_pos.copy()
        self.sfx.teleport.play()


# ------------------------------------------------------------------------------
# GAME LOADING SCREEN (LEVEL RESOURCE LOADER)
# ------------------------------------------------------------------------------


class LoadingScreen:
    # @profile
    def __init__(self, game: Game, level: int) -> None:
        self.game = game
        self.level = level

        self.clock = pg.time.Clock()  # Or use game's clock?

        self.w, self.h = pre.DIMENSIONS_HALF

        self.fontsize = 18  # 9*2: Font author suggest multiples of 9

        self.font_sm = self.game.font_sm
        self.font_xs = self.game.font_xs

        self.font_sm_linesize = self.font_sm.get_linesize()
        self.font_xs_linesize = self.font_xs.get_linesize()

        self.queue: queue.Queue[int] = queue.Queue()
        self.queue.put(0)
        self.progress: int = self.queue.get()  # 0% initially

        if pre.DEBUG_GAME_ASSERTS:  # WHY: self.queue.join()
            assert self.queue.qsize() == 0 or self.queue.empty()

    # @profile
    def run(self) -> None:
        self.bgcolor = pre.COLOR.BACKGROUND

        running = True

        while running:
            loading_thread: Optional[threading.Thread] = None

            match self.level:
                case _:
                    loading_thread = threading.Thread(target=self.game.lvl_load_level, args=(self.level, self.queue))
                    loading_thread.start()

            while True:
                # NOTE(Lloyd): Do not tick to avoid slow loading time??
                # self.clock.tick(pre.FPS_CAP)
                self.events()
                self.update()
                self.render()
                if loading_thread and not loading_thread.is_alive():
                    # NOTE(Lloyd): THIS IS CRAZY CODE UGHH!! -_-
                    _ = set_mainscreen(game=self.game, scr=self.game)
                    if not self.game.running:
                        break

            # Sync state changes
            if not self.game.running:
                self.game.running = True
                self.level = self.game.level

                if self.game.gameover:
                    running = False
                    # NOTE(Lloyd): I don't know what is going on here anymore -_-
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
        # Clear screen and render background
        self.game.display.fill(self.bgcolor)

        pbar_h = 30 // 6
        pbar_w = (self.w - (self.w / 4)) // 3

        x = (self.w / 2) - (pbar_w / 2)
        y = self.h / 2

        pcounter = self.progress / 100
        if pcounter >= 1:
            pcounter = 1

        pbar_fill = pcounter * pbar_w
        pbar_outline_rect = pg.Rect(x - 10 / 2, y - 10 / 2, pbar_w + 20 / 2, pbar_h + 20 / 2)
        pbar_fill_rect = pg.Rect(x, y, pbar_fill, pbar_h)

        # Draw bar
        pg.draw.rect(self.game.display, pre.WHITE, pbar_fill_rect)
        pg.draw.rect(self.game.display, pre.WHITE, pbar_outline_rect, 1)

        # Draw text
        textlevel = f"STAGE {self.game.level}"
        rect_level_text: pg.Rect = self.game.draw_text(
            self.w // 2 - self.font_sm_linesize // 2,
            self.h // 2 - self.font_sm_linesize // 2 - pbar_h - 50,
            self.font_sm,
            pg.Color('maroon'),
            textlevel,
        )
        textlevelname = f"{self.game.levelnames.get(self.game.level, '...')}"
        self.game.draw_text(
            self.w // 2 - self.font_xs_linesize // 2,
            (rect_level_text.y + (2 * self.font_xs_linesize)),
            self.font_xs,
            pre.WHITE,
            textlevelname,
        )

        dispmask: pg.Mask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)

        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))
        pg.display.flip()  # This *flip*s the display


# ------------------------------------------------------------------------------
# GAME CREDITS SCREEN (CREDITS MENU PLAY ROLL)
# ------------------------------------------------------------------------------


class CreditsScreen:
    def __init__(self, game: Game, level: int) -> None:
        self.game = game
        self.level = level

        # NOTE(lloyd): using this as Game.set_screen(screen: 'CreditsScreen |
        # Game | ...') requires each args passed to __init__ to have game and
        # level. doing this via manual inheritance. sigh OOP -_-
        self.w, self.h = pre.DIMENSIONS_HALF

        self.start_font = self.game.font_sm
        self.title_font = self.game.font

        self.bgcolor = pre.DARKCHARCOAL

        self.clock = pg.time.Clock()  # Or use game's clock?
        self.running = True

        self.fps = self.clock.get_fps()

        # Start credit roll from bottom??
        _offset_x = 32
        self.creditroll_x = (self.w // 2) - _offset_x

        self.creditroll_y = self.h  # Start credit roll from bottom

        self.previous_credit = -1
        self.current_credit = 0
        self.can_switch_to_next_credit = False

        self.credit_item_offset_y = 20  # temp
        self.prev_daw_timer = 970

        # Using non-floats value for index to emulate DAWs
        # Data Structure: (endtime, content, color)
        self.credits = [
            (1000, "TIP", pg.Color("maroon")),
            (1019, "TOE", pg.Color("maroon")),
            (1050, "2024", pg.Color("white")),
            (1080, "DESIGN * CODE * ETC * BY LLOYD LOBO", pg.Color("cyan")),
            (1110, "MUSIC * SOUNDS * SFX * BY LLOYD LOBO", pg.Color("cyan")),
            (1140, "GAME LIBRARY * BY PYGAME", pg.Color("cyan")),
        ]

        # FUTURE(Lloyd): If time permits work on animating start and end times
        # declaratively. Remember `worse is better`!!!
        self.credits_marque = [(0, 3000, "TIP TOE"), (3000, 6000, "CREATED BY LLOYD LOBO")]

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
            self.clock.tick(pre.FPS_CAP // 2)  # Play at half-speed
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
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.running = False

    def update(self):
        # Clear screen and render background
        self.game.display.fill(self.bgcolor)

        if self.current_credit == (self.MAX_CREDITS_COUNT - 1):
            last_position = self.creditroll_y + self.current_credit * self.credit_item_offset_y
            last_item_is_above_fold = last_position <= (-1 * (self.h // 4)) + self.credit_item_offset_y
            if last_item_is_above_fold:  # Exit current screen
                self.running = False

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
        # FIXME: Stop manually overriding this branch
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
        FIXME(Lloyd): Either change offset_y or add to it or lerp it also
        consider creditroll_y:
            y=pos_y + (i * (offset_y * 1 + self.daw_timer_markers_offset)),
        """

        # Draw credits vertical marque
        # ---------------------------------------------------------------------
        offset_y = self.credit_item_offset_y
        pos_y = self.creditroll_y

        for i, credit in enumerate(self.credits):
            if i > self.current_credit:
                continue
            if i > 0:
                offset_y = self.credits[i][0] - self.credits[i - 1][0]
            self.game.draw_text(
                (self.w // 2),
                (pos_y + (i * offset_y)),
                self.start_font,
                color=(self.credits[i][2]),
                text=credit[1],
            )
        # ---------------------------------------------------------------------

        # Draw mask outline for all
        # ---------------------------------------------------------------------
        dispmask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)
        # ---------------------------------------------------------------------

        # Render display
        # ---------------------------------------------------------------------
        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))
        pg.display.flip()
        # ---------------------------------------------------------------------


# ------------------------------------------------------------------------------
# GAME SETTINGS SCREEN (SETTINGS MENU)
# ------------------------------------------------------------------------------


class SettingsScreen:
    """Implements SettingsScreen that provide game settings.
    It is accessed via StartScreen main menu.
    """

    def __init__(self, game: Game, level: int) -> None:
        self.game = game
        self.level = level

        # NOTE(lloyd): Using this as Game.set_screen(screen: 'CreditsScreen | # Game | ...')
        # requires each args passed to __init__ to have game and level.
        # So doing # this via manual inheritance. sigh OOP -_-
        #
        self.w, self.h = pre.DIMENSIONS_HALF
        self.clock = pg.time.Clock()  # Or use game's clock?
        self.running = True

        # Update key events on navigation buttons
        # ---------------------------------------------------------------------
        self.FONT_TYPES = [self.game.font_xs, self.game.font_sm, self.game.font]
        font = FontType.SM

        position_x, position_y = self.w // 2, self.h // 2
        offset_x, offset_y = 0, 16

        self.settings = [
            ((position_x + offset_x), (position_y + (0 * offset_y)), font, pg.Color("white"), SETTINGS_NAVITEMS[0]),
            ((position_x + offset_x), (position_y + (1 * offset_y)), font, pg.Color("white"), SETTINGS_NAVITEMS[1]),
            ((position_x + offset_x), (position_y + (2 * offset_y)), font, pg.Color("white"), SETTINGS_NAVITEMS[2]),
            # NOTE(lloyd): This must always be at the end. Please adjust index accordingly.
            (position_x, (position_y + (3 * offset_y)), font, pg.Color("white"), SETTINGS_NAVITEMS[3]),
        ]

        if pre.DEBUG_GAME_ASSERTS:
            assert (
                (want := MAX_SETTINGS_NAVITEMS, got := len(self.settings))
                and (want == got)
                and f"want settings array length to be {repr(want)}. got {repr(got)}"
            )
            assert (
                (want := "GO BACK", got := self.settings[-1][4])
                and (want == got)
                and f"want the last SettingsScreen navitem to have text {repr(want)}. got {repr(got)}"
            )

        self.movement = pre.Movement(False, False, False, False)
        self.is_key_pressed_key_enter = False

        self.navitem_offset = 0
        self.selected_navitem = SettingsNavitemType.MUTE_MUSIC
        if pre.DEBUG_GAME_ASSERTS:
            assert (
                (want := 0, got := self.selected_navitem)
                and (got == want)
                and f"want selected_navitem to be initialized with the zero value enumeration. got {repr(got)}"
            )
        # ---------------------------------------------------------------------

    def run(self) -> None:
        self.bgcolor = pre.COLOR.BACKGROUND

        loop_counter = 0  # GAME_SLOW=0 :: safety feature
        MAX_LOOP_COUNTER = pre.FPS_CAP * 60  # 60 seconds

        while self.running:
            if loop_counter >= MAX_LOOP_COUNTER:
                self.running = False
            self.clock.tick(pre.FPS_CAP // 2)  # Play at half-speed
            self.events()  # Process events this frame
            self.update()  # Update data this frame
            self.render()  # Draw updated data this frame

            loop_counter += 1

    def events(self):
        # Some event resets
        # ---------------------------------------------------------------------
        # Reset self.movement each frame to avoid navigating on key down at 60fps 0_0
        self.movement = pre.Movement(False, False, False, False)
        self.is_key_pressed_key_enter = False
        # ---------------------------------------------------------------------

        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()
            if event.type == pg.QUIT:
                self.running = False
                quit_exit()
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                # NOTE(Lloyd): See if we need to de-init or unload assets/flags/variables etc
                self.running = False  # Go back to main menu
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

    def update(self):
        # Clear screen and render background
        self.game.display.fill(self.bgcolor)

        # Update movement parameters
        if self.movement.top:
            self.navitem_offset -= 1
        elif self.movement.bottom:
            self.navitem_offset += 1

        # Wrap around negative index for MenuItemType Enumerations
        # ---------------------------------------------------------------------
        if self.navitem_offset < 0:
            self.navitem_offset = MAX_MENU_ITEMS - 1  # Set to last item
        if self.navitem_offset >= MAX_MENU_ITEMS:
            self.navitem_offset = 0  # Set to first item

        assert (
            self.navitem_offset in range(0, MAX_SETTINGS_NAVITEMS)
        ) and f"expected valid offset for menu items while navigating in StartScreen"

        self.selected_navitem = SettingsNavitemType(self.navitem_offset)
        # ---------------------------------------------------------------------

        # Handle settings screen navigation button on press/enter
        # PERF: use left/right for incr/decr music/sound levels
        # ---------------------------------------------------------------------
        if self.is_key_pressed_key_enter:
            match self.selected_navitem:
                case SettingsNavitemType.MUTE_MUSIC:
                    self.game.settings_handler.music_muted = not self.game.settings_handler.music_muted
                    if self.game.settings_handler.music_muted:
                        pg.mixer.music.set_volume(0.0)
                    else:
                        pg.mixer.music.set_volume(0.4)
                case SettingsNavitemType.MUTE_SOUND:
                    self.game.settings_handler.sound_muted = not self.game.settings_handler.sound_muted
                    if self.game.settings_handler.sound_muted:
                        self.game.sfx.dashbassy.set_volume(0)
                        self.game.sfx.hit.set_volume(0)
                        self.game.sfx.hitmisc.set_volume(0)
                        self.game.sfx.hitwall.set_volume(0)
                        self.game.sfx.jump.set_volume(0)
                        self.game.sfx.jumplanding.set_volume(0)
                        self.game.sfx.playerspawn.set_volume(0)
                        self.game.sfx.portaltouch.set_volume(0)
                        self.game.sfx.shoot.set_volume(0)
                        self.game.sfx.teleport.set_volume(0)
                        if self.game.sfx.dash:
                            self.game.sfx.dash.set_volume(0)
                        if self.game.sfx.shootmiss:
                            self.game.sfx.shootmiss.set_volume(0)
                    else:
                        self.game.sfx.dashbassy.set_volume(0.2)
                        self.game.sfx.hit.set_volume(0.2)
                        self.game.sfx.hitmisc.set_volume(0.2)
                        self.game.sfx.hitwall.set_volume(0.2)
                        self.game.sfx.jump.set_volume(0.4)
                        self.game.sfx.jumplanding.set_volume(0.3)
                        self.game.sfx.playerspawn.set_volume(0.2)
                        self.game.sfx.portaltouch.set_volume(0.2)
                        self.game.sfx.shoot.set_volume(0.1)
                        self.game.sfx.teleport.set_volume(0.2)
                        if self.game.sfx.dash:
                            self.game.sfx.dash.set_volume(0.2)
                        if self.game.sfx.shootmiss:
                            self.game.sfx.shootmiss.set_volume(0.2)
                case SettingsNavitemType.DISABLE_SCREENSHAKE:
                    self.game.settings_handler.screenshake = not self.game.settings_handler.screenshake
                case SettingsNavitemType.GO_BACK:
                    self.running = False  # Exit SettingsScreen and return to caller i.e. StartScreen
                case _:  # pyright: ignore [reportUnnecessaryComparison]
                    pass
        # ---------------------------------------------------------------------

    def render(self):
        # Text VFX
        shake_x = (0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0.0
        shake_y = (0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0.0

        # Draw screen name
        # ---------------------------------------------------------------------
        text_xpos: int = int((self.w // 2) + shake_x)
        text_ypos: int = int(69 - shake_y)
        self.game.draw_text(text_xpos, text_ypos, self.FONT_TYPES[FontType.BASE], pg.Color("maroon"), "SETTINGS")
        # ---------------------------------------------------------------------

        # Draw navigation items
        # ---------------------------------------------------------------------
        shake_x = math.floor(shake_x)
        shake_y = math.floor(shake_y)

        for i, option in enumerate(self.settings):
            assert (
                (0 <= self.navitem_offset < MAX_SETTINGS_NAVITEMS)
                and f"want valid navitem offset ranging from {repr(0)}..={repr(MAX_SETTINGS_NAVITEMS-1)}. got {repr( self.navitem_offset )}"
            )
            is_active = (self.navitem_offset == i)  # fmt: skip
            pos_x = (option[0] - shake_x) if is_active else option[0]
            pos_y = (option[1] - shake_y) if is_active else option[1]
            color = pg.Color("maroon")    if is_active else option[3]  # fmt: skip
            text: str
            match SettingsNavitemType(i):
                case SettingsNavitemType.MUTE_MUSIC:
                    text = (option[4] + " OFF") if self.game.settings_handler.music_muted else (option[4] + " ON")
                case SettingsNavitemType.MUTE_SOUND:
                    text = (option[4] + " OFF") if self.game.settings_handler.sound_muted else (option[4] + " ON")
                case SettingsNavitemType.DISABLE_SCREENSHAKE:
                    text = (option[4] + " OFF") if not self.game.settings_handler.screenshake else (option[4] + " ON")
                case SettingsNavitemType.GO_BACK:
                    text = option[4]
                case _:  # pyright: ignore [reportUnnecessaryComparison]
                    msg = f"want valid SettingsNavitemType while drawing text in SettingsScreen. got {repr(SettingsNavitemType(i))} while iterating over item at index {repr(i)}."
                    raise ValueError(msg)

            self.game.draw_text(pos_x, pos_y, self.FONT_TYPES[option[2]], color, text)
        # ---------------------------------------------------------------------

        # DEBUG: HUD
        # ---------------------------------------------------------------------
        if pre.DEBUG_GAME_HUD:
            font = self.FONT_TYPES[0]
            pos_y = 16
            pos_x = 64
            gap_y = 16

            text = f"UP*{1 if self.movement.top else 0} DOWN*{1 if self.movement.bottom else 0}"
            color = pg.Color("cyan")
            self.game.draw_text(pos_x, pos_y, font, color, text)
            pos_y += gap_y

            text = f"LEFT*{1 if self.movement.left else 0} RIGHT*{1 if self.movement.right else 0}"
            self.game.draw_text(pos_x + 10, pos_y, font, color, text)
            pos_y += gap_y

            text = f"NAVITEM OFFSET*{self.navitem_offset}"
            self.game.draw_text(pos_x + 20, pos_y, font, pg.Color("maroon"), text)
            pos_y += gap_y
        # ---------------------------------------------------------------------

        # Draw mask outline for all
        # ---------------------------------------------------------------------
        dispmask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)
        # ---------------------------------------------------------------------

        # Render display
        # ---------------------------------------------------------------------
        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))
        pg.display.flip()


# ------------------------------------------------------------------------------
# GAME START SCREEN (MAIN MENU)
# ------------------------------------------------------------------------------


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
        self.menuitem_offset = 0

        self.clock = pg.time.Clock()  # or use game's clock?
        self.running = True

    # @profile
    def run(self) -> None:
        music_filename = pre.SRC_DATA_PATH / "music" / "level_2.wav"
        # pg.mixer.music.load(music_filename)  # play background music
        pre.load_music_to_mixer(
            music_filename, opts=dict(file_=__file__, line_=pre.get_current_line())
        )  # play background music
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
            if (event.type == pg.KEYDOWN) and (event.key == pg.K_RETURN):
                match self.selected_menuitem:
                    case MenuItemType.PLAY:
                        pg.mixer.music.fadeout(1000)
                        if not self.game.running:
                            set_mainscreen(game=self.game, scr=LoadingScreen(game=self.game, level=self.game.level))
                        else:
                            set_mainscreen(game=self.game, scr=self.game)
                    case MenuItemType.SETTINGS:
                        set_mainscreen(game=self.game, scr=SettingsScreen(game=self.game, level=self.game.level))
                    case MenuItemType.CREDITS:
                        set_mainscreen(game=self.game, scr=CreditsScreen(game=self.game, level=self.game.level))
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
        # Clear screen and render background
        self.game.display.fill(self.bgcolor)

        # Update movement parameters
        # ---------------------------------------------------------------------
        if self.movement.top:
            self.menuitem_offset -= 1
        elif self.movement.bottom:
            self.menuitem_offset += 1
        # ---------------------------------------------------------------------

        # Wrap around negative index for MenuItemType Enumerations
        # ---------------------------------------------------------------------
        if self.menuitem_offset < 0:
            self.menuitem_offset = MAX_MENU_ITEMS - 1  # set to last item
        if self.menuitem_offset >= MAX_MENU_ITEMS:
            self.menuitem_offset = 0  # set to first item

        assert (
            self.menuitem_offset in range(0, MAX_MENU_ITEMS)
        ) and f"expected valid offset for menu items while navigating in StartScreen"

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

        # Draw game logo
        # ---------------------------------------------------------------------
        shake_x = math.floor(0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0
        shake_y = math.floor(0.85 * uniform(-0.618, 0.618)) if random() < 0.1 else 0
        self.game.draw_text((self.w // 2) + shake_x, 50 - shake_y, self.font_base, pg.Color("maroon"), "TIP")
        self.game.draw_text((self.w // 2) - shake_x, 69 + shake_y, self.font_base, pre.WHITE, "TOE")
        # ---------------------------------------------------------------------

        # Draw menu items instructions
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
                assert (
                    (i == self.menuitem_offset)
                    and f"expected exact selected menu item type while rendering in StartScreen. got {i, val, self.selected_menuitem =}"
                )
                self.game.draw_text((pos_x - shake_x), (pos_y - shake_y), self.font_sm, pg.Color("maroon"), val)
            else:
                self.game.draw_text(pos_x, pos_y, self.font_sm, pre.WHITE, f"{val}")
            pos_y += offset_y
        # ---------------------------------------------------------------------

        # Draw instructions
        # ---------------------------------------------------------------------
        if 0:
            self.game.draw_text((self.w // 2), (self.h - 100), self.font_sm, pre.WHITE, "Press enter to start")
        # ---------------------------------------------------------------------

        # Draw mask outline for all
        # ---------------------------------------------------------------------
        dispmask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))

        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)
        # ---------------------------------------------------------------------

        # Render display
        # ---------------------------------------------------------------------
        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))
        pg.display.flip()
        # ---------------------------------------------------------------------


# ------------------------------------------------------------------------------
# GAME LAUNCHER
# ------------------------------------------------------------------------------


class Launcher(Game):
    def __init__(self) -> None:
        super().__init__()

    def start(self) -> None:
        # Some platforms require the pygame.mixerpygame module for loading and
        # playing sounds module to be initialized after the display modules
        # have initialized. The top level pygame.init() takes care of this
        # automatically, but cannot pass any arguments to the mixer init. To
        # solve this, mixer has a function pygame.mixer.pre_init() to set the
        # proper defaults before the toplevel init is used.
        #
        # pygame.mixer.init()
        #   It is safe to call this more than once, but after the mixer is
        #   initialized you cannot change the playback arguments without first
        #   calling pygame.mixer.quit().
        #
        # See reference: https://www.pygame.org/docs/ref/mixer.html#pygame.mixer.init
        pg.mixer.pre_init()

        startscreen = StartScreen(self)
        set_mainscreen(game=self, scr=startscreen)
