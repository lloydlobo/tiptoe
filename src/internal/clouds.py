import math
import random
from typing import Final

import pygame as pg

import internal.prelude as pre


class Cloud:
    def __init__(self, img: pg.SurfaceType, pos: pg.Vector2, speed: float, depth: float) -> None:
        self.pos = pos

        self._depth: Final = depth
        self._img: Final = img
        self._speed: Final = speed

        self._img_w: Final = self._img.get_width()
        self._img_h: Final = self._img.get_height()
        # self.time = pg.time
        self.rot = 0

    def update(self) -> None:
        self.rot += round(abs(0.3 + math.atan2(self._speed, self.pos.y)), 2)
        if (_horizontal_only := True) and not _horizontal_only:
            self.pos.x += self._speed
        elif (_verticaly_dominant := True) and _verticaly_dominant:
            self.pos.y -= self._speed

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int]) -> None:
        dest: pg.Vector2 = self.pos - pg.Vector2(offset) * self._depth  # parallax FX
        dest_wrapped: tuple[float, float] = (
            dest.x % (surf.get_width() + self._img_w) - self._img_w,
            dest.y % (surf.get_height() + self._img_h) - self._img_h,
        )
        surf.blit(pg.transform.rotate(self._img, self.rot), dest_wrapped)  # loop around the screen width


class Clouds:
    def __init__(self, cloud_imgs: list[pg.SurfaceType], count: int = 16) -> None:
        _speedmultiplexer: Final = 5
        self._mut_clouds: list[Cloud] = [
            Cloud(
                img=random.choice(cloud_imgs),
                pos=pg.Vector2(random.random() * 99999, random.random() * 99999),
                speed=(random.random() * 0.05 + 0.05) * _speedmultiplexer,
                depth=random.random() * 0.6 + 0.2,
            )
            for _ in range(count)
        ]

    def update(self) -> None:
        for cl in self._mut_clouds:
            cl.update()

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        for cl in self._mut_clouds:
            cl.render(surf, offset)
