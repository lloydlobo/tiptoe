import itertools as it
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from functools import lru_cache, partial, reduce
from pathlib import Path
from pprint import pprint
from random import randint
from typing import Any, Dict, Final, Generator, Sequence, Tuple, Union

import pygame as pg
import toml


#########
# TYPES #


# This typehint is used when a function would return an RGBA table.
# note: ported from pygame source file: _common.py
RGBAOutput = Tuple[int, int, int, int]
ColorValue = Union[pg.Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]


Number = Union[int, float]


@dataclass
class Projectile:
    pos: list[Number]  # [x, y]
    velocity: Number  # directional velocity : left (-ve) : right (+ve)
    timer: int  # frame timer


# fmt:off
class ParticleKind(Enum):
    # class AnimationMiscAssets:
    FLAME           = "flame"
    FLAMEGLOW       = "flameglow"
    LEAF            = "leaf"
# fmt:on


class EntityKind(Enum):
    PLAYER = "player"
    ENEMY = "enemy"
    # FIXME: is portal an entity? if it can teleport and move then maybe consider it.
    PORTAL = "portal"


class TileKind(Enum):
    DECOR = "decor"
    GRASS = "grass"
    LARGE_DECOR = "large_decor"
    PORTAL = "portal"
    SPAWNERS = "spawners"
    STONE = "stone"


class SpawnerKind(IntEnum):
    # auto(): Instances are replaced with an appropriate value in Enum class suites.
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


##########
# ANIMATION #


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
        """Returns current image to render in animation cycle. Similar to
        render phase in the '__init__ -> update -> render' cycle"""

        return self.images[int(self.frame * self._img_duration_inverse)]


############
# FILE I/O #


def load_img(path: str, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None) -> pg.Surface:
    """Load and return a pygame Surface image. Note: Ported from DaFluffyPotato's pygpen lib"""
    img = pg.image.load(path).convert_alpha() if with_alpha else pg.image.load(path).convert()
    if colorkey is not None:
        img.set_colorkey(colorkey)
    return img


def load_imgs(path: str, with_alpha: bool = False, colorkey: Union[tuple[int, int, int], None] = None) -> list[pg.Surface]:
    """
    listdir lists all image filenames in path directory and loads_img over each and returns list of pg.Surfaces
        @example:   load_imgs(path=os.path.join(IMAGES_PATH, "tiles", "grass"), with_alpha=True, colorkey=BLACK)
    """
    return [load_img(f"{Path(path) / img_name}", with_alpha, colorkey) for img_name in sorted(os.listdir(path))]


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
    """
    HEX to RGB color:
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

    >>> assert hex_to_rgb("#ff0000") == (255, 0, 0)
    >>> assert hex_to_rgb("ff0000") == (255, 0, 0)
    >>> assert hex_to_rgb("#ffd700") == (255, 215, 0)
    >>> assert hex_to_rgb("#FFD700") == (255, 215, 0)
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


@lru_cache(maxsize=32)
def hsl_to_rgb(h: int, s: float, l: float) -> tuple[int, int, int]:
    """
    Constraints: 0 ≤ H < 360, 0 ≤ S ≤ 1 and 0 ≤ L ≤ 1

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
    return (round((r_prime + m) * 255), round((g_prime + m) * 255), round((b_prime + m) * 255))


#############
# CONSTANTS #


# flags: debugging, etc
# fmt: off
DEBUG_EDITOR_ASSERTS    = True
DEBUG_EDITOR_HUD        = True

DEBUG_GAME_ASSERTS      = True
DEBUG_GAME_CACHEINFO    = False
DEBUG_GAME_HUD          = False
DEBUG_GAME_PROFILER     = False
DEBUG_GAME_STRESSTEST   = False
# fmt: on


# fmt: off
CAMERA_SPEED        = 2  # use with editor camera move fast around the world
FPS_CAP             = 60
RENDER_SCALE        = 2  # for editor
SCALE               = 0.5
TILE_SIZE           = 16
# fmt: on


# fmt: off
SCREEN_WIDTH        = 960 or 640
SCREEN_HEIGHT       = 630 or 480

