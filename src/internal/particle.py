from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import pygame as pg

from internal import prelude as pre

if TYPE_CHECKING:
    from game import Game


class Particle:
    def __init__(
        self,
        game: Game,
        p_kind: pre.ParticleKind,
        pos: pg.Vector2,
        velocity: pg.Vector2 = pg.Vector2(0, 0),
        frame: int = 0,
    ) -> None:
        self.game = game
        self.kind = p_kind
        self.pos = pos
        self.velocity = velocity

        self.animation = self.game.assets.animations_misc.particle[self.kind.value].copy()
        self.animation.frame = frame

    def update(self) -> bool:
        """Update particle and returns bool if particle must disappear."""

        kill_animation = False
        if self.animation.done:
            kill_animation = True

        self.pos.x += self.velocity.x
        self.pos.y += self.velocity.y

        self.animation.update()

        return kill_animation

    def render(self, surf: pg.SurfaceType, offset: Tuple[int, int] = (0, 0)) -> None:
        img = self.animation.img()
        surf.blit(
            img,
            (
                self.pos.x - offset[0] - img.get_width() // 2,
                self.pos.y - offset[1] - img.get_height() // 2,
            ),
        )  # use center of the image as origin for particle ^
