# file: tiptoe/src/internal/prelude.py

"""This module contains all the classes, functions and constants used in the
game.
"""


import math
import os
import sys
from dataclasses import dataclass
from enum import Enum, IntEnum, auto, unique
from functools import lru_cache, partial
from pathlib import Path
from random import randint
from time import time
from typing import DefaultDict  # pyright: ignore[reportUnusedImport]
from typing import (
    Any,
    Dict,
    Final,
    Generator,
    NamedTuple,
    Optional,
    Sequence,
    SupportsFloat,
    SupportsIndex,
    Tuple,
    TypeAlias,
    Union,
)

import pygame as pg


################################################################################
### DFLAGS
################################################################################

DDEBUG: Final[bool] = "--debug" in sys.argv

# flags for debugging, etc
DEBUG_EDITOR_ASSERTS = False
DEBUG_EDITOR_HUD = False

DEBUG_GAME_ASSERTS = False
DEBUG_GAME_CACHEINFO = False
DEBUG_GAME_CAMERA = False
DEBUG_GAME_CPROFILE = False
DEBUG_GAME_HUD = False
DEBUG_GAME_LOGGING = False
DEBUG_GAME_PRINTLOG = False
DEBUG_GAME_STRESSTEST = False
DEBUG_GAME_TRACEMALLOC = False
DEBUG_GAME_TRANSITION = False
DEBUG_GAME_UNITTEST = False


################################################################################
### TYPES
################################################################################

"""
(class) TypeAlias
───────────────────────────────────────────────────────────────
Special form for marking type aliases.
"""
Number: TypeAlias = int | float

# This typehint is used when a math function like sin or cos accepts an angle.
# Ported from math.py via typing.py
SupportsFloatOrIndex: TypeAlias = SupportsFloat | SupportsIndex

# This typehint is used when a function would return an RGBA table.
#   Ported from pygame source file: _common.py
RGBAOutput: TypeAlias = Tuple[int, int, int, int]
ColorValue: TypeAlias = (
    pg.Color | Tuple[int, int, int] | RGBAOutput | Sequence[int]
)  # old: ColorValue: TypeAlias = Union[pg.Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]

# Ported from pygame source file: _common.py
Coordinate2: TypeAlias = Tuple[Number, Number] | Sequence[Number] | pg.Vector2

# A = TypeVar("A", pg.Vector2, tuple[float, float])
# Vec2Type: TypeAlias = pg.Vector2 | tuple[float, float] # @Unused


class ColorKind(NamedTuple):
    """
    Examples::

        >>> ColorKind(255, 255, 255)
        ColorKind(r=255, g=255, b=255)
    """

    r: int
    g: int
    b: int


@dataclass
class Projectile:
    """
    Examples::

        >>> Projectile((0, 0), 2, 12)
        Projectile(pos=(0, 0), velocity=2, timer=12)
    """

    pos: pg.Vector2  # [x, y]
    velocity: Number  # directional velocity : left (-ve) : right (+ve)
    timer: int  # frame timer


@unique
class ParticleKind(Enum):
    """used for class AnimationMiscAssets"""

    FLAME = "flame"
    FLAMEGLOW = "flameglow"
    PARTICLE = "particle"
    """Player dash particle"""


# @unique
class EntityKind(Enum):
    ENEMY = "enemy"
    PLAYER = "player"
    PORTAL = "portal"


@unique  # """Class decorator for enumerations ensuring unique member values."""
class TileKind(Enum):
    BOUNCEPAD = "bouncepad"
    DECOR = "decor"
    GRANITE = "granite"
    GRASS = "grass"
    GRASSPLATFORM = "grassplatform"
    GRASSPILLAR = "grasspillar"
    LARGE_DECOR = "large_decor"
    PORTAL = "portal"
    SPAWNERS = "spawners"
    SPIKE = "spike"
    STONE = "stone"


@unique  # """Class decorator for enumerations ensuring unique member values."""
class SpawnerKind(Enum):
    """Enumerates the spawners that are used in the level editor.

    Note ideally start with 1 (as 0 may be assumed as False) but we used 0,1,2
    as variants for spawner 'tiles' while drawing the map.json via level editor
    in src/editor.py for the sake of the wrapping around all spawner variants,
    e.g. 0 1 2 0 1 2 ..... or it.cycle(...)

    Examples::
        >>> SpawnerKind.PLAYER.value
        0
        >>> SpawnerKind.PLAYER
        <SpawnerKind.PLAYER: 0>

        >>> SpawnerKind.as_entity(SpawnerKind, EntityKind.PLAYER)
        <SpawnerKind.PLAYER: 0>
    """

    PLAYER = 0
    ENEMY = 1
    PORTAL = 2

    def as_entity(self, entity_kind: EntityKind):
        match entity_kind:
            case EntityKind.PLAYER:
                return self.PLAYER
            case EntityKind.ENEMY:
                return self.ENEMY
            case EntityKind.PORTAL:
                return self.PORTAL
            case _:  # pyright: ignore[reportUnnecessaryComparison]
                raise ValueError('not implemented yet or invalid entity kind')


