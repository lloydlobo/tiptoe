"""This module implements general purpose utilities, helpers, constants, flags,
providing project specific alternatives to Python's general purpose built-in
library.

* Animation                 class
* AutotileID                class
* COLOR                     class
* COUNT                     class
* COUNTRANDOMFRAMES         class
* Collisions                class
* ConfigHandler             class
* EntityKind                class
* Math                      class
* Movement                  class
* ParticleKind              class
* Projectile                class
* SpawnerKind               class
* TileKind                  class
* UserConfig                class
* create_circle_surf        function
* create_surface            function
* create_surface_withalpha  function
* create_surfaces           function
* hex_to_rgb                function
* hsl_to_rgb                function
* load_img                  function
* load_imgs                 function
* rects_collidepoint        function
* surfaces_collidepoint     function
"""

__all__ = [
    # class
    "Animation",
    "AutotileID",
    "COLOR",
    "COUNT",
    "COUNTRANDOMFRAMES",
    "Collisions",
    "ConfigHandler",
    "EntityKind",
    "Math",
    "Movement",
    "ParticleKind",
    "Projectile",
    "SpawnerKind",
    "TileKind",
    "UserConfig",
    # function
    "create_circle_surf",
    "create_surface",
    "create_surface_withalpha",
    "create_surfaces",
    "hex_to_rgb",
    "hsl_to_rgb",
    "load_img",
    "load_imgs",
    "rects_collidepoint",
    "surfaces_collidepoint",
]


import itertools as it
import math
import os
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum, IntEnum, auto, unique
from functools import lru_cache, partial, reduce
from pathlib import Path
from pprint import pprint
from random import randint
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    Generator,
    NamedTuple,
    NoReturn,
    Optional,
    Protocol,
    Sequence,
    SupportsFloat,
    SupportsIndex,
    Tuple,
    TypeAlias,
    TypeVar,
    Union,
)

import _collections_abc
import pygame as pg
import toml


################################################################################
### TYPES
################################################################################

# This typehint is used when a math function like sin or cos accepts an angle.
# Ported from math.py via typing.py
SupportsFloatOrIndex: TypeAlias = SupportsFloat | SupportsIndex

# This typehint is used when a function would return an RGBA table.
# Ported from pygame source file: _common.py
RGBAOutput = Tuple[int, int, int, int]
ColorValue = Union[pg.Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]


# Ported from pygame source file: _common.py
Coordinate = Union[Tuple[float, float], Sequence[float], pg.Vector2]
Vec2Type = pg.Vector2 | tuple[float, float]  # A = TypeVar("A", pg.Vector2, tuple[float, float])

Number = int | float


class ColorKind(NamedTuple):
    r: int
    g: int
    b: int


@dataclass
class Projectile:
    pos: pg.Vector2  # [x, y]
    velocity: Number  # directional velocity : left (-ve) : right (+ve)
    timer: int  # frame timer


# fmt:off
@unique 
class ParticleKind(Enum): 
    """used for class AnimationMiscAssets"""

    FLAME           = "flame"
    FLAMEGLOW       = "flameglow"
    LEAF            = "leaf"
# fmt:on


@unique
class EntityKind(Enum):
    PLAYER = "player"
    ENEMY = "enemy"
    # note: is portal an entity? if it can teleport and move then maybe consider it.
    PORTAL = "portal"


@unique  # """Class decorator for enumerations ensuring unique member values."""
class TileKind(Enum):
    DECOR = "decor"
    GRASS = "grass"
    LARGE_DECOR = "large_decor"
    PORTAL = "portal"
    SPAWNERS = "spawners"
    STONE = "stone"


#  NOTE: ideally start with 1 (as 0 may be assumed as False)
#   but we used 0,1,2 as variants for spawner 'tiles' while drawing the map.json via level editor in src/editor.py
#   for the sake of the wrapping around all spawner variants, e.g. 0 1 2 0 1 2 ..... or it.cycle(...)
@unique  # """Class decorator for enumerations ensuring unique member values."""
class SpawnerKind(Enum):
    # auto(): Instances are replaced with an appropriate value in Enum class suites.
    PLAYER = 0
    ENEMY = 1
    PORTAL = 2

    # PERF: use cls classmethod instead?
    def as_entity(self, entity_kind: EntityKind):
        match entity_kind:
            case EntityKind.PLAYER:
                return self.PLAYER
            case EntityKind.ENEMY:
                return self.ENEMY
            case EntityKind.PORTAL:
                return self.PORTAL


