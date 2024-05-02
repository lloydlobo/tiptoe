"""This module contains all the classes, functions and constants used in the
game.

## Classes

* Animation
* AutotileID
* COLOR
* COUNT
* COUNTRANDOMFRAMES
* Collisions
* EntityKind
* Math
* Movement
* Palette
* ParticleKind
* Projectile
* SpawnerKind
* TileKind
* UserConfig

## Functions

* create_circle_surf
* create_surface
* create_surface_withalpha
* create_surfaces
* hex_to_rgb
* hsl_to_rgb
* load_img
* load_imgs
* rects_collidepoint
* surfaces_collidepoint
* surfaces_get_outline_mask_from_surf
* surfaces_vfx_outline_offsets_animation_frames
"""

__all__ = [
    # class
    "Animation",
    "AutotileID",
    "COLOR",
    "COUNT",
    "COUNTRANDOMFRAMES",
    "Collisions",
    "EntityKind",
    "Math",
    "Movement",
    "Palette",
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
    "surfaces_get_outline_mask_from_surf",
    "surfaces_vfx_outline_offsets_animation_frames",
]


import math
import os
from dataclasses import dataclass
from enum import Enum, IntEnum, auto, unique
from functools import lru_cache, partial
from pathlib import Path
from random import randint
from typing import (
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


# import toml


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


@unique
class ParticleKind(Enum):
    """used for class AnimationMiscAssets"""

    FLAME = "flame"
    FLAMEGLOW = "flameglow"
    PARTICLE = "particle"  # player particle


@unique
class EntityKind(Enum):
    PLAYER = "player"
    ENEMY = "enemy"
    # note: is portal an entity? if it can teleport and move then maybe consider it.
    PORTAL = "portal"


@unique  # """Class decorator for enumerations ensuring unique member values."""
class TileKind(Enum):
    DECOR = "decor"
    GRANITE = "granite"
    LARGE_DECOR = "large_decor"
    PORTAL = "portal"
    SPAWNERS = "spawners"
    SPIKE = "spike"
    STONE = "stone"


@unique  # """Class decorator for enumerations ensuring unique member values."""
class SpawnerKind(Enum):
    """Enumerates the spawners that are used in the level editor.

    NOTE: ideally start with 1 (as 0 may be assumed as False) but we used 0,1,2
    as variants for spawner 'tiles' while drawing the map.json via level editor
    in src/editor.py for the sake of the wrapping around all spawner variants,
    e.g. 0 1 2 0 1 2 ..... or it.cycle(...)
    """

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
    """Movement is a dataclass of 4 booleans for each of the 4 cardinal
    directions where movement is possible.

    Note: False == 0 and True == 1

    Example::

        left, right, top, bottom = Movement(True, False, True, False)
    """

    left: bool
    right: bool
    top: bool
    bottom: bool


@dataclass
class Collisions:
    """Collisions is a dataclass of 4 booleans for each of the 4 cardinal
    directions where collisions are possible.

    Note: False == 0 and True == 1

    Example::

        left, right, top, bottom = Collisions(True, False, True, False)
    """

    left: bool
    right: bool
    up: bool
    down: bool


################################################################################
### ANIMATION
################################################################################


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


def load_img(
    path: str, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None
) -> pg.Surface:
    """Load and return a pygame Surface image.

    Note: Ported from DaFluffyPotato's pygpen lib
    """
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
        load_img(f"{Path(path) / img_name}", with_alpha, colorkey)
        for img_name in sorted(os.listdir(path))
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
    window_height: int
    window_width: int
    player_dash: int
    player_jump: int
    player_speed: int
    shadow_range: int
    screenshake: bool
    sound_volume: float
    star_count: int

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
            window_height=int(config_dict.get('window_height', '480')),
            window_width=int(config_dict.get('window_width', '640')),
            player_dash=int(config_dict.get('player_dash', '0')),
            player_jump=int(config_dict.get('player_jump', '0')),
            player_speed=int(config_dict.get('player_speed', '0')),
            screenshake=config_dict.get('screenshake', 'true').lower() == 'true',
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
                for k, v in [l.split(maxsplit=1)]
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

        assert hex_to_rgb("#ff0000") == (255, 0, 0)
        assert hex_to_rgb("#00ff00") == (0, 255, 0)
        assert hex_to_rgb("#0000ff") == (0, 0, 255)
    """
    base: Final = 16

    if (n := len(s)) == 7:
        if s[0] == "#":
            s = s[1:]
            if DEBUG_GAME_ASSERTS:
                assert len(s) == (
                    n - 1
                ), "invalid hexadecimal format"  # Lua: assert(hex_string:sub(2):find("^%x+$"),
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
    return ColorKind(
        round((r_prime + m) * 255), round((g_prime + m) * 255), round((b_prime + m) * 255)
    )


#############
# CONSTANTS #


# flags: debugging, etc
DEBUG_EDITOR_ASSERTS = False
DEBUG_EDITOR_HUD = True

DEBUG_GAME_ASSERTS = True
DEBUG_GAME_PRINTLOG = False
DEBUG_GAME_LOGGING = True
DEBUG_GAME_CACHEINFO = False
DEBUG_GAME_HUD = False
DEBUG_GAME_PROFILER = False
DEBUG_GAME_UNITTEST = False
DEBUG_GAME_STRESSTEST = False


CAMERA_SPEED = 2  # use with editor camera move fast around the world
FPS_CAP = 60
RENDER_SCALE = 2  # for editor
SCALE = 0.5
TILE_SIZE = 16


SCREEN_RESOLUTION_MODE = 0
SCREEN_WIDTH = (960, 640)[SCREEN_RESOLUTION_MODE]
SCREEN_HEIGHT = (630, 480)[SCREEN_RESOLUTION_MODE]

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
CHARCOAL = (10, 10, 10)
GREEN = hsl_to_rgb(120, 1, 0.25)
PINK = hsl_to_rgb(300, 0.26, 0.18)
RED = hsl_to_rgb(0, 0.618, 0.328)
TRANSPARENT = (0, 0, 0, 0)
WHITE = (255, 255, 255)


@dataclass
class Palette:
    """Color Palette.

    GIMP Palette
    #Palette Name: Rust Gold 8
    #Description: This pallete was made based on rust colors and gold tones.
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


@dataclass
class COLOR:
    TRANSPARENTGLOW = (20, 20, 20)

    BACKGROUND = (12, 12, 14) or Palette.COLOR7
    STAR = Palette.COLOR6

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
    PORTAL2 = Palette.COLOR0

    GRANITE = Palette.COLOR7
    STONE = Palette.COLOR6
    SPIKE = (145,145,145) or Palette.COLOR1


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
    STAR = int((69 / 1.618) ** 0.328), int((69 / 1.618) ** 0.328)  # 3.425, 3.425 -> 3, 3

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


AUTOTILE_TYPES = {TileKind.STONE, TileKind.GRANITE}
PHYSICS_TILES = {TileKind.STONE, TileKind.GRANITE}

SPAWNERS_KINDS = {EntityKind.PLAYER, EntityKind.ENEMY, TileKind.PORTAL}  # not used for now


################################################################################
### AUTOTILING
################################################################################


@unique
class AutotileID(IntEnum):
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
    tuple(sorted([(1, 0), (0, 1)])): AutotileID.TOPLEFT or 0,  # ES
    tuple(sorted([(1, 0), (0, 1), (-1, 0)])): AutotileID.TOPCENTER or 1,  # ESW
    tuple(sorted([(-1, 0), (0, 1)])): AutotileID.TOPRIGHT or 2,  # WS
    tuple(sorted([(-1, 0), (0, -1), (0, 1)])): AutotileID.MIDDLERIGHT or 3,  # WSN
    tuple(sorted([(-1, 0), (0, -1)])): AutotileID.BOTTOMRIGHT or 4,  # WN
    tuple(sorted([(-1, 0), (0, -1), (1, 0)])): AutotileID.BOTTOMCENTER or 5,  # WNE
    tuple(sorted([(1, 0), (0, -1)])): AutotileID.BOTTOMLEFT or 6,  # EN
    tuple(sorted([(1, 0), (0, -1), (0, 1)])): AutotileID.MIDDLELEFT or 7,  # ENS
    tuple(sorted([(1, 0), (-1, 0), (0, 1), (0, -1)])): AutotileID.MIDDLECENTER or 8,  # EWSN
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

# import pygame as pg
# from pygame import Rect
# SPIKE_CONFIGS = {
#     'bottom': (16, 6, lambda pos, size, grace: Rect(pos.x + grace / 2, pos.y + (size - 6), 16 - grace, 6)),
#     'top': (16, 6, lambda pos, grace: Rect(pos.x + grace / 2, pos.y, 16 - grace, 6)),
#     'left': (6, 16, lambda pos, grace: Rect(pos.x, pos.y + grace / 2, 6, 16 - grace)),
#     'right': (6, 16, lambda pos, size, grace: Rect(pos.x + (size - 6), pos.y + grace / 2, 6, 16 - grace))
# }
# class MyClass:
#     def __init__(self):
#         self.spike_tiles_hitbox = []
#         for spike in self.tilemap.extract([("spike", v) for v in range(4)], keep=True):
#             cfg = SPIKE_CONFIGS.get(spike.orientation)
#             if not cfg:
#                 raise ValueError(f"Invalid spike orientation: {spike.orientation}")
#             w, h, rect_func = cfg
#             rect = rect_func(spike.pos, pre.TILE_SIZE, _spikegrace)
#             self.spike_tiles_hitbox.append(rect)

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
        # if ofst != (0, 0)
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
    size: tuple[int, int],
    colorkey: tuple[int, int, int] | ColorValue,
    fill_color: tuple[int, int, int] | ColorValue,
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
create_surfaces_partialfn.__doc__ = """New create_surfaces function with partial application of colorkey argument and or other keywords."""


def create_circle_surf(
    size: tuple[int, int], fill_color: ColorValue, colorkey: ColorValue = BLACK
) -> pg.SurfaceType:
    # FIXME:
    """Special case for flameglow particle and should not be used here for
    general circle creation.
    """

    surf = pg.Surface(size).convert()
    ca, cb = iter(size)
    center = ca * 0.5, cb * 0.5
    radius = center[0]
    # rect = pg.draw.circle(surf, BLACK, center, radius * 2)
    _rect = pg.draw.circle(surf, fill_color, center, radius)
    # rect = pg.draw.ellipse(surf, fill_color, rect)
    # rect = pg.draw.ellipse(surf, (127,20,20), rect)
    # rect = pg.draw.circle(surf, (127,20,20), center, radius)
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
    def advance_vec2_ip(vec2: pg.Vector2, angle: SupportsFloatOrIndex, amount: Number) -> None:
        """Advances a 2D vector (pg.Vector2) by a given angle and amount in place.

        Args:
            vec2: The pg.Vector2 object representing the 2D vector to advance.
            angle: The angle in radians to move the vector.
            amount: The distance to move the vector along the specified angle.

        This function modifies the `vec2` object in-place and returns None.
        """
        vec2 += (math.cos(angle) * amount, math.sin(angle) * amount)

    @staticmethod
    def advance_float2_ip(
        point2: list[float], angle: SupportsFloatOrIndex, amount: Number
    ) -> None:
        """Advances a 2D point represented by a list of floats by a given angle and amount in place.

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
    def advance_int2_ip(point2: list[int], angle: SupportsFloatOrIndex, amount: Number) -> None:
        """Advances a 2D point represented by a list of integers by a given angle and amount.

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
