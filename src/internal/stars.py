import itertools as it
import math
import random
from time import time
from typing import Final

import pygame as pg

import internal.prelude as pre


def rot_function(x: float, _: float | None) -> float:
    """Ported from DaFluffyPotato's mrc.py"""
    return int((math.sin((x * 0.01) + time() * 1.5) - 0.7) * 30) * 0.1


class Star:
    def __init__(self, img: pg.SurfaceType, pos: pg.Vector2, speed: float, depth: float) -> None:
        self.pos = pos

        self._depth: Final = depth
        self._speed: Final = speed
        self._img: Final = img
        self._img_w: Final = self._img.get_width()
        self._img_h: Final = self._img.get_height()

        if pre.DEBUG_GAME_STRESSTEST:
            base: Final = 0.618
            self.rot = 0.0
            self._angles = tuple(map(lambda x: x * 45, range(0, 9)))
            self._rot_reset_cycle: Final[it.cycle[int]] = it.cycle(tuple(it.starmap(pow, ((1, base), (2, base), (3, base), (5, base), (8, base), (13, base), (21, base), (34, base)))))

    def update(self) -> None:
        self.pos.y -= self._speed

        if pre.DEBUG_GAME_STRESSTEST:
            if 350 <= self.rot <= 360:
                self.rot += round(abs(0.3 + math.atan2(self._speed, self.pos.y)), 1) % (1 - rot_function(self.pos.x, self.pos.y))
            else:
                self.rot += round(abs(0.3 + math.atan2(self._speed, self.pos.y)), 1)
        if 0:
            if pre.DEBUG_GAME_STRESSTEST:
                if 354 < self.rot < 357:  # reset fiesty rotation
                    self.rot = int(1 + rot_function(self.pos.y, None))
                if round(abs(self.rot)) in self._angles:  # slingshot
                    self.pos.y -= 2 * next(self._rot_reset_cycle) * self._speed

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int]) -> None:
        dest = self.pos - pg.Vector2(offset) * self._depth  # parallax FX
        dest_wrapped = (dest.x % (surf.get_width() + self._img_w) - self._img_w, dest.y % (surf.get_height() + self._img_h) - self._img_h)

        if pre.DEBUG_GAME_STRESSTEST:
            surf.blit(pg.transform.rotate(self._img, self.rot), dest_wrapped)  # loop around the screen width
        else:
            surf.blit(self._img, dest_wrapped)  # loop around the screen width


class Stars:
    def __init__(self, star_imgs: list[pg.SurfaceType], count: int = 16) -> None:
        # fibs: Final = (2, 3, 5, 8, 13)
        fibs: Final = (3, 5, 8, 13)
        fib_sumavg: Final = sum(fibs) / len(fibs)

        fibs_cycle: Final = it.cycle(fibs)
        speed_multiplier: Final = 0.5  # Star.speed==approx range(0.05:0.10) when 1==speed_multiplier

        self._mut_stars: list[Star] = [
            Star(
                img=random.choice(star_imgs),
                pos=pg.Vector2(random.random() * 99999, random.random() * 99999),
                speed=(random.random() * 0.05 + 0.05) * speed_multiplier * next(fibs_cycle),
                depth=random.random() * 0.618 + min(0.2, round(next(fibs_cycle) / (fib_sumavg * 1.618), 4)),
            )
            for _ in range(count)
        ]

    def update(self) -> None:
        for cl in self._mut_stars:
            cl.update()

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        for cl in self._mut_stars:
            cl.render(surf, offset)
