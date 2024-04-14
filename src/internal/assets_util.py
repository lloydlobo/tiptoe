import os
from dataclasses import dataclass
from typing import Union

import pygame as pg

from internal.prelude import TILE_SIZE, ColorValue, EntityKind, TileKind


@dataclass
class Assets:
    surface: dict[str, pg.Surface]
    surfaces: dict[str, list[pg.Surface]]
    animation: None  # TODO


# @dataclass
# class Assets:
#     player: pg.Surface
#     enemy: pg.Surface
#     grass: list[pg.Surface]
#     stone: list[pg.Surface]
#     decor: list[pg.Surface]
#     large_decor: list[pg.Surface]
#
#     def for_entity(self, key: EntityKind):
#         match key:
#             case EntityKind.PLAYER:
#                 return self.player
#             case EntityKind.ENEMY:
#                 return self.enemy
#                 # Pattern will never be matched for subject type "Never" [reportUnnecessaryComparison]
#                 # case _:
#                 #   sys.exit()
#
#         if not isinstance(key, EntityKind):
#             raise ValueError(f"expected EntityKind. got {type(key)}")
#         else:
#             return pg.Surface((TILE_SIZE, TILE_SIZE))
#
#     def for_tile(self, key: TileKind):
#         if key == TileKind.GRASS:
#             return self.grass
#         elif key == TileKind.STONE:
#             return self.stone


def load_img(path: str, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None) -> pg.Surface:
    """Load and return a pygame Surface image. Note: Ported from DaFluffyPotato's pygpen lib"""
    img = pg.image.load(path).convert_alpha() if with_alpha else pg.image.load(path).convert()
    if colorkey is not None:
        img.set_colorkey(colorkey)
    return img


def load_imgs(path: str, with_alpha: bool = False, colorkey: Union[tuple[int, int, int], None] = None) -> list[pg.Surface]:
    """listdir lists all image filenames in path directory and loads_img over each and returns list of pg.Surfaces"""
    return [
        load_img(
            os.path.join(path, img_name),
            with_alpha,
            colorkey,
        )
        for img_name in sorted(os.listdir(path))
    ]
