import os
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import Final, Sequence, Tuple, TypedDict, Union

import pygame as pg

from internal.colors_util import hsl_to_rgb

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


BG_VIOLET = hsl_to_rgb(234, 0.1618, 0.0618)
BLACK = (0, 0, 0)
CHARCOAL = (10, 10, 10)
DARK_AYU_NAVY = (15, 20, 25)
GRAY = hsl_to_rgb(0, 0, 0.5)
RED = hsl_to_rgb(0, 0.618, 0.328)
CREAM = hsl_to_rgb(0, 0.1618, 0.618)  # awesome color for player
SILVER = hsl_to_rgb(0, 0, 0.75)
TRANSPARENT = (0, 0, 0, 0)
WHITE = (255, 255, 255)


LEN_NEIGHBOR_OFFSETS = 9
NEIGHBOR_OFFSETS = {
    # fmt: off
    (-1,-1), ( 0,-1), ( 1,-1),
    (-1, 0), ( 0, 0), ( 1, 0),
    (-1, 1), ( 0, 1), ( 1, 1),
    # fmt: on
}

# This typehint is used when a function would return an RGBA table.
# note: ported from pygame source file: _common.py

# fmt: off
RGBAOutput          = Tuple[int, int, int, int]
ColorValue          = Union[pg.Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]
# fmt: on


# fmt: off
class EntityKind(Enum):
    ENEMY           = "enemy"
    PLAYER          = "player"

class TileKind(Enum):
    GRASS           = "grass"
    STONE           = "stone"

PHYSICS_TILES       = {TileKind.GRASS, TileKind.STONE}
# fmt: on

# fmt: off

@dataclass
class Movement:
    """False == 0 and True == 1"""
    left            : bool
    right           : bool

@dataclass
class Collisions:
    """False == 0 and True == 1"""
    up              : bool
    down            : bool
    left            : bool
    right           : bool

# fmt: on


@lru_cache(maxsize=None)
def calc_pos_to_loc(x: int, y: int, offset: tuple[int, int]) -> str:
    """
    calc_pos_to_loc convert position with offset to json serializable key for game level map
    Returns a string with `_lru_cache_wrapper` that is a 'Constants shared by all lru cache instances'
    """
    return f"{ x-offset[0] };{ y-offset[1] }"