DIMENSIONS          = (SCREEN_WIDTH, SCREEN_HEIGHT)  # ratio: (4/3) or (1.3333333333333333)
DIMENSIONS_HALF     = (int(SCREEN_WIDTH * SCALE), int(SCREEN_HEIGHT * SCALE)) # 340,240  # 640/480==4/3 | 853/480==16/9
# fmt: on

# fmt: off
CAPTION             = "tiptoe"
CAPTION_EDITOR      = "tiptoe level editor"
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
ENTITY_PATH         = SRC_DATA_IMAGES_ENTITIES_PATH
FONT_PATH           = None
IMGS_PATH           = SRC_DATA_IMAGES_PATH 
INPUTSTATE_PATH     = None  
MAP_PATH            = SRC_DATA_MAP_PATH
SOUNDS_PATH         = None
SPRITESHEET_PATH    = None
# fmt: on


# colors:
# fmt: off
BEIGE               = (15, 20, 25)
BGDARK              = hsl_to_rgb(234, 0.1618, 0.0618)
BGDARKER            = hsl_to_rgb(234, 0.1618, 0.0328)
BLACK               = (0, 0, 0)
BLACKMID            = (1, 1, 1)
CHARCOAL            = (10, 10, 10)
CREAM               = hsl_to_rgb(0, 0.1618, 0.618)
DARKGRAY            = (20, 20, 20)
GRAY                = hsl_to_rgb(0, 0, 0.5)
GREEN               = hsl_to_rgb(120, 1, 0.25)
MIDNIGHT            = (2, 2, 3)
OLIVE               = hsl_to_rgb(60, 1, 0.25)
OLIVEMID            = hsl_to_rgb(60, 0.4, 0.25)
ORANGE              = hsl_to_rgb(10,0.5,0.5)
PINK                = hsl_to_rgb(300, 0.26, 0.18)
PURPLE              = hsl_to_rgb(300, 1, 0.25)
PURPLEMID           = hsl_to_rgb(300, 0.3, 0.0828)
RED                 = hsl_to_rgb(0, 0.618, 0.328)
SILVER              = hsl_to_rgb(0, 0, 0.75)
TEAL                = hsl_to_rgb(180, 0.4, 0.25)
TRANSPARENT         = (0, 0, 0, 0)
WHITE               = (255, 255, 255)
YELLOW              = hsl_to_rgb(60, 0.6, 0.3)
YELLOWMID           = hsl_to_rgb(60, 0.4, 0.25)
# fmt: on


# fmt: off
@dataclass
class COUNT:
    STAR            = (TILE_SIZE or 16)
    # FLAMEPARTICLE   = (TILE_SIZE or 16)


@dataclass
class COUNTRAND:
    FLAMEPARTICLE   = randint(36, 64)        # (0,20) OG
# fmt: on


# fmt: off
@dataclass
class SIZE:
    ENEMY           = (8, 16)
    ENEMYJUMP       = (ENEMY[0], ENEMY[1] - 1)
    FLAMEPARTICLE   = (4,5)or(3, 3)  # use 6,6 if a circles else 3,3 if particle is rect
    FLAMETORCH      = (3, 12)
    PLAYER          = (8, TILE_SIZE)
    PLAYERJUMP      = (PLAYER[0] - 1, PLAYER[1])
    PLAYERRUN       = (PLAYER[0] + 1, PLAYER[1] - 1)
    PORTAL          = (max(5, round(PLAYER[0] * 1.618)), max(18, round(TILE_SIZE + 2)))
    STAR            = tuple(map(lambda x: x**0.328, (69 / 1.618, 69 / 1.618)))

    # Derived Constants
    FLAMEGLOWPARTICLE = (FLAMEPARTICLE[0] + 1, FLAMEPARTICLE[1] + 1)  # use 6,6 if a circles else 3,3 if particle is rect
# fmt: on