@dataclass
class Movement:
    """Movement is a dataclass of 4 booleans for each of the 4 cardinal
    directions where movement is possible. Note: False == 0 and True == 1

    Examples::

        >>> Movement(True, False, True, False)
        Movement(left=True, right=False, top=True, bottom=False)
    """

    left: bool
    right: bool
    top: bool
    bottom: bool


@dataclass
class Collisions:
    """Collisions is a dataclass of 4 booleans for each of the 4 cardinal
    directions where collisions are possible. Note: False == 0 and True == 1

    Examples::

        >>> Collisions(True, False, True, False)
        Collisions(left=True, right=False, up=True, down=False)
    """

    left: bool
    right: bool
    up: bool
    down: bool


################################################################################
### UTILS
################################################################################


def clamp(value: int | float, lo: int | float, hi: int | float) -> int | float:
    """
    Examples::

        >>> (clamp(15, 3, 11), clamp(5, 3, 11), clamp(-15, 3, 11))
        (11, 5, 3)

        >>> (clamp(float("-inf"), 3, 11), clamp(float("inf"), 3, 11))
        (3, 11)
    """
    return min(max(value, lo), hi)


################################################################################
### ANIMATION
################################################################################


class Motion:
    @staticmethod
    def lerp(a: Number, b: Number, t: float) -> float:
        """
        Examples::

            >>> Motion.lerp(0, 10, 0.5)
            5.0
            >>> Motion.lerp(-20, 20, 0.25)
            -10.0
        """
        return a + t * (b - a)

    @lru_cache
    @staticmethod
    def pan_smooth(value: int | float, target: int, smoothness: int | float = 1) -> int | float:
        """
        Examples::

            >>> value, target, smoothness = 123, 321, 0.5
            >>> Motion.pan_smooth(value, target, smoothness)
            123.0
            >>> value
            123

        """
        smoothness = 1 if (smoothness == 0) else smoothness
        value += (target - value) / smoothness * min(pg.time.get_ticks() * 0.001, smoothness)
        return value


class Animation:
    """Animation is a class that holds a list of images and a duration for each
    image to be displayed.

    Example::

        animation = Animation([image1, image2, image3], img_dur=5)

    Note: if img_dur is not specified then it defaults to 5
    Note: if loop is not specified then it defaults to True
    """

    def __init__(self, images: list[pg.Surface], img_dur: int = 5, loop: bool = True) -> None:
        self.images: Final[list[pg.Surface]] = images  # this is not copied
        self.loop = loop
        self._img_duration: Final = img_dur

        self._img_duration_inverse: Final = 1 / self._img_duration  # perf:minor
        self._total_frames: Final = self._img_duration * len(self.images)

        self.done = False  # fixed: should always be False at __init__

        self.frame = 0

    def copy(self) -> "Animation":
        """Return a copy of the animation."""
        return Animation(self.images, self._img_duration, self.loop)

    def update(self) -> None:
        """Increment frames like a movie screen roll or a marque."""
        if self.loop:
            self.frame += 1
            self.frame %= self._total_frames
        else:
            self.frame = min(self.frame + 1, self._total_frames - 1)
            if self.frame >= self._total_frames - 1:
                self.done = True

    def img(self) -> pg.SurfaceType:
        """Returns current image to render in animation cycle.

        Similar to render phase in the '__init__ -> update -> render' cycle"""
        return self.images[int(self.frame * self._img_duration_inverse)]


################################################################################
### FILE I/O
################################################################################


TFilesVisitedOpts = Dict[str, (int | Any | None)]
TFilesVisitedDict = Dict[int, Tuple[float, (str | Path), str]]

global_files_visited: TFilesVisitedDict = dict()


import inspect


def get_current_line() -> int | Any | None:
    if (caller_frame := inspect.currentframe()) and caller_frame:
        if (f_back := caller_frame.f_back) and f_back:
            return f_back.f_lineno
    return None


def global_files_visited_update(path: str | Path, opts: Optional[TFilesVisitedOpts] = None) -> int | None:
    if "--debug" in sys.argv:
        count = len(global_files_visited.items())
        global_files_visited.update({count: (time(), path, f"{opts}" if opts else f"{opts=}")})
        return count + 1
    return None


_callable_sound = pg.mixer.Sound


def load_sound(path: Path, opts: Optional[TFilesVisitedOpts] = None) -> pg.mixer.Sound:
    global_files_visited_update(path, opts=(opts if opts else dict(file_=__file__, line_=get_current_line())))
    return _callable_sound(path)  # > Callable[Sound]


