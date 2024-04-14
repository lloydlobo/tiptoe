import os
from typing import Union

import pygame as pg

from internal.prelude import ColorValue


def load_img(path: str, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None) -> pg.Surface:
    """Load and return a pygame Surface image. Note: Ported from DaFluffyPotato's pygpen lib"""
    img = pg.image.load(path).convert_alpha() if with_alpha else pg.image.load(path).convert()
    if colorkey is not None:
        img.set_colorkey(colorkey)
    return img


# HACK: we aren't using base path so beware
def load_imgs(path: str, with_alpha: bool = False, colorkey: Union[tuple[int, int, int], None] = None) -> list[pg.Surface]:
    return [load_img(img_name, with_alpha, colorkey) for img_name in sorted(os.listdir(path))]
