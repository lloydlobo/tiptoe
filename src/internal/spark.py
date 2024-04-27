import math
from random import randint
from typing import Sequence

import pygame as pg

import internal.prelude as pre


# angle and speed are polar coords for velocity vector
#   - polar coors avoids object moving faster diagonally
#   - need angle where spark is facing
#   - long white diamond shape
#   - slows down and shrinks as it moves
#   - disappears once it stops
#   - size should be proportional to its speed
#   - speed is its timer


class Spark:
    def __init__(self, pos: pg.Vector2, angle: pre.Number, speed: pre.Number, color: pre.ColorValue = pre.WHITE) -> None:
        self.pos = pos
        self.angle = angle
        self.speed = speed
        self.color = color if color else pre.COLOR.FLAME

    def update(self) -> bool:
        """Decay speed and check if it stopped."""
        self.speed = max(0, self.speed - 1)  # decay*dt -> 1 ???
        if self.speed <= 0:
            return True
        pre.Math.advance_vec2(self.pos, self.angle, self.speed)
        return not self.speed

    def log(self):
        """Prints detailed information about the Spark."""
        print(f"Spark: {self.__dict__}")

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        if (_tmp_simple_spark := 0) and _tmp_simple_spark:
            img = pg.Surface(pre.SIZE.STAR).convert()
            img.set_colorkey(pre.BLACK)
            img.fill(self.color)
            surf.blit(img, self.pos - offset)
            return

        x, y = self.pos
        angle = self.angle
        speed = self.speed
        ofx, ofy = offset
        # l, m = iter(offset) # if offest was a list with x,y value to be mutable

        # Calculate spark points
        dega, degc = (angle + 0), (angle + math.pi)
        degb, degd = (angle + (math.pi * 0.5)), (angle - (math.pi * 0.5))
        va = vc = speed * 3 + (0.618 if randint(0, 1) else 0)
        vb = vd = speed * 0.5 + (-0.618 if randint(0, 1) else 0)
        render_points: Sequence[pg.Vector2] = [
            pg.Vector2(x + (math.cos(dega) * va) - ofx, y + (math.sin(dega) * va) - ofy),
            pg.Vector2(x + (math.cos(degb) * vb) - ofx, y + (math.sin(degb) * vb) - ofy),
            pg.Vector2(x + (math.cos(degc) * vc) - ofx, y + (math.sin(degc) * vc) - ofy),
            pg.Vector2(x + (math.cos(degd) * vd) - ofx, y + (math.sin(degd) * vd) - ofy),
        ]

        pg.draw.polygon(surface=surf, color=self.color, points=render_points)