_callable_music_load = pg.mixer.music.load


def load_music_to_mixer(path: Path, opts: Optional[TFilesVisitedOpts] = None) -> None:
    global_files_visited_update(path, (opts if opts else dict(file_=__file__, line_=get_current_line())))
    return _callable_music_load(path)  # > None


# FIXME: Cannot test it due to error:
#   pygame.error: No video mode has been set
# CANFIX: Add a param flag to avoid converting the image after load....
def load_img(path: str | Path, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None) -> pg.Surface:
    """Load and return a pygame Surface image.
    Note: Ported from DaFluffyPotato's pygpen lib

    Errors::
        Throws if No video mode has been set before calling this function.
        Ensure the following is called prior load_img(...)

        >>> import pygame as pg
        >>> display_flag = pg.DOUBLEBUF | pg.RESIZABLE | pg.NOFRAME | pg.HWSURFACE  # BITFLAGS
        >>> screen = pg.display.set_mode(size=(960, 630), flags=display_flag)
        >>> isinstance(screen, pg.SurfaceType)
        True
    """
    path = Path(path)
    global_files_visited_update(path, opts=dict(file_=__file__, line_=get_current_line()))
    img = pg.image.load(path).convert_alpha() if with_alpha else pg.image.load(path).convert()
    if colorkey is not None:
        img.set_colorkey(colorkey)
    return img


def load_imgs(
    path: str, with_alpha: bool = False, colorkey: Union[tuple[int, int, int], None] = None
) -> list[pg.Surface]:
    """Lists all image filenames in path directory and loads_img over each and
    returns list of pg.Surfaces.

    Example::

        ```python
        load_imgs(path=os.path.join(IMAGES_PATH, "tiles", "grass"), with_alpha=True, colorkey=BLACK)
        ```
    """
    return [
        load_img(f"{path}/{img_name}", with_alpha, colorkey)
        for img_name in sorted(os.listdir(path))
        if img_name.endswith(".png")
    ]


@dataclass
class UserConfig:
    """Configuration options for the game application.

    Usage::

        ```python
        def get_user_config(filepath: Path) -> AppConfig:
            config: Optional[dict[str, str]] = AppConfig.read_user_config(filepath=filepath)
            if not config:
                print("error while reading configuration file at", repr(filepath))
                return AppConfig.from_dict({})
            return AppConfig.from_dict(config)
        ```
    """

    blur_enabled: bool
    blur_passes: int
    blur_size: int
    blur_vibrancy: float
    col_shadow: str
    drop_shadow: bool
    enemy_jump: int
    enemy_speed: int
    music_muted: bool
    music_volume: float
    player_dash: int
    player_jump: int
    player_speed: int
    screenshake: bool
    shadow_range: int
    sound_muted: bool
    sound_volume: float
    star_count: int
    window_height: int
    window_width: int

    @classmethod
    def from_dict(cls, config_dict: dict[str, str]):
        """Create an AppConfig instance from a dictionary.

        Handles converting string values to appropriate data types and setting
        defaults for missing keys.

        Example::

            ```python
            config = AppConfig.from_dict(config_dict)
            ```

        Args:
            config_dict: dict[str, str]

        Returns:
            AppConfig

        Raises:
            ValueError if config_dict is not valid
        """
        # if not all(key in config_dict for key in cls.__annotations__):
        #     raise ValueError("invalid config_dict")
        return cls(
            blur_enabled=config_dict.get('blur_enabled', 'false').lower() == 'true',
            blur_passes=int(config_dict.get('blur_passes', '1')),
            blur_size=int(config_dict.get('blur_size', '3')),
            blur_vibrancy=float(config_dict.get('blur_vibrancy', '0.0')),
            col_shadow=config_dict.get('col_shadow', '000000'),
            drop_shadow=config_dict.get('drop_shadow', 'false').lower() == 'true',
            enemy_jump=int(config_dict.get('enemy_jump', '0')),
            enemy_speed=int(config_dict.get('enemy_speed', '0')),
            music_muted=config_dict.get('music_muted', 'false').lower() == 'true',
            music_volume=float(config_dict.get('music_volume', '0.0')),
            player_dash=int(config_dict.get('player_dash', '0')),
            player_jump=int(config_dict.get('player_jump', '0')),
            player_speed=int(config_dict.get('player_speed', '0')),
            screenshake=config_dict.get('screenshake', 'true').lower() == 'true',
            shadow_range=int(config_dict.get('shadow_range', '1')),
            sound_muted=config_dict.get('sound_muted', 'false').lower() == 'true',
            sound_volume=float(config_dict.get('sound_volume', '0.0')),
            star_count=int(config_dict.get('star_count', '0')),
            window_height=int(config_dict.get('window_height', '480')),
            window_width=int(config_dict.get('window_width', '640')),
        )

    @staticmethod
    def read_user_config(filepath: Path) -> Optional[dict[str, str]]:
        """Read configuration file and return a dictionary.

        Skips comments, empty lines, and returns None if file doesn't exist.
        """
        if not filepath.is_file():
            print(f"error while locating file at {repr(filepath)}")
            return None

        if DEBUG_GAME_PRINTLOG:
            print(f"reading configuration file at {repr(filepath)}")

        global_files_visited_update(filepath, opts=dict(file_=__file__, line_=get_current_line()))
        with open(filepath, "r") as f:
            return {
                k: v for line in f if (l := line.strip()) and not l.startswith("#") for k, v in [l.split(maxsplit=1)]
            }