# fmt: off
@dataclass
class COLOR:
    BG              = hsl_to_rgb(240, 0.328, 0.128)
    BGCOLORDARK     = (9, 9, 17) or hsl_to_rgb(240, 0.3, 0.05)
    BGCOLORDARKER   = hsl_to_rgb(240, 0.3, 0.04)
    BGCOLORDARKGLOW = (((9 + 238) * 0.2, (9 + 238) * 0.2, (17 + 238) * 0.3), ((9 + 0) * 0.2, (9 + 0) * 0.2, (17 + 0) * 0.3))[randint(0, 1)]  # TODO: add factor_adder till 17 becomes 255, and so on for each r,g,b
    BGMIRAGE        = hsl_to_rgb(240, 0.2, 0.07) # used to set colorkey for stars
    ENEMY           = hsl_to_rgb(10,0.3,0.08) #(hsl_to_rgb(180, 0.4, 0.25), )[randint(0,1)]
    FGSTARS         = hsl_to_rgb(240, 0.3, 0.10) # used to set colorkey for stars
    FLAME           = hsl_to_rgb(0, 0.618, 0.328)
    TRANSPARENTGLOW = (20,20,20)
    FLAMEGLOW       = (30,30,20) # uses special_flags=pygame.BLEND_RGB_ADD for glow effect while blitting
    FLAMETORCH      = hsl_to_rgb(300, 0.5, 0.045)
    GRASS           = hsl_to_rgb(0, 0.618, 0.328)
    PLAYER          = (1, 1, 1)
    PLAYERJUMP      = PINK or hsl_to_rgb(0, 0.618, 0.328)
    PLAYERRUN       = (1, 1, 1)
    PLAYERSTAR      = PINK
    PORTAL1         = (255, 255, 255)
    PORTAL2         = (15, 20, 25)
    STAR            = PINK
    STONE           = (1, 1, 1)
# fmt: on


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
class AutotileID(IntEnum):
    """
    >>> assert list(range(0, 8 + 1)) == [x.value for x in AutoTileVariant]
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


###################
# PYGAME SURFACES #


@dataclass
class Surfaces:

    # expensive computation if run inside game loop
    @staticmethod
    def compute_vignette_scaled(surf: pg.SurfaceType, scale: int = 2, a: int = 255):
        w, h = surf.get_width() * scale, surf.get_height() * scale
        w_half = w / 2.0
        w_half_inv = 1 / w_half
        # a = 255

        # Apply vignette effect
        for y in range(h):
            for x in range(w):
                # Calculate distance from center
                dx = x - w * 0.5
                dy = y - h * 0.5
                dist = math.sqrt(dx * dx + dy * dy)

                # imprecise here
                factor = 1.0 - dist * w_half_inv
                r = abs(int(255 * factor))
                g = abs(int(255 * factor))
                b = abs(int(255 * factor))
                surf.set_at((x - w // scale * 2, y - h // scale * 2), (r, g, b, a))

    @staticmethod
    def compute_vignette_include_corners(surf: pg.SurfaceType, a: int = 255):
        w, h = surf.get_width(), surf.get_height()
        w_half = w / 2.0
        w_half_inv = 1 / w_half

        seen: set[tuple[int, int]] = set()
        # Apply vignette effect
        for y in range(h):
            for x in range(w):
                # continue
                # Calculate distance from center
                dx = x - w * 0.5
                dy = y - h * 0.5
                dist = math.sqrt(dx * dx + dy * dy)

                factor = 1.0 - dist * w_half_inv
                # imprecise here
                r = abs(int(255 * factor))
                g = abs(int(255 * factor))
                b = abs(int(255 * factor))
                surf.set_at((x, y), (r, g, b, a))
                seen.add((x, y))

    @staticmethod
    def compute_vignette(surf: pg.SurfaceType, a: int = 255):
        w, h = surf.get_width(), surf.get_height()
        w_half = w / 2.0
        w_half_inv = 1 / w_half
        # a = 255

        # Apply vignette effect
        for y in range(h):
            for x in range(w):
                for offx, offy in {(-1, 0), (0, -1), (0, 1), (1, 0)}:
                    nx, ny = x + offx, y + offy
                    if not (0 <= nx < w and 0 <= ny < h):
                        # print(nx, ny)
                        continue

                # Calculate distance from center
                dx = x - w * 0.5
                dy = y - h * 0.5
                dist = math.sqrt(dx * dx + dy * dy)

                factor = 1.0 - dist * w_half_inv
                r = abs(int(255 * factor))
                g = abs(int(255 * factor))
                b = abs(int(255 * factor))
                surf.set_at((x, y), (r, g, b, a))

        print(f"{w, h=}")


def create_surface(
    size: tuple[int, int],
    colorkey: tuple[int, int, int] | ColorValue,
    fill_color: tuple[int, int, int],
) -> pg.SurfaceType:
    surf = pg.Surface(size).convert()
    surf.set_colorkey(colorkey)
    surf.fill(fill_color)
    return surf


create_surface_partialfn = partial(create_surface, colorkey=BLACK)
create_surface_partialfn.__doc__ = """
(function) def create_surface(
    size: tuple[int, int], colorkey: tuple[int, int, int] | ColorValue, fill_color: tuple[int, int, int]
) -> pg.SurfaceType

