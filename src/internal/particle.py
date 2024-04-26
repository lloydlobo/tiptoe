from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

import pygame as pg

from internal import prelude as pre


if TYPE_CHECKING:
    from tiptoe import Game

_FLAG_PERF_WIP = 0


class Particle:
    def __init__(self, game: Game, p_kind: pre.ParticleKind, pos: pg.Vector2, velocity: pg.Vector2 = pg.Vector2(0, 0), frame: int = 0) -> None:
        self.game = game
        self.kind = p_kind
        self.pos = pos
        self.velocity = velocity

        self.animation = self.game.assets.animations_misc.particle[self.kind.value].copy()
        self.animation.frame = frame

        # WIP: HISTORY: memory pool or reuse particle to avoid GC overhead
        if _FLAG_PERF_WIP:
            self.is_used = False
            self.pos_id = int(pos.x), int(pos.y)
            self.q_pos_id: deque[tuple[int, int]] = deque()
            self.unique_pos_id: set[tuple[int, int]] = set()

    def update(self) -> bool:
        """Update particle and returns bool if particle must disappear"""
        kill_animation = False

        if _FLAG_PERF_WIP:
            self.q_pos_id.appendleft(self.pos_id)
            self.unique_pos_id.add(self.pos_id)

        if self.animation.done:
            kill_animation = True

            if _FLAG_PERF_WIP:
                self.is_used = kill_animation  # maybe add this is second arg of tuple to collections recording history

        # Do this one axis at a time?
        #   self.pos.x += self.velocity.x
        #   self.pos.y += self.velocity.y
        self.pos += self.velocity

        if _FLAG_PERF_WIP:
            self.pos_id = int(self.pos.x), int(self.pos.y)

        self.animation.update()

        return kill_animation

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        img = self.animation.img()
        surf.blit(
            img,
            (
                self.pos.x - offset[0] - img.get_width() // 2,
                self.pos.y - offset[1] - img.get_height() // 2,
            ),
        )  # use center of the image as origin for particle ^