##########
# COLORS #


@lru_cache(maxsize=32)
def hex_to_rgb(s: str) -> tuple[int, int, int]:
    """Convert hex color code to RGB color code.

    Args:
        s: hex color code

    Returns:
        tuple[int, int, int]

    Examples::

        >>> assert hex_to_rgb("#ff0000") == (255, 0, 0)
        >>> assert hex_to_rgb("#00ff00") == (0, 255, 0)
        >>> assert hex_to_rgb("#0000ff") == (0, 0, 255)
    """
    base: Final = 16
    if (n := len(s)) == 7:
        if s[0] == "#":
            s = s[1:]
            if DEBUG_GAME_ASSERTS:
                assert len(s) == (n - 1), "invalid hexadecimal format"  # Lua: assert(hex_string:sub(2):find("^%x+$"),
        else:
            raise ValueError(f"want valid hex format string. got {s}")
    return (int(s[0:2], base), int(s[2:4], base), int(s[4:6], base))


# Sat Apr 27 11:15:24 AM IST 2024
#  pre.hsl_to_rgb.cache_info() = CacheInfo(hits=2884, misses=516, maxsize=1024, currsize=516)
@lru_cache(maxsize=1024)
def hsl_to_rgb(h: int, s: float, l: float) -> ColorKind:
    """Convert hsl to rgb color value.

    Args:
        h: hue
        s: saturation
        l: lightness

    Returns:
        tuple[int, int, int]

    Raises:
        ValueError if h, s, l is not valid

    Constraints:
        0 ≤ h < 360 and 0.0 ≤ s ≤ 1.0 and 0.0 ≤ l ≤ 1.0

    Examples::

        >>> assert hsl_to_rgb(0, 0, 0) == (0, 0, 0)             # black
        >>> assert hsl_to_rgb(0, 0, 1) == (255, 255, 255)       # white
        >>> assert hsl_to_rgb(0, 1, 0.5) == (255, 0, 0)         # red
        >>> assert hsl_to_rgb(120, 1, 0.5) == (0, 255, 0)       # lime green
        >>> assert hsl_to_rgb(240, 1, 0.5) == (0, 0, 255)       # blue
        >>> assert hsl_to_rgb(60, 1, 0.5) == (255, 255, 0)      # yellow
        >>> assert hsl_to_rgb(180, 1, 0.5) == (0, 255, 255)     # cyan
        >>> assert hsl_to_rgb(300, 1, 0.5) == (255, 0, 255)     # magenta
        >>> assert hsl_to_rgb(0, 0, 0.75) == (191, 191, 191)    # silver
        >>> assert hsl_to_rgb(0, 0, 0.5) == (128, 128, 128)     # gray
        >>> assert hsl_to_rgb(0, 1, 0.25) == (128, 0, 0)        # maroon
        >>> assert hsl_to_rgb(60, 1, 0.25) == (128, 128, 0)     # olive
        >>> assert hsl_to_rgb(120, 1, 0.25) == (0, 128, 0)      # green
        >>> assert hsl_to_rgb(300, 1, 0.25) == (128, 0, 128)    # purple
        >>> assert hsl_to_rgb(180, 1, 0.25) == (0, 128, 128)    # teal
        >>> assert hsl_to_rgb(240, 1, 0.25) == (0, 0, 128)      # navy
    """
    if DEBUG_GAME_ASSERTS:
        assert 0 <= h <= 360
        assert 0 <= s <= 1
        assert 0 <= l <= 1
    # calculate C, X, and m
    c: Final[float] = (1 - abs((2 * l) - 1)) * s
    x: Final[float] = c * (1 - abs(((h / 60) % 2) - 1))
    m: Final[float] = l - (c / 2)
    r_prime: float
    g_prime: float
    b_prime: float
    # sector mapping: determine which sector of the hue circle the color is in
    match (h // 60) % 6:
        case 0:
            r_prime, g_prime, b_prime = c, x, 0.0
        case 1:
            r_prime, g_prime, b_prime = x, c, 0.0
        case 2:
            r_prime, g_prime, b_prime = 0.0, c, x
        case 3:
            r_prime, g_prime, b_prime = 0.0, x, c
        case 4:
            r_prime, g_prime, b_prime = x, 0.0, c
        case _:  # default
            r_prime, g_prime, b_prime = c, 0.0, x
    # convert to 0-255 scale, note: round() instead of int() helps in precision. e.g. gray 127 -> 128
    return ColorKind(round((r_prime + m) * 255), round((g_prime + m) * 255), round((b_prime + m) * 255))


#############
# CONSTANTS #

FPS_CAP = 60
"""Frames per seconds.

FPS of 60 == 16 milliseconds per frame
1000ms / FPS = ms per frame.
If it takes longer than 16 ms to render a frame, game slows down.
"""

CAMERA_SPEED = 2  # use with editor camera move fast around the world
RENDER_SCALE = 2  # for editor
SCALE = 0.5
TILE_SIZE = 16

SCREEN_RESOLUTIONS = (
    # ===---32/21---=== #
    (960, 630),
    # ===----4/3----=== #
    (640, 480),
    (1280, 960),
    (960, 720),
    (320, 240),
    # ===---16/9----=== #
    (640, 360),
    (384, 216),
    (320, 180),
)  # (width, height)

SCREEN_RESOLUTION_MODE = 0
SCREEN_WIDTH, SCREEN_HEIGHT = SCREEN_RESOLUTIONS[SCREEN_RESOLUTION_MODE]


# 32/21, 4/3, 16/9, 16/9
def _test__screen__dimensions():
    from fractions import Fraction as _F

    f0 = _F(960, 630)
    assert (f0.numerator, f0.denominator) == (32, 21)


if DEBUG_GAME_ASSERTS:
    _test__screen__dimensions()


DIMENSIONS = (SCREEN_WIDTH, SCREEN_HEIGHT)  # ratio: (4/3) or (1.3333333333333333)
DIMENSIONS_HALF = (int(SCREEN_WIDTH * SCALE), int(SCREEN_HEIGHT * SCALE))

CAPTION = "tiptoe"
CAPTION_EDITOR = "tiptoe level editor"

SRC_PATH = Path("src")

SRC_DATA_PATH = SRC_PATH / "data"

SRC_DATA_IMAGES_PATH = SRC_DATA_PATH / "images"
SRC_DATA_MAP_PATH = SRC_DATA_PATH / "maps"

SRC_DATA_IMAGES_ENTITIES_PATH = SRC_DATA_IMAGES_PATH / "entities"

# aliases for directory paths
CONFIG_PATH = SRC_PATH / "config"
ENTITY_PATH = SRC_DATA_IMAGES_ENTITIES_PATH
FONT_PATH = SRC_DATA_PATH / "font"
IMGS_PATH = SRC_DATA_IMAGES_PATH
INPUTSTATE_PATH = None
MAP_PATH = SRC_DATA_MAP_PATH
SFX_PATH = SRC_DATA_PATH / "sfx"
SPRITESHEET_PATH = None

# colors:
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

BLUE = (0, 0, 255)
BLUEGLOW = hsl_to_rgb(220, 0.618, 0.618) or (10, 10, 180)
CHARCOAL = (10, 10, 10)
DARKCHARCOAL = (5, 5, 5)
GREEN = (0, 255, 0) or hsl_to_rgb(120, 1, 0.25)
GREENBLURB = (20, 222, 20) or hsl_to_rgb(120, 1, 0.25)
GREENGLOW = (20, 127, 20) or hsl_to_rgb(120, 1, 0.25)
PINK = hsl_to_rgb(300, 0.36, 0.38)
PURPLEBLURB = hsl_to_rgb(220, 0.6, 0.6) or (255, 0, 0)
PURPLEGLOW = hsl_to_rgb(220, 0.75, 0.6) or (255, 0, 0)
RED = (255, 0, 0) or hsl_to_rgb(0, 0.618, 0.328)

TRANSPARENT = (0, 0, 0, 0)


@dataclass
class Palette:
    """Color Palette.

    GIMP Palette
    #Palette Name: Rust Gold 8
    #Description: This palette was made based on rust colors and gold tones.
    #Colors: 8
    """

    COLOR0 = 246, 205, 38  # f6cd26
    COLOR1 = 172, 107, 38  # ac6b26
    COLOR2 = 86, 50, 38  # 563226
    COLOR3 = 51, 28, 23  # 331c17
    COLOR4 = 187, 127, 87  # bb7f57
    COLOR5 = 114, 89, 86  # 725956
    COLOR6 = 57, 57, 57  # 393939
    COLOR7 = 32, 32, 32  # 202020


# https://lospec.com/palette-list/baba-is-you-default-color
# 080808
# 0b0a0f
# 242424
# 737373
# c3c3c3
# ffffff
# 15181f
# 293040
# 3e7687
# 5f9dd0
# 83c9e5
# 411910
# 82261b
# e5533a
# e39950
# 692e4c
# 8e5e9c
# 4e5a94
# 9183d8
# d9386a
# ea91c9
# 303823
# 4c5c1d
# 5d833a
# a4b13e
# 362e23
# 503f25
# 91673f
# c29e46


@dataclass
class COLOR:
    TRANSPARENTGLOW = (20, 20, 20)

    BACKGROUND = (12, 12, 14) or Palette.COLOR7
    STAR = (200, 200, 200) or PINK or Palette.COLOR3

    FLAME = Palette.COLOR0
    FLAMEGLOW = Palette.COLOR0
    FLAMETORCH = Palette.COLOR3

    ENEMY = Palette.COLOR5
    ENEMYSLEEPING = Palette.COLOR7
    GUN = Palette.COLOR1

    PLAYER = Palette.COLOR4
    PLAYERIDLE = Palette.COLOR4
    PLAYERJUMP = Palette.COLOR4
    PLAYERRUN = Palette.COLOR4
    PLAYERSTAR = Palette.COLOR0

    PORTAL1 = Palette.COLOR0
    PORTAL2 = Palette.COLOR4

    GRANITE = Palette.COLOR7
    STONE = Palette.COLOR6
    SPIKE = (145, 145, 145) or Palette.COLOR1


@dataclass
class COUNT:
    STAR = TILE_SIZE or 16
    FLAMEGLOW = 18 // 2
    FLAMEPARTICLE = 18 // 2
    # FLAMEPARTICLE   = (TILE_SIZE or 16)


@dataclass
class COUNTRANDOMFRAMES:
    """Random frame count to start on."""

    FLAMEGLOW = randint(0, 20)  # (0,20) OG or (36,64)
    FLAMEPARTICLE = randint(0, 20)  # (0,20) OG or (36,64)


@dataclass
class SIZE:
    ENEMY = (9, TILE_SIZE)  # (9, 16)
    PLAYER = (9, TILE_SIZE)  # (9, 16)

    FLAMEPARTICLE = (5, 5)
    FLAMETORCH = (4, 12)
    GUN = (7, 4)
    # STAR = int((69 / 1.618) ** 0.328), int((69 / 1.618) ** 0.328)  # 3.425, 3.425 -> 3, 3
    STAR = (2, 2)

    # Constants derived from above
    ENEMYJUMP = (ENEMY[0], ENEMY[1] - 1)
    FLAMEGLOWPARTICLE = (2, 2)
    PLAYERIDLE = (PLAYER[0] + 1, PLAYER[1] - 1)
    PLAYERJUMP = (PLAYER[0] - 1, PLAYER[1])
    PLAYERRUN = (PLAYER[0] + 1, PLAYER[1] - 1)
    PLAYERSTARDASHRADIUS = STAR or (int(PLAYER[0] - STAR[0] - 1), int(PLAYER[1] - STAR[1]))
    PORTAL = (max(5, round(PLAYER[0] * 1.618)), max(18, round(TILE_SIZE + 2)))


NEIGHBOR_OFFSETS = {(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)}
N_NEIGHBOR_OFFSETS = 9


AUTOTILE_TYPES = {TileKind.STONE, TileKind.GRANITE, TileKind.GRASS}
AUTOTILE_HORIZONTAL_TYPES = {TileKind.GRASSPLATFORM}
AUTOTILE_VERTICAL_TYPES = {TileKind.GRASSPILLAR}

PHYSICS_TILES = {TileKind.STONE, TileKind.GRANITE, TileKind.GRASS, TileKind.GRASSPLATFORM, TileKind.GRASSPILLAR}

SPAWNERS_KINDS = {EntityKind.PLAYER, EntityKind.ENEMY, TileKind.PORTAL}  # not used for now


################################################################################
### AUTOTILING
################################################################################


@unique
class AutotileMatrixID(IntEnum):
    """Key ID via `AutoTileVariant` for `AUTOTILE_MAP`

    For example::

        assert list(range(0, 8 + 1)) is [x.value for x in AutoTileVariant]

    (constant) AUTOTILE_MAP

    offsets::

        [ (-1,-1) ( 0,-1) ( 1,-1 )
          (-1, 0) ( 0, 0) ( 1, 0 )
          (-1, 1) ( 0, 1) ( 1, 1 ) ]

    tiles::

        { 0   1   2
          7   8   3
          6   5   4 }
    """

    TOPLEFT = auto(0)  # 0
    TOPCENTER = auto()  # 1
    TOPRIGHT = auto()  # 2
    MIDDLERIGHT = auto()  # 3
    BOTTOMRIGHT = auto()  # 4
    BOTTOMCENTER = auto()  # 5
    BOTTOMLEFT = auto()  # 6
    MIDDLELEFT = auto()  # 7
    MIDDLECENTER = auto()  # 8


AUTOTILE_MAP = {
    tuple(sorted([(1, 0), (0, 1)])): AutotileMatrixID.TOPLEFT or 0,  # ES
    tuple(sorted([(1, 0), (0, 1), (-1, 0)])): AutotileMatrixID.TOPCENTER or 1,  # ESW
    tuple(sorted([(-1, 0), (0, 1)])): AutotileMatrixID.TOPRIGHT or 2,  # WS
    tuple(sorted([(-1, 0), (0, -1), (0, 1)])): AutotileMatrixID.MIDDLERIGHT or 3,  # WSN
    tuple(sorted([(-1, 0), (0, -1)])): AutotileMatrixID.BOTTOMRIGHT or 4,  # WN
    tuple(sorted([(-1, 0), (0, -1), (1, 0)])): AutotileMatrixID.BOTTOMCENTER or 5,  # WNE
    tuple(sorted([(1, 0), (0, -1)])): AutotileMatrixID.BOTTOMLEFT or 6,  # EN
    tuple(sorted([(1, 0), (0, -1), (0, 1)])): AutotileMatrixID.MIDDLELEFT or 7,  # ENS
    tuple(sorted([(1, 0), (-1, 0), (0, 1), (0, -1)])): AutotileMatrixID.MIDDLECENTER or 8,  # EWSN
}
"""Coordinates for a minimum 9 cell or 6 cell similar tiles in contact with each other.

Example::
offsets::

    [ (-1,-1) ( 0,-1) ( 1,-1 )
      (-1, 0) ( 0, 0) ( 1, 0 )
      (-1, 1) ( 0, 1) ( 1, 1 ) ]

tiles::

    { 0   1   2
      7   8   3
      6   5   4 }
"""

AUTOTILE_HORIZONTAL_MAP = {
    tuple(sorted([(1, 0)])): AutotileMatrixID.TOPLEFT or 0,  # ES
    tuple(sorted([(1, 0), (-1, 0)])): AutotileMatrixID.TOPCENTER or 1,  # ESW
    tuple(sorted([(-1, 0)])): AutotileMatrixID.TOPRIGHT or 2,  # WS
}
"""Coordinates for a platform with only tiles in sequence without any similar tile above or below them.

Example::

    Number is variant value
    ```txt
    #####
    00000

    #####
    01112
    ```
"""

AUTOTILE_VERTICAL_MAP = {
    tuple(sorted([(0, 1)])): 0,
    tuple(sorted([(0, -1), (0, 1)])): 1,
    tuple(sorted([(0, -1)])): 2,
}

################################################################################
### SPIKE NON-PHYSICS TILE HITBOX TILING
################################################################################

# Global constant for spike configurations
SPIKE_CONFIGURATIONS = [
    {'position': (0, 10), 'size': (16, 6), 'orientation': 'bottom'},
    {'position': (0, 0), 'size': (16, 6), 'orientation': 'top'},
    {'position': (0, 0), 'size': (6, 16), 'orientation': 'left'},
    {'position': (10, 0), 'size': (6, 16), 'orientation': 'right'},
]

################################################################################
### MATH
################################################################################


class Math:
    """Collection of utility functions for mathematical operations."""

    @staticmethod
    def advance_vec2_ip(vec2: pg.Vector2, angle: SupportsFloatOrIndex, amount: Number) -> None:
        """Advances a 2D vector (pg.Vector2) by a given angle and amount in place.

        Args:
            vec2: The pg.Vector2 object representing the 2D vector to advance.
            angle: The angle in radians to move the vector.
            amount: The distance to move the vector along the specified angle.

        This function modifies the `vec2` object in-place and returns None.

        Examples::

            >>> import pygame
            >>> vec2, angle, amount = pygame.Vector2(2, 4), 0, 10
            >>> assert Math.advance_vec2_ip(vec2, angle, amount) is None
            >>> vec2
            <Vector2(12, 4)>
        """
        vec2 += (math.cos(angle) * amount, math.sin(angle) * amount)


################################################################################
### SURFACE PYGAME
################################################################################


def surfaces_get_outline_mask_from_surf(
    surf: pg.SurfaceType, color: ColorValue | ColorKind, width: int, loc: tuple[int, int]
):
    """Create thick outer outlines for surface using masks."""
    m = pg.mask.from_surface(surf)
    m_outline: list[tuple[int, int]] = m.outline()

    for i, point in enumerate(m_outline):
        m_outline[i] = (point[0] + loc[0], point[1] + loc[1])

    outlinesurf = surf.copy().convert()
    outlinesurf.fill(TRANSPARENT)
    pg.draw.polygon(outlinesurf, color, m_outline, width=width)
    return outlinesurf


def surfaces_vfx_outline_offsets_animation_frames(
    surf: pg.SurfaceType,
    color: ColorKind | ColorValue = (255, 255, 255),
    width: int = 1,
    iterations: int = 32,
    offsets: set[tuple[int, int]] = NEIGHBOR_OFFSETS,  # pyright: ignore
):
    """Returns a Generator for a sequence of surfaces snake chasing it's tail
    effect in clockwise motion.
    """
    return (
        surfaces_get_outline_mask_from_surf(surf=surf, color=color, width=width, loc=(ofst))
        for _ in range(iterations)
        for ofst in offsets
    )


def surfaces_collidepoint(pos: pg.Vector2, sprites: Sequence[pg.SurfaceType]):
    """Get a iterable generator of all surfaces that contain a point (x,y).
    Source: https://www.pygame.org/docs/tut/newbieguide.html
    """
    return (s for s in sprites if s.get_rect().collidepoint(pos))


def rects_collidepoint(pos: pg.Vector2, sprites: Sequence[pg.Rect]):
    """Get a iterable generator of all rects that contain a point (x,y).
    Source: https://www.pygame.org/docs/tut/newbieguide.html
    """
    return (s for s in sprites if s.collidepoint(pos))


def create_surface(
    size: tuple[int, int], colorkey: tuple[int, int, int] | ColorValue, fill_color: tuple[int, int, int] | ColorValue
) -> pg.SurfaceType:
    surf = pg.Surface(size).convert()
    surf.set_colorkey(colorkey)
    surf.fill(fill_color)
    return surf


create_surface_partialfn = partial(create_surface, colorkey=BLACK)
create_surface_partialfn.__doc__ = """\
New create_surface function with partial application of colorkey argument and or other keywords.

(function) def create_surface(
    size: tuple[int, int], colorkey: tuple[int, int, int] | ColorValue, fill_color: tuple[int, int, int]
) -> pg.SurfaceType

Parameters:

    size: tuple[int, int],
    colorkey: ColorValue,
    fill_color: ColorValue


Returns:

    pg.SurfaceType
"""


def create_surface_withalpha(
    size: tuple[int, int],
    colorkey: tuple[int, int, int] | ColorValue,
    fill_color: tuple[int, int, int] | ColorValue,
    alpha: int,
) -> pg.SurfaceType:
    surf = pg.Surface(size).convert_alpha()
    surf.set_colorkey(colorkey)
    surf.fill(fill_color)
    surf.set_alpha(alpha)
    return surf


create_surface_withalpha_partialfn = partial(create_surface_withalpha, colorkey=BLACK)
create_surface_withalpha_partialfn.__doc__ = """\
(function) def create_surface_withalpha
    size: tuple[int, int], colorkey: tuple[int, int, int] | ColorValue, fill_color: tuple[int, int, int], alpha: int
) -> pg.SurfaceType

New create_surface_withalpha function with partial application of colorkey argument and or other keywords.
"""


def create_surfaces(
    count: int,
    fill_color: ColorKind | ColorValue | tuple[int, int, int] = BLACK,
    size: tuple[int, int] = (TILE_SIZE, TILE_SIZE),
    colorkey: ColorValue = BLACK,
) -> Generator[pg.SurfaceType, None, None]:
    if colorkey:
        return (create_surface(size, colorkey, fill_color) for _ in range(count))
    return (create_surface_partialfn(size, fill_color) for _ in range(count))


create_surfaces_partialfn = partial(create_surfaces, colorkey=BLACK)
create_surfaces_partialfn.__doc__ = (
    """New create_surfaces function with partial application of colorkey argument and or other keywords."""
)


def create_circle_surf(size: tuple[int, int], fill_color: ColorValue, colorkey: ColorValue = BLACK) -> pg.SurfaceType:
    """Special case for flameglow particle and should not be used here for
    general circle creation.
    """
    surf = pg.Surface(size).convert()
    ca, cb = iter(size)
    center = ca * 0.5, cb * 0.5
    radius = center[0]
    pg.draw.circle(surf, fill_color, center, radius)
    surf.set_colorkey(colorkey)
    return surf


create_circle_surf_partialfn = partial(create_circle_surf, colorkey=BLACK)
create_circle_surf_partialfn.__doc__ = (
    """New create_circle_surf_partialfn function with partial application of colorkey argument and or other keywords."""
)

if __name__ == "__main__":
    import doctest

    doctest.testmod()