New create_surface function with partial application of colorkey argument and or other keywords.
"""


def create_surface_withalpha(
    size: tuple[int, int],
    colorkey: tuple[int, int, int] | ColorValue,
    fill_color: tuple[int, int, int],
    alpha: int,
) -> pg.SurfaceType:
    surf = pg.Surface(size).convert_alpha()
    surf.set_colorkey(colorkey)
    surf.fill(fill_color)
    surf.set_alpha(alpha)
    return surf


create_surface_withalpha_partialfn = partial(create_surface_withalpha, colorkey=BLACK)
create_surface_withalpha_partialfn.__doc__ = """
(function) def create_surface_withalpha
    size: tuple[int, int], colorkey: tuple[int, int, int] | ColorValue, fill_color: tuple[int, int, int], alpha: int
) -> pg.SurfaceType

New create_surface_withalpha function with partial application of colorkey argument and or other keywords.
"""


def create_surfaces(
    count: int,
    color: tuple[int, int, int] = BLACK,
    size: tuple[int, int] = (TILE_SIZE, TILE_SIZE),
    colorkey: ColorValue = BLACK,
) -> Generator[pg.SurfaceType, None, None]:
    if colorkey:
        return (create_surface(size, colorkey, color) for _ in range(count))
    else:
        return (create_surface_partialfn(size, color) for _ in range(count))


create_surfaces_partialfn = partial(create_surfaces, colorkey=BLACK)
create_surfaces_partialfn.__doc__ = """New create_surfaces function with partial application of colorkey argument and or other keywords."""


def create_circle_surf(size: tuple[int, int], fill_color: ColorValue, colorkey: ColorValue = BLACK) -> pg.SurfaceType:
    surf = pg.Surface(size).convert()
    center = size[0] / 2, size[1] / 2
    radius = center[0]
    pg.draw.circle(surf, fill_color, center, radius)
    surf.set_colorkey(colorkey)
    return surf


create_circle_surf_partialfn = partial(create_circle_surf, colorkey=BLACK)
create_circle_surf_partialfn.__doc__ = """New create_circle_surf_partialfn function with partial application of colorkey argument and or other keywords."""


#########################
# FUNCUTILS & ITERUTILS #

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


"""

vignette effect:

