import os
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Final, Sequence, Tuple, Union

import pygame as pg

#########
# TYPES #

# This typehint is used when a function would return an RGBA table.
# note: ported from pygame source file: _common.py
RGBAOutput = Tuple[int, int, int, int]
ColorValue = Union[pg.Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]


class EntityKind(Enum):
    ENEMY = "enemy"
    PLAYER = "player"


class TileKind(Enum):
    GRASS = "grass"
    STONE = "stone"


@dataclass
class Movement:
    """False == 0 and True == 1"""

    left: bool
    right: bool


@dataclass
class Collisions:
    """False == 0 and True == 1"""

    up: bool
    down: bool
    left: bool
    right: bool


##########
# ASSETS #


@dataclass
class Assets:
    surface: dict[str, pg.Surface]
    surfaces: dict[str, list[pg.Surface]]
    animation: None  # TODO


def load_img(path: str, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None) -> pg.Surface:
    """Load and return a pygame Surface image. Note: Ported from DaFluffyPotato's pygpen lib"""
    img = pg.image.load(path).convert_alpha() if with_alpha else pg.image.load(path).convert()
    if colorkey is not None:
        img.set_colorkey(colorkey)
    return img


def load_imgs(path: str, with_alpha: bool = False, colorkey: Union[tuple[int, int, int], None] = None) -> list[pg.Surface]:
    """
    listdir lists all image filenames in path directory and loads_img over each and returns list of pg.Surfaces
        @example:
            load_imgs(path=os.path.join(IMAGES_PATH, "tiles", "grass"), with_alpha=True, colorkey=BLACK)
    """
    return [
        load_img(
            os.path.join(path, img_name),
            with_alpha,
            colorkey,
        )
        for img_name in sorted(os.listdir(path))
    ]


###############
# COORDINATES #     (px and grid systems)


@lru_cache(maxsize=None)
def calc_pos_to_loc(x: int, y: int, offset: tuple[int, int] | None) -> str:
    """
    calc_pos_to_loc convert position with offset to json serializable key for game level map
    Returns a string with `_lru_cache_wrapper` that is a 'Constants shared by all lru cache instances'
    """
    if offset:
        return f"{ x-offset[0] };{ y-offset[1] }"
    return f"{ x };{ y }"


##########
# COLORS #


@lru_cache(maxsize=None)
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

    if (n := len(s)) and n == 7:
        if s[0] == "#":
            s = s[1:]
            assert len(s) == (n - 1)
        else:
            raise ValueError(f"expected valid hex format string. got {s}")

    return (int(s[0:2], base), int(s[2:4], base), int(s[4:6], base))


@lru_cache(maxsize=None)
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
    if h == 360:
        h = 0
    assert 0 <= h < 360
    assert 0 <= s <= 1
    assert 0 <= l <= 1

    # calculate C, X, and m
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2

    rp: float
    gp: float
    bp: float

    # determine which sector of the hue circle the color is in
    match (h // 60) % 6:  # integer division and modulo for efficient sector mapping
        case 0:
            rp, gp, bp = c, x, 0.0
        case 1:
            rp, gp, bp = x, c, 0.0
        case 2:
            rp, gp, bp = 0.0, c, x
        case 3:
            rp, gp, bp = 0.0, x, c
        case 4:
            rp, gp, bp = x, 0.0, c
        case _:  # default case
            rp, gp, bp = c, 0.0, x

    # convert to 0-255 scale
    # note: round() instead of int() helps in precision. e.g. gray 127 -> 128
    return (round((rp + m) * 255), round((gp + m) * 255), round((bp + m) * 255))


#############
# CONSTANTS #

# fmt: off
CAMERA_SPEED        = 2  # use with editor camera move fast around the world
FPS_CAP             = 60
SCALE               = 0.5
TILE_SIZE           = 16
# fmt: on

# fmt: off
SCREEN_WIDTH        = 640
SCREEN_HEIGHT       = 480
DIMENSIONS          = (SCREEN_WIDTH, SCREEN_HEIGHT)
DIMENSIONS_HALF     = (int(SCREEN_WIDTH * SCALE), int(SCREEN_HEIGHT * SCALE))
# fmt: on


# fmt: off
CAPTION             = "tiptoe"
CAPTION_EDITOR      = "tiptoe level editor"
IMAGES_PATH         = os.path.join("src", "data", "images")
ENTITY_PATH         = os.path.join("src", "data", "images", "entities")
FONT_PATH           = None
INPUT_PATH          = None  # InputState
SOUNDS_PATH         = None
SPRITESHEET_PATH    = None
# fmt: on


BG_DARK = hsl_to_rgb(234, 0.1618, 0.0618)
BLACK = (0, 0, 0)
CHARCOAL = (10, 10, 10)
CREAM = hsl_to_rgb(0, 0.1618, 0.618)  # awesome color for player
DARK_AYU_NAVY = (15, 20, 25)
GRAY = hsl_to_rgb(0, 0, 0.5)
GREEN = hsl_to_rgb(120, 1, 0.25)
RED = hsl_to_rgb(0, 0.618, 0.328)
SILVER = hsl_to_rgb(0, 0, 0.75)
TRANSPARENT = (0, 0, 0, 0)
WHITE = (255, 255, 255)


NEIGHBOR_OFFSETS = {
    # fmt: off
    (-1,-1), ( 0,-1), ( 1,-1),
    (-1, 0), ( 0, 0), ( 1, 0),
    (-1, 1), ( 0, 1), ( 1, 1),
    # fmt: on
}
LEN_NEIGHBOR_OFFSETS = 9

PHYSICS_TILES = {TileKind.GRASS, TileKind.STONE}