@dataclass
class Movement:
    """False == 0 and True == 1"""

    left: bool
    right: bool
    top: bool
    bottom: bool


@dataclass
class Collisions:
    """False == 0 and True == 1"""

    left: bool
    right: bool
    up: bool
    down: bool


################################################################################
### ANIMATION
################################################################################


class Animation:
    def __init__(self, images: list[pg.Surface], img_dur: int = 5, loop: bool = True) -> None:
        self.images: Final[list[pg.Surface]] = images  # this is not copied
        self._img_duration: Final = img_dur

        self._img_duration_inverse: Final = 1 / self._img_duration  # perf:minor
        self._total_frames: Final = self._img_duration * len(self.images)

        self.done = True
        self.frame = 0
        self.loop = loop

    def copy(self) -> "Animation":
        return Animation(self.images, self._img_duration, self.loop)

    def update(self) -> None:
        """Increment frames like a movie screen roll or a marque"""
        if self.loop:
            self.frame += 1
            self.frame %= self._total_frames
        else:
            self.frame = min(self.frame + 1, self._total_frames - 1)

            if self.frame >= self._total_frames - 1:
                self.done = True

    def img(self) -> pg.Surface:
        """Returns current image to render in animation cycle. Similar to render phase in the '__init__ -> update -> render' cycle"""

        return self.images[int(self.frame * self._img_duration_inverse)]


################################################################################
### FILE I/O
################################################################################


def load_img(path: str, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None) -> pg.Surface:
    """Load and return a pygame Surface image. Note: Ported from DaFluffyPotato's pygpen lib"""
    img = pg.image.load(path).convert_alpha() if with_alpha else pg.image.load(path).convert()
    if colorkey is not None:
        img.set_colorkey(colorkey)
    return img


