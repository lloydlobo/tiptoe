import itertools as it
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum, auto
from functools import lru_cache, reduce
from typing import Final, Sequence, Tuple, Union

import pygame as pg

#########
# TYPES #


# This typehint is used when a function would return an RGBA table.
# note: ported from pygame source file: _common.py
RGBAOutput = Tuple[int, int, int, int]
ColorValue = Union[pg.Color, int, str, Tuple[int, int, int], RGBAOutput, Sequence[int]]


class EntityKind(Enum):
    PLAYER = "player"
    ENEMY = "enemy"
    PORTAL = "portal"


class TileKind(Enum):
    DECOR = "decor"
    GRASS = "grass"
    LARGE_DECOR = "large_decor"
    PORTAL = "portal"
    SPAWNERS = "spawners"
    STONE = "stone"


class SpawnerKind(Enum):
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


##########
# ASSETS #


@dataclass
class Assets:
    @dataclass
    class AnimationMiscAssets:
        particle: dict[str, Animation]

    @dataclass
    class AnimationEntityAssets:
        player: dict[str, Animation]
        enemy: dict[str, Animation]

        @property
        def elems(self):
            return {EntityKind.PLAYER.value: self.player, EntityKind.ENEMY.value: self.enemy}

        # skipping error handling for performance
        def __getitem__(self, key: str) -> dict[str, Animation]:
            # match key:
            #     case EntityKind.PLAYER.value: return self.player
            #     case EntityKind.ENEMY.value: return self.enemy
            #     case _: raise ValueError(f"expected valid AnimationAssets key. got {key}")
            return self.elems[key]

    entity: dict[str, pg.Surface]
    misc_surf: dict[str, pg.SurfaceType]
    misc_surfs: dict[str, list[pg.SurfaceType]]
    tiles: dict[str, list[pg.Surface]]
    animations_entity: AnimationEntityAssets
    animations_misc: AnimationMiscAssets


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

    return [load_img(os.path.join(path, img_name), with_alpha, colorkey) for img_name in sorted(os.listdir(path))]


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
            assert len(s) == (n - 1)
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


# fmt: off
# flags: debugging, etc
DEBUG_EDITOR_ASSERTS= True
DEBUG_EDITOR_HUD    = True

DEBUG_GAME_ASSERTS  = True
DEBUG_GAME_CACHEINFO= False
DEBUG_GAME_HUD      = False
DEBUG_GAME_PROFILER = False
DEBUG_GAME_STRESSTEST = False
# fmt: on


# fmt: off
CAMERA_SPEED        = 2  # use with editor camera move fast around the world
FPS_CAP             = 60
RENDER_SCALE        = 2  # for editor
SCALE               = 0.5
TILE_SIZE           = 16
# fmt: on


# fmt: off
SCREEN_WIDTH        = 640
SCREEN_HEIGHT       = 480

DIMENSIONS          = (SCREEN_WIDTH, SCREEN_HEIGHT)  # ratio: (4/3) or (1.3333333333333333)
DIMENSIONS_HALF     = (int(SCREEN_WIDTH * SCALE), int(SCREEN_HEIGHT * SCALE)) # 340,240  # 640/480==4/3 | 853/480==16/9
# fmt: on


# fmt: off
CAPTION             = "tiptoe"
CAPTION_EDITOR      = "tiptoe level editor"
ENTITY_PATH         = os.path.join("src", "data", "images", "entities")
FONT_PATH           = None
IMAGES_PATH         = os.path.join("src", "data", "images")
INPUT_PATH          = None  # InputState
MAP_PATH            = os.path.join("src", "data", "maps")
SOUNDS_PATH         = None
SPRITESHEET_PATH    = None
# fmt: on


# colors:
# fmt: off
BEIGE               = (15, 20, 25)
BG_DARK             = hsl_to_rgb(234, 0.1618, 0.0618)
BG_DARKER           = hsl_to_rgb(234, 0.1618, 0.0328)
BLACK               = (0, 0, 0)
BLACKMID            = (1, 1, 1)
CHARCOAL            = (10, 10, 10)
CREAM               = hsl_to_rgb(0, 0.1618, 0.618)
GRAY                = hsl_to_rgb(0, 0, 0.5)
GREEN               = hsl_to_rgb(120, 1, 0.25)
MIDNIGHT            = (2, 2, 3)
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
class AutotileID(Enum):
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
    tuple(sorted([( 1, 0), ( 0, 1)                 ])): AutotileID.TOPLEFT.value      or 0,  # ES
    tuple(sorted([( 1, 0), ( 0, 1), (-1, 0)        ])): AutotileID.TOPCENTER.value    or 1,  # ESW
    tuple(sorted([(-1, 0), ( 0, 1)                 ])): AutotileID.TOPRIGHT.value     or 2,  # WS
    tuple(sorted([(-1, 0), ( 0,-1), ( 0, 1)        ])): AutotileID.MIDDLERIGHT.value  or 3,  # WSN
    tuple(sorted([(-1, 0), ( 0,-1)                 ])): AutotileID.BOTTOMRIGHT.value  or 4,  # WN
    tuple(sorted([(-1, 0), ( 0,-1), ( 1, 0)        ])): AutotileID.BOTTOMCENTER.value or 5,  # WNE
    tuple(sorted([( 1, 0), ( 0,-1)                 ])): AutotileID.BOTTOMLEFT.value   or 6,  # EN
    tuple(sorted([( 1, 0), ( 0,-1), ( 0, 1)        ])): AutotileID.MIDDLELEFT.value   or 7,  # ENS
    tuple(sorted([( 1, 0), (-1, 0), ( 0, 1), (0,-1)])): AutotileID.MIDDLECENTER.value or 8,  # EWSN
}
# fmt: on

###################
# PYGAME SURFACES #


def generate_surf(count: int, color: tuple[int, int, int] = BLACK, size: tuple[int, int] = (TILE_SIZE, TILE_SIZE), colorkey: ColorValue = BLACK) -> list[pg.Surface]:
    _with_variation = False
    return [
        (
            surf := pg.Surface(size),
            surf.set_colorkey(colorkey),
            surf.fill(color if not _with_variation else (color[0] + int(math.sin(i) + i * 10) // 10, color[1] + int(math.cos(i) + i * 10) // 10, color[2] + i * (1 or 2))),
        )[0]
        # ^ after processing pipeline, select first [0] Surface in tuple
        for i in range(count)
    ]


#############
# ITERUTILS #


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
    # NOTE: this is just for learning

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
