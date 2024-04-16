from __future__ import annotations

from typing import TYPE_CHECKING

import pygame as pg

if TYPE_CHECKING:
    from tiptoe import Game


class Particle:
    def __init__(self, game: Game, p_type: str, pos: pg.Vector2, velocity: pg.Vector2 = pg.Vector2(0, 0), frame: int = 0) -> None:
        self.game = game
        self.type = p_type
        self.pos = pos.copy()
        self.velocity = velocity.copy()

        self.animation = self.game.assets.animations_misc.particle[p_type].copy()
        self.animation.frame = frame

    def update(self) -> bool:
        # flag: determines when must particle disappear
        kill_animation = False  # note: keep this local to avoid clashing with other particles

        if self.animation.done:
            kill_animation = True

        # note: important to do this one axis at a time
        self.pos.x += self.velocity.x
        self.pos.y += self.velocity.y

        self.animation.update()

        return kill_animation

    def render(self, surf: pg.Surface, offset: tuple[int, int] = (0, 0)) -> None:
        # image dest: use center of the image as origin
        img = self.animation.img()
        img_center = pg.Vector2(img.get_rect().center) or pg.Vector2(img.get_width() // 2, img.get_height() // 2)

        surf.blit(img, dest=(self.pos - offset - img_center // 2))