def load_imgs(path: str, with_alpha: bool = False, colorkey: Union[tuple[int, int, int], None] = None) -> list[pg.Surface]:
    """listdir lists all image filenames in path directory and loads_img over each and returns list of pg.Surfaces

    Example::

        ```python
        load_imgs(path=os.path.join(IMAGES_PATH, "tiles", "grass"), with_alpha=True, colorkey=BLACK)
        ```
    """
    return [load_img(f"{Path(path) / img_name}", with_alpha, colorkey) for img_name in sorted(os.listdir(path))]


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
    window_height: int
    window_width: int
    player_dash: int
    player_jump: int
    player_speed: int
    shadow_range: int
    sound_volume: float
    star_count: int

    @classmethod
    def from_dict(cls, config_dict: dict[str, str]):
        """
        Create an AppConfig instance from a dictionary.

        Handles converting string values to appropriate data types and setting defaults for missing keys.
        """
        return cls(
            blur_enabled=config_dict.get('blur_enabled', 'false').lower() == 'true',
            blur_passes=int(config_dict.get('blur_passes', '1')),
            blur_size=int(config_dict.get('blur_size', '3')),
            blur_vibrancy=float(config_dict.get('blur_vibrancy', '0.0')),
            col_shadow=config_dict.get('col_shadow', '000000'),
            drop_shadow=config_dict.get('drop_shadow', 'false').lower() == 'true',
            enemy_jump=int(config_dict.get('enemy_jump', '0')),
            enemy_speed=int(config_dict.get('enemy_speed', '0')),
            window_height=int(config_dict.get('window_height', '480')),
            window_width=int(config_dict.get('window_width', '640')),
            player_dash=int(config_dict.get('player_dash', '0')),
            player_jump=int(config_dict.get('player_jump', '0')),
            player_speed=int(config_dict.get('player_speed', '0')),
            shadow_range=int(config_dict.get('shadow_range', '1')),
            sound_volume=float(config_dict.get('sound_volume', '0.0')),
            star_count=int(config_dict.get('star_count', '0')),
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

        with open(filepath, "r") as f:
            return {
                k: v
                for line in f
                if (l := line.strip()) and not l.startswith("#")
                for k, v in [
                    l.split(
                        maxsplit=1,
                    )
                ]
            }


@dataclass
class ConfigHandler:
    def __init__(self, config_path: Path) -> None:
        self._path: Final[Path] = config_path
        self.config: Dict[str, Any] = {}

        self.game: Dict[str, Any] = {}

        self.game_entity_enemy: Dict[str, Any] = {}
        self.game_entity_player: Dict[str, Any] = {}
        self.game_misc_decorations: Dict[str, Any] = {}
        self.game_misc_decorations_blur: Dict[str, Any] = {}
        self.game_world_stars: Dict[str, Any] = {}

    def load_game_config(self) -> None:
        self.config = toml.load(self._path)
        self.game = self.config.copy().get("game", {})

        self.game_world_stars = self.game.get("world", {}).get("stars", {})
        self.game_entity_player = self.game.get("entity", {}).get("player", {}).get("movement", {})
        self.game_entity_enemy = self.game.get("entity", {}).get("enemy", {}).get("movement", {})
        self.game_misc_decorations = self.game.get("misc", {}).get("decorations", {})
        self.game_misc_decorations_blur = self.game.get("misc", {}).get("decorations", {}).get("blur", {})


##########
# COLORS #


@lru_cache(maxsize=32)
def hex_to_rgb(s: str) -> tuple[int, int, int]:
    """HEX to RGB color:

    The red, green and blue use 8 bits each, which have integer values from 0 to 255.
    So the number of colors that can be generated is:
    256×256×256 = 16777216 = 100000016
    Hex to RGB conversion
      - Get the 2 left digits of the hex color code and convert to decimal value to get the red color level.
      - Get the 2 middle digits of the hex color code and convert to decimal value to get the green color level.
      - Get the 2 right digits of the hex color code and convert to decimal value to get the blue color level.
    Convert red hex color code FF0000 to RGB color: Hex = FF0000
    R = FF16 = 25510, G = 0016 = 010, B = 0016 = 010
    RGB = (255, 0, 0)
    Source: https://www.rapidtables.com/convert/color/how-hex-to-rgb.html

    Examples::

        assert hex_to_rgb("#ff0000") == (255, 0, 0)
        assert hex_to_rgb("ff0000") == (255, 0, 0)
        assert hex_to_rgb("#ffd700") == (255, 215, 0)
        assert hex_to_rgb("#FFD700") == (255, 215, 0)
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

    Constraints::

        0 ≤ h < 360 and 0.0 ≤ s ≤ 1.0 and 0.0 ≤ l ≤ 1.0

    Examples::

        assert hsl_to_rgb(0, 0, 0) == (0, 0, 0)             # black
        assert hsl_to_rgb(0, 0, 1) == (255, 255, 255)       # white
        assert hsl_to_rgb(0, 1, 0.5) == (255, 0, 0)         # red
        assert hsl_to_rgb(120, 1, 0.5) == (0, 255, 0)       # lime green
        assert hsl_to_rgb(240, 1, 0.5) == (0, 0, 255)       # blue
        assert hsl_to_rgb(60, 1, 0.5) == (255, 255, 0)      # yellow
        assert hsl_to_rgb(180, 1, 0.5) == (0, 255, 255)     # cyan
        assert hsl_to_rgb(300, 1, 0.5) == (255, 0, 255)     # magenta
        assert hsl_to_rgb(0, 0, 0.75) == (191, 191, 191)    # silver
        assert hsl_to_rgb(0, 0, 0.5) == (128, 128, 128)     # gray
        assert hsl_to_rgb(0, 1, 0.25) == (128, 0, 0)        # maroon
        assert hsl_to_rgb(60, 1, 0.25) == (128, 128, 0)     # olive
        assert hsl_to_rgb(120, 1, 0.25) == (0, 128, 0)      # green
        assert hsl_to_rgb(300, 1, 0.25) == (128, 0, 128)    # purple
        assert hsl_to_rgb(180, 1, 0.25) == (0, 128, 128)    # teal
        assert hsl_to_rgb(240, 1, 0.25) == (0, 0, 128)      # navy
    """

    # pre.hsl_to_rgb.cache_info()
    #   Thu Apr 18 04:56:05 PM IST 2024
    #   hits=79, misses=28, currsize=28

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

    # convert to 0-255 scale
    #   note: round() instead of int() helps in precision. e.g. gray 127 -> 128
    return ColorKind(round((r_prime + m) * 255), round((g_prime + m) * 255), round((b_prime + m) * 255))


#############
# CONSTANTS #


# flags: debugging, etc
# fmt: off
DEBUG_EDITOR_ASSERTS    = False
DEBUG_EDITOR_HUD        = True

DEBUG_GAME_ASSERTS      = True
DEBUG_GAME_PRINTLOG     = False
DEBUG_GAME_LOGGING      = True
DEBUG_GAME_CACHEINFO    = True
DEBUG_GAME_HUD          = True
DEBUG_GAME_PROFILER     = False
DEBUG_GAME_STRESSTEST   = False
# fmt: on


# fmt: off
CAMERA_SPEED            = 2  # use with editor camera move fast around the world
FPS_CAP                 = 60
RENDER_SCALE            = 2  # for editor
SCALE                   = 0.5
TILE_SIZE               = 16
# fmt: on


# fmt: off
SCREEN_RESOLUTION_MODE = 0
SCREEN_WIDTH            = (960 ,640)[SCREEN_RESOLUTION_MODE]
SCREEN_HEIGHT           = (630 ,480)[SCREEN_RESOLUTION_MODE]

DIMENSIONS              = (SCREEN_WIDTH, SCREEN_HEIGHT)  # ratio: (4/3) or (1.3333333333333333)
DIMENSIONS_HALF         = (int(SCREEN_WIDTH * SCALE), int(SCREEN_HEIGHT * SCALE)) # 340,240  # 640/480==4/3 | 853/480==16/9
# fmt: on

# fmt: off
CAPTION                 = "tiptoe"
CAPTION_EDITOR          = "tiptoe level editor"
# fmt: on

# fmt: off
SRC_PATH                        = Path("src")

SRC_DATA_PATH                   = SRC_PATH / "data"

SRC_DATA_IMAGES_PATH            = SRC_DATA_PATH / "images" 
SRC_DATA_MAP_PATH               = SRC_DATA_PATH / "maps" 

SRC_DATA_IMAGES_ENTITIES_PATH   = SRC_DATA_IMAGES_PATH / "entities"
# fmt: on

# aliases for directory paths
# fmt: off
CONFIG_PATH             = SRC_PATH / "config"
ENTITY_PATH             = SRC_DATA_IMAGES_ENTITIES_PATH
FONT_PATH               = SRC_DATA_PATH / "font"
IMGS_PATH               = SRC_DATA_IMAGES_PATH 
INPUTSTATE_PATH         = None  
MAP_PATH                = SRC_DATA_MAP_PATH
SFX_PATH                = SRC_DATA_PATH / "sfx"
SPRITESHEET_PATH        = None
# fmt: on


# colors:
# fmt: off
BEIGE                   = (15, 20, 25)
BGDARK                  = hsl_to_rgb(234, 0.1618, 0.0618)
BGDARKER                = hsl_to_rgb(234, 0.1618, 0.0328)
BLACK                   = (0, 0, 0)
BLACKMID                = (1, 1, 1)
CHARCOAL                = (10, 10, 10)
CREAM                   = hsl_to_rgb(0, 0.1618, 0.618)
DARKGRAY                = (20, 20, 20)
GRAY                    = hsl_to_rgb(0, 0, 0.5)
GREEN                   = hsl_to_rgb(120, 1, 0.25)
MIDNIGHT                = (2, 2, 3)
OLIVE                   = hsl_to_rgb(60, 1, 0.25)
OLIVEMID                = hsl_to_rgb(60, 0.4, 0.25)
ORANGE                  = hsl_to_rgb(10,0.5,0.5)
PINKLIGHT               = hsl_to_rgb(300, 0.26, 0.4)
PINK                    = hsl_to_rgb(300, 0.26, 0.18)
PURPLE                  = hsl_to_rgb(300, 1, 0.25)
PURPLEMID               = hsl_to_rgb(300, 0.3, 0.0828)
RED                     = hsl_to_rgb(0, 0.618, 0.328)
SILVER                  = hsl_to_rgb(0, 0, 0.75)
TEAL                    = hsl_to_rgb(180, 0.4, 0.25)
TRANSPARENT             = (0, 0, 0, 0)
WHITE                   = (255, 255, 255)
YELLOW                  = hsl_to_rgb(60, 0.6, 0.3)
YELLOWMID               = hsl_to_rgb(60, 0.4, 0.25)
# fmt: on


@dataclass
class COLORPALETTEOIL6:
    """
    Palette Name: Oil 6
    Description: Created by [GrafxKid](http://grafxkid.tumblr.com/palettes).
    Colors: 6
    """

    COLOR0 = 39, 39, 68  # 272744
    COLOR1 = 73, 77, 126  # 494d7e
    COLOR2 = 139, 109, 156  # 8b6d9c
    COLOR3 = 198, 159, 165  # c69fa5
    COLOR4 = 242, 211, 171  # f2d3ab
    COLOR5 = 251, 245, 239  # fbf5ef


# fmt: off
@dataclass
class COLOR:
    BG                  = hsl_to_rgb(240, 0.328, 0.128)
    BGCOLORDARK         = (9, 9, 17) or hsl_to_rgb(240, 0.3, 0.05)
    BGCOLORDARKER       = hsl_to_rgb(240, 0.3, 0.04)
    BGCOLORDARKGLOW     = (((9 + 238) * 0.2, (9 + 238) * 0.2, (17 + 238) * 0.3), ((9 + 0) * 0.2, (9 + 0) * 0.2, (17 + 0) * 0.3))[randint(0, 1)] 
                        # ^ todo: add factor_adder till 17 becomes 255, and so on for each r,g,b
    BGMIRAGE            = hsl_to_rgb(240, 0.2, 0.07)  # used to set colorkey for stars
    ENEMY               = ORANGE or hsl_to_rgb(10, 0.3, 0.08) 
    GUN                 = hsl_to_rgb(300, 0.5, 0.045) 
    FGSTARS             = hsl_to_rgb(240, 0.3, 0.10)
    FLAME               = hsl_to_rgb(0, 0.618, 0.328)
    TRANSPARENTGLOW     = (20, 20, 20)
    FLAMEGLOW           = (20, 20, randint(70,90))  # uses special_flags=pygame.BLEND_RGB_ADD for glow effect while blitting
    FLAMETORCH          = hsl_to_rgb(300, 0.5, 0.045)
    GRASS               = hsl_to_rgb(0, 0.618, 0.328)
    PLAYER              = TEAL or (4, 2, 0)
    PLAYERIDLE          = (4, 2, 0)
    PLAYERJUMP          = PLAYER or hsl_to_rgb(0, 0.618, 0.328)
    PLAYERRUN           = PLAYER or (1, 1, 1)
    PLAYERSTAR          = PINK
    PORTAL1             = (255, 255, 255)
    PORTAL2             = (15, 20, 25)
    STAR                = hsl_to_rgb(300, 0.26, 0.18) or PINK
    STONE               = (1, 1, 1)
# fmt: on


# fmt: off
@dataclass
class COUNT:
    STAR                = (TILE_SIZE or 16)
    FLAMEGLOW           = 1
    # FLAMEPARTICLE   = (TILE_SIZE or 16)


@dataclass
class COUNTRANDOMFRAMES:
    """Random frame count to start on.""" 
    FLAMEGLOW           = randint(0, 20)        # (0,20) OG or (36,64)
    FLAMEPARTICLE       = randint(0, 20)        # (0,20) OG or (36,64)
# fmt: on


@dataclass
class SIZE:
    ENEMY = (TILE_SIZE // 2, TILE_SIZE - 1)
    FLAMEPARTICLE = (4, 5) or (3, 3)
    FLAMETORCH = (3, 12)
    GUN = (7, 4)
    PLAYER = (TILE_SIZE // 2, TILE_SIZE - 1)
    # STAR = tuple(map(lambda x: x**0.328, (69 / 1.618, 69 / 1.618)))
    STAR = int((69 / 1.618) ** 0.328), int((69 / 1.618) ** 0.328)  # 3.425, 3.425 -> 3, 3
    # Constants derived from above
    ENEMYJUMP = (ENEMY[0], ENEMY[1] - 1)
    FLAMEGLOWPARTICLE = (round(FLAMEPARTICLE[0] ** 1.618 * 1), round(FLAMEPARTICLE[1] ** 1.618 * 1))
    PLAYERIDLE = (PLAYER[0] + 1, PLAYER[1] - 1)
    PLAYERJUMP = (PLAYER[0] - 1, PLAYER[1])
    PLAYERSTARDASHRADIUS = STAR or (int(PLAYER[0] - STAR[0] - 1), int(PLAYER[1] - STAR[1]))
    PLAYERRUN = (PLAYER[0] + 1, PLAYER[1] - 1)
    PORTAL = (max(5, round(PLAYER[0] * 1.618)), max(18, round(TILE_SIZE + 2)))


# fmt: off
NEIGHBOR_OFFSETS    = {
    (-1,-1), ( 0,-1), ( 1,-1),
    (-1, 0), ( 0, 0), ( 1, 0),
    (-1, 1), ( 0, 1), ( 1, 1),
}
N_NEIGHBOR_OFFSETS  = 9
# fmt: on


# fmt: off
AUTOTILE_TYPES      = { TileKind.STONE, TileKind.GRASS, }
PHYSICS_TILES       = { TileKind.STONE, TileKind.GRASS, }

SPAWNERS_KINDS      = { EntityKind.PLAYER, EntityKind.ENEMY, TileKind.PORTAL }  # not used for now
# fmt: on


##############
# AUTOTILING #


# fmt: off
# NOTE: prefer Enum over IntEnum
# use 0 for the first (even though 0 seems as False) to wrap (%) around all
# variation,,  it.cycle() or next(...)

@unique 
class AutotileID(IntEnum):
    """Key ID via `AutoTileVariant` for `AUTOTILE_MAP`

    For example::

        assert list(range(0, 8 + 1)) is [x.value for x in AutoTileVariant]
    """
    TOPLEFT         = auto(0)   # 0     
    TOPCENTER       = auto()    # 1
    TOPRIGHT        = auto()    # 2
    MIDDLERIGHT     = auto()    # 3
    BOTTOMRIGHT     = auto()    # 4
    BOTTOMCENTER    = auto()    # 5
    BOTTOMLEFT      = auto()    # 6
    MIDDLELEFT      = auto()    # 7
    MIDDLECENTER    = auto()    # 8
# fmt: on


"""
offsets:
    [ (-1,-1) ( 0,-1) ( 1,-1 )
      (-1, 0) ( 0, 0) ( 1, 0 )
      (-1, 1) ( 0, 1) ( 1, 1 ) ]

tiles:
    { 0   1   2 
      7   8   3
      6   5   4 }
"""
# fmt: off
AUTOTILE_MAP = {
    tuple(sorted([( 1, 0), ( 0, 1)                 ])): AutotileID.TOPLEFT      or 0,  # ES
    tuple(sorted([( 1, 0), ( 0, 1), (-1, 0)        ])): AutotileID.TOPCENTER    or 1,  # ESW
    tuple(sorted([(-1, 0), ( 0, 1)                 ])): AutotileID.TOPRIGHT     or 2,  # WS
    tuple(sorted([(-1, 0), ( 0,-1), ( 0, 1)        ])): AutotileID.MIDDLERIGHT  or 3,  # WSN
    tuple(sorted([(-1, 0), ( 0,-1)                 ])): AutotileID.BOTTOMRIGHT  or 4,  # WN
    tuple(sorted([(-1, 0), ( 0,-1), ( 1, 0)        ])): AutotileID.BOTTOMCENTER or 5,  # WNE
    tuple(sorted([( 1, 0), ( 0,-1)                 ])): AutotileID.BOTTOMLEFT   or 6,  # EN
    tuple(sorted([( 1, 0), ( 0,-1), ( 0, 1)        ])): AutotileID.MIDDLELEFT   or 7,  # ENS
    tuple(sorted([( 1, 0), (-1, 0), ( 0, 1), (0,-1)])): AutotileID.MIDDLECENTER or 8,  # EWSN
}
# fmt: on


################################################################################
### SURFACE PYGAME
################################################################################


def surfaces_collidepoint(pos: pg.Vector2, sprites: Sequence[pg.SurfaceType]):
    """Get a iterable generator of all surfaces that contain a point (x,y).
    Source: https://www.pygame.org/docs/tut/newbieguide.html"""
    return (s for s in sprites if s.get_rect().collidepoint(pos))


def rects_collidepoint(pos: pg.Vector2, sprites: Sequence[pg.Rect]):
    """Get a iterable generator of all rects that contain a point (x,y).
    Source: https://www.pygame.org/docs/tut/newbieguide.html"""
    return (s for s in sprites if s.collidepoint(pos))


def create_surface(size: tuple[int, int], colorkey: tuple[int, int, int] | ColorValue, fill_color: tuple[int, int, int] | ColorValue) -> pg.SurfaceType:
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

    pg.SurfaceType"""


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
create_surfaces_partialfn.__doc__ = """New create_surfaces function with partial application of colorkey argument and or other keywords."""


def create_circle_surf(size: tuple[int, int], fill_color: ColorValue, colorkey: ColorValue = BLACK) -> pg.SurfaceType:  # FIXME:
    """FIXME!!! this is a special case for flameglow particle and should not be used here for general circle creation"""
    # FIXME:
    surf = pg.Surface(size).convert()
    ca, cb = iter(size)
    center = ca * 0.5, cb * 0.5
    radius = center[0]
    rect = pg.draw.circle(surf, BLACK, center, radius * 2)
    rect = pg.draw.ellipse(surf, fill_color, rect)
    rect = pg.draw.circle(surf, RED, center, radius)
    surf.set_colorkey(colorkey)
    return surf


create_circle_surf_partialfn = partial(create_circle_surf, colorkey=BLACK)
create_circle_surf_partialfn.__doc__ = """New create_circle_surf_partialfn function with partial application of colorkey argument and or other keywords."""


################################################################################
### MATH
################################################################################


class Math:
    """Collection of utility functions for mathematical operations."""

    @dataclass
    class UnitState:
        pos: Vec2Type  # pyright: ignore
        max_distance: float

    @staticmethod
    def move_to_unitstate(unit: UnitState, next_pos: UnitState, max_dist: Number):
        x1, y1 = unit.pos
        x2, y2 = next_pos.pos
        dx, dy = x2 - x1, y2 - y1
        dist_squared = dx * dx + dy * dy
        if dist_squared <= max_dist * max_dist:
            unit.pos = next_pos.pos
        else:
            dist = float(math.sqrt(float(dist_squared)))
            ratio = max_dist / dist
            unit.pos = (x1 + dx * ratio, y1 + dy * ratio)

    @staticmethod
    def move_to_vec2(unit: pg.Vector2, next_pos: pg.Vector2, max_dist: Number):
        x1, y1 = iter(unit)
        x2, y2 = iter(next_pos)
        dx, dy = x2 - x1, y2 - y1
        dist_squared = dx * dx + dy * dy
        if dist_squared <= max_dist * max_dist:
            unit = next_pos
        else:
            dist = float(math.sqrt(float(dist_squared)))
            ratio = max_dist / dist
            unit = pg.Vector2(x1 + dx * ratio, y1 + dy * ratio)

    @staticmethod
    def move_to(unit: tuple[Number, Number], next_pos: tuple[Number, Number], max_dist: Number):
        x1, y1 = iter(unit)
        x2, y2 = iter(next_pos)
        dx, dy = x2 - x1, y2 - y1
        dist_squared = dx * dx + dy * dy
        if dist_squared <= max_dist * max_dist:
            unit = next_pos
        else:
            dist = float(math.sqrt(float(dist_squared)))
            ratio = max_dist / dist
            unit = (x1 + dx * ratio, y1 + dy * ratio)

    @staticmethod
    def advance_vec2(vec2: pg.Vector2, angle: SupportsFloatOrIndex, amount: Number) -> None:
        """
        Advances a 2D vector (pg.Vector2) by a given angle and amount.

        Args:
            vec2: The pg.Vector2 object representing the 2D vector to advance.
            angle: The angle in radians to move the vector.
            amount: The distance to move the vector along the specified angle.

        This function modifies the `vec2` object in-place and returns None.
        """
        vec2 += (math.cos(angle) * amount, math.sin(angle) * amount)

    @staticmethod
    def advance_float2(point2: list[float], angle: SupportsFloatOrIndex, amount: Number) -> None:
        """
        Advances a 2D point represented by a list of floats by a given angle and amount.

        Args:
            point2: A list of two floats representing the x and y coordinates of the 2D point.
            angle: The angle in radians to move the point.
            amount: The distance to move the point along the specified angle.

        This function modifies the `point2` list in-place and returns None.

        Raises:
            AssertionError: If the length of `point2` is not 2 (assuming x and y coordinates).
        """
        if DEBUG_GAME_ASSERTS:
            assert len(point2) == 2, f"want a vector like list of x and y items. got: {point2}"

        point2[0] += math.cos(angle) * amount
        point2[1] += math.sin(angle) * amount

    @staticmethod
    def advance_int2(point2: list[int], angle: SupportsFloatOrIndex, amount: Number) -> None:
        """
        Advances a 2D point represented by a list of integers by a given angle and amount.

        **Important:** This function uses floor division (`//`) to convert potentially floating-point
                      calculations to integers before assigning them to the list elements.

        Args:
            point2: A list of two integers representing the x and y coordinates of the 2D point.
            angle: The angle in radians to move the point.
            amount: The distance to move the point along the specified angle.

        This function modifies the `point2` list in-place and returns None.

        Raises:
            AssertionError: If the length of `point2` is not 2 (assuming x and y coordinates).
        """
        if DEBUG_GAME_ASSERTS:
            assert len(point2) == 2, f"want a vector like list of x and y items. got: {point2}"

        point2[0] += math.floor(100 * (math.cos(angle) * amount) // 100)
        point2[1] += math.floor(100 * (math.sin(angle) * amount) // 100)


################################################################################
### FUNCUTILS & ITERUTILS #
################################################################################
# NOTE: this is just for learning


class Funcutils:
    @staticmethod
    def idiom_functools_reducer():
        print(f"{ reduce(lambda x, y: x/y, [1, 2, 3, 4, 5]) = }")  # 0.008333333333333333
        print(f"{ reduce(lambda x, y: x//y, [1, 2, 3, 4, 5]) = }")  # 0
        print(f"{ reduce(lambda x, y: x*y, [1, 2, 3, 4, 5]) = }")  # 120
        print(f"{ reduce(lambda x, y: x+y, [1, 2, 3, 4, 5]) = }")  # 15: calculates ((((1+2)+3)+4)+5)
        print(f"{ reduce(lambda x, y: x-y, [1, 2, 3, 4, 5]) = }")  # -13
        print(f"{ reduce(lambda x, y: x%y, [1, 2, 3, 4, 5]) = }")  # 1
        print(f"{ reduce(lambda x, y: x**y, [1, 2, 3, 4, 5]) = }")  # 1
        print(f"{ reduce(lambda x, y: x**(1/y), [1, 2, 3, 4, 5]) = }")  # 1.0


class Iterutils:

    @staticmethod
    def idiom_it_cycle():
        # THIS IS A STUB FOR DOCSTRING PORTED FROM collections as inspiration
        """Like dict.update() but subtracts counts instead of replacing them.
        Counts can be reduced below zero.  Both the inputs and outputs are
        allowed to contain zero and negative counts.

        Source can be an iterable, a dictionary, or another Counter instance.

        >>> c = Counter('which')
        >>> c.subtract('witch')             # subtract elements from another iterable
        >>> c.subtract(Counter('watch'))    # subtract elements from another counter
        >>> c['h']                          # 2 in which, minus 1 in witch, minus 1 in watch
        0
        >>> c['w']                          # 1 in which, minus 1 in witch, minus 1 in watch
        -1

        """
        # bg = (0, 0, 0)
        # ...
        bg_colors = (hsl_to_rgb(240, 0.3, 0.1), hsl_to_rgb(240, 0.35, 0.1), hsl_to_rgb(240, 0.3, 0.15))
        bg_color_cycle = it.cycle(bg_colors)
        counter = 0
        while True:
            # display_2.blit(bg, (0, 0))
            # ...
            bg_color_cycle = it.cycle(bg_colors)
            nxt_bg_color = next(bg_color_cycle)
            # ...
            # bg.fill(nxt_bg_color)
            print(nxt_bg_color)
            # ...
            if (_user_quits := True) and _user_quits:
                if counter >= 10:
                    break
            counter += 1

    @staticmethod
    def idiom_collection_defaultdict():
        lst = {"a": (0, 0), "b": (1, 1)}
        foo: defaultdict[str, list[tuple[int, int]]] = defaultdict(list)
        for key, (x, y) in lst.items():
            foo[key].append((x, y))
        print(foo)

    @staticmethod
    def idiom_it_zip_long():
        for x in it.zip_longest([1, 2, 3], [1, 2, 3, 4, 5, 6]):
            print(x, end=" ")
        print()

    @staticmethod
    def idiom_it_startmap():
        # @fbaptiste: 05_itertools.ipynb
        lst = [(3, x) for x in range(6)]
        lst_starmap = it.starmap(math.pow, lst)
        for i in lst_starmap:
            print(i, end=" ")
        # ^ >>> 1.0 3.0 9.0 27.0 81.0 243.0
        print()

    @staticmethod
    def idiom_it_chain():
        # @fbaptiste: 05_itertools.ipynb
        lst1 = [1, 2, 3, 4, 5]
        lst2 = "abcd"
        lst3 = (100, 200, 300)
        lst_chain = it.chain(lst1, lst2, lst3)
        for el in it.chain.from_iterable(zip(lst_chain)):
            print(el, end=" ")
        # ^ >>> 1 2 3 4 5 a b c d 100 200 300
        print()

    @staticmethod
    def idiom_it_islice():
        # @fbaptiste: 05_itertools.ipynb
        # slice iterator: it even support start stop and step, except negative slicing
        for el in it.islice((el * 2 for el in range(10)), 3):
            print(el, end=" ")
        # ^ >>> 0 2 4
        print()
        for el in it.islice((el * 2 for el in range(10)), 1, None, 2):
            print(el, end=" ")
        # ^ >>> 2 6 10 14 18
        print()
        for el in it.islice((el * 2 for el in range(10)), 1, 5, 2):
            print(el, end=" ")
        # ^ >>> 2 6
        print()
        # slice sets: no guarantees of order in sets
        s = {"a", "b", 10, 3.2}
        for el in it.islice(s, 0, 2):
            print(el, end=" ")
        # ^ >>> b 10
        print()
        # t=it.tee()
        # takew=it.takewhile()


### PATHFINDING

# todo: astar
# todo: djikstra