VERSION 1:
PYTHON
        from dataclasses import dataclass
        from pygame import BLEND_ALPHA_SDL2, BLEND_RGBA_MULT
        
        @dataclass
        class GameDisplayConfig:
            dreamlike: int
            noir: int
            moody: int
            blend_flag: int
        
            def create_display(self, bgcolor):
                if self.dreamlike:
                    return self._create_display(bgcolor, alpha=17)
                elif self.noir:
                    return self._create_display(bgcolor, fill_color=(174 * 0.2, 226 * 0.2, 255 * 0.3), vignette_range=(24, 28), color_key=pre.BLACK if self.noir_spotlight else None)
                elif self.moody:
                    return self._create_display(bgcolor, alpha=255 // 2, color_key=pre.BLACK)
                else:
                    return self._create_display(bgcolor, fill_color=(174 * 0.2, 226 * 0.2, 255 * 0.3), vignette_range=(10, 20) if randint(10, 20) else min(8, 255 // 13))
        
            def _create_display(self, bgcolor, alpha=None, fill_color=None, vignette_range=None, color_key=None):
                display = pg.Surface(pre.DIMENSIONS_HALF, self.blend_flag).convert_alpha()
                if fill_color:
                    display.fill(fill_color)
                    if vignette_range:
                        vignette_value = vignette_range[1] if bgcolor == pre.COLOR.BGCOLORDARK else (vignette_range[0] if bgcolor == pre.COLOR.BGCOLORDARKER else vignette_range[1])
                        pre.Surfaces.compute_vignette(display, vignette_value)
                if alpha is not None:
                    display.set_alpha(alpha)
                if color_key is not None:
                    display.set_colorkey(color_key)
                return display
        
        display_config = GameDisplayConfig(
            dreamlike=0,
            noir=1,
            moody=0,
            blend_flag=BLEND_ALPHA_SDL2
        )
        
        self.display_3 = display_config.create_display(self.bgcolor)


VERSION 1:
RUST
        use rand::Rng;
        
        #[derive(Debug)]
        struct GameDisplayConfig {
            dreamlike: bool,
            noir: bool,
            moody: bool,
            blend_flag: u32,
        }
        
        impl GameDisplayConfig {
            fn create_display(&self, bgcolor: (u8, u8, u8)) -> Surface {
                if self.dreamlike {
                    self.create_dreamlike_display(bgcolor)
                } else if self.noir {
                    self.create_noir_display(bgcolor)
                } else if self.moody {
                    self.create_moody_display(bgcolor)
                } else {
                    self.create_default_display(bgcolor)
                }
            }
        
            fn create_dreamlike_display(&self, bgcolor: (u8, u8, u8)) -> Surface {
                self._create_display(bgcolor, Some(17), None, None, None)
            }
        
            fn create_noir_display(&self, bgcolor: (u8, u8, u8)) -> Surface {
                let fill_color = (174 * 2 / 10, 226 * 2 / 10, 255 * 3 / 10);
                let vignette_range = Some((24, 28));
                let color_key = None; // pre.BLACK if self.noir_spotlight else None
                self._create_display(bgcolor, None, Some(fill_color), vignette_range, color_key)
            }
        
            fn create_moody_display(&self, bgcolor: (u8, u8, u8)) -> Surface {
                self._create_display(bgcolor, Some(255 / 2), None, None, Some(pre::BLACK))
            }
        
            fn create_default_display(&self, bgcolor: (u8, u8, u8)) -> Surface {
                let fill_color = (174 * 2 / 10, 226 * 2 / 10, 255 * 3 / 10);
                let vignette_range = if rand::thread_rng().gen_range(10, 20) { Some((10, 20)) } else { Some((8, 255 / 13)) };
                self._create_display(bgcolor, None, Some(fill_color), vignette_range, None)
            }
        
            fn _create_display(&self, bgcolor: (u8, u8, u8), alpha: Option<u8>, fill_color: Option<(u8, u8, u8)>, vignette_range: Option<(u8, u8)>, color_key: Option<Color>) -> Surface {
                let mut display = Surface::new(pre::DIMENSIONS_HALF, self.blend_flag).convert_alpha();
                if let Some(fill_color) = fill_color {
                    display.fill(fill_color);
                    if let Some(vignette_range) = vignette_range {
                        let vignette_value = match bgcolor {
                            pre::COLOR::BGCOLORDARK => vignette_range.1,
                            pre::COLOR::BGCOLORDARKER => vignette_range.0,
                            _ => vignette_range.1,
                        };
                        pre::Surfaces.compute_vignette(&mut display, vignette_value);
                    }
                }
                if let Some(alpha) = alpha {
                    display.set_alpha(alpha);
                }
                if let Some(color_key) = color_key {
                    display.set_colorkey(color_key);
                }
                display
            }
        }
        
        let display_config = GameDisplayConfig {
            dreamlike: false,
            noir: true,
            moody: false,
            blend_flag: BLEND_ALPHA_SDL2,
        };
        
        let display_3 = display_config.create_display(self.bgcolor);


"""
