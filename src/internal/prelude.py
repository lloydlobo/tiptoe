import os
from dataclasses import dataclass
from enum import Enum
from typing import Final, Sequence, Tuple, Union

import pygame as pg

FPS_CAP = 60
CAMERA_SCROLL_SPEED = 2  # use with editor camera move fast around the world

SCALE = 0.5
SCREEN_WIDTH, SCREEN_HEIGHT = 640, 480
DIMENSIONS = (SCREEN_WIDTH, SCREEN_HEIGHT)
DIMENSIONS_HALF = (int(SCREEN_WIDTH * SCALE), int(SCREEN_HEIGHT * SCALE))

CAPTION = "tiptoe"

DATA_IMAGES_PATH = os.path.join("src", "data", "images")
ENTITY_PATH = None
FONT_PATH = None
INPUT_PATH = None  # InputState
SOUNDS_PATH = None
SPRITESHEET_PATH = None

TILE_SIZE: Final[int] = 16

BLACK = (0, 0, 0)
CHARCOAL = (10, 10, 10)
RED = (255, 0, 0)
TRANSPARENT = (0, 0, 0, 0)
WHITE = (255, 255, 255)

# This typehint is used when a function would return an RGBA table
# Note: Ported from pygame source file: _common.py
RGBAOutput = Tuple[int, int, int, int]
ColorValue = Union[pg.Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]


class TileKind(Enum):
    GRASS = "grass"
    STONE = "stone"


class EntityKind(Enum):
    PLAYER = "player"
    ENEMY = "enemy"


@dataclass
class Movement:
    """False == 0 and True == 1"""

    left: bool
    right: bool
    # use these for editor camera movement scroll
    #   up: bool
    #   down: bool
