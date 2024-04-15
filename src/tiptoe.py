import math
import os
import sys
from functools import lru_cache
from random import randint

import pygame as pg

from internal.assets_util import Assets, load_img, load_imgs
from internal.entities import Player
# fmt: off
from internal.prelude import (BG_VIOLET, BLACK, CAPTION, CHARCOAL, CREAM,
                              DARK_AYU_NAVY, DIMENSIONS, DIMENSIONS_HALF,
                              FPS_CAP, GRAY, IMAGES_PATH, RED, SILVER,
                              TILE_SIZE, TRANSPARENT, WHITE, ColorValue,
                              EntityKind, Movement)
# fmt: on
from internal.tilemap import Tilemap

# fmt: off
# fmt: on


@lru_cache(maxsize=8)
def generate_tiles(
    count: int,
    base_color: tuple[int, int, int] = BLACK,
    size: tuple[int, int] = (TILE_SIZE, TILE_SIZE),
    colorkey: ColorValue = BLACK,
    alpha: int = 255,
    variance: int = 0,  # (0==base_color) && (>0 == random colors)
) -> list[pg.Surface]:
    """Tip: use lesser alpha to blend with the background fill for a cohesive theme"""

    alpha = max(0, min(255, alpha))  # clamp from less opaque -> fully opaque
    fill = [max(0, min(255, base + randint(-variance, variance))) for base in base_color] if variance else base_color

    return [
        (
            surf := pg.Surface(size),
            surf.set_colorkey(colorkey),
            surf.fill(fill),
            surf.set_alpha(alpha),
        )[0]
        # ^ after processing pipeline, select first [0] Surface in tuple
        for _ in range(count)
    ]


class Game:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption(CAPTION)
        self.screen = pg.display.set_mode(DIMENSIONS)
        self.display = pg.Surface(DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(DIMENSIONS_HALF)

        self.font = pg.font.SysFont(pg.font.get_default_font() or "monospace", TILE_SIZE)

        self.clock = pg.time.Clock()

        self.movement = Movement(left=False, right=False)
        # ^ or use simpler self.movement = [False, False]

        self.assets = Assets(
            surface=dict(
                # entity
                player=generate_tiles(1, RED, size=(8, TILE_SIZE - 1), alpha=(255 // 2))[0],
                enemy=generate_tiles(1, CREAM, size=(8, TILE_SIZE - 1), alpha=(255 // 2))[0],
            ),
            surfaces=dict(
                # tiles: on_grid
                grass=(
                    generate_tiles(9, base_color=GRAY, alpha=64)
                    or load_imgs(path=os.path.join(IMAGES_PATH, "tiles", "grass"), with_alpha=True, colorkey=BLACK)
                    #  ^  used as placeholder, if we decide to use spritesheet
                ),
                stone=generate_tiles(9, base_color=SILVER, alpha=64),
                # tiles: off_grid
                decor=generate_tiles(4, base_color=WHITE, size=(TILE_SIZE // 2, TILE_SIZE // 2)),  # offgrid (plant,box,..)
                large_decor=generate_tiles(4, base_color=BLACK, size=(TILE_SIZE * 2, TILE_SIZE * 2)),  # offgrid (tree,boulder,bush..)
            ),
            animation=None,  # TODO:
        )

        self.player = Player(self, pg.Vector2(50, 50), pg.Vector2(self.assets.surface[EntityKind.PLAYER.value].get_size()))
        # self.player = Player(self, pg.Vector2(50, 50), pg.Vector2(16, 16))

        self.tilemap = Tilemap(self, TILE_SIZE)

        self.scroll = pg.Vector2(0.0, 0.0)  # or use [0, 0]

        self.dead = 0  # tracks if the player died -> 'reloads level' - which than resets this counter to zero

    def run(self) -> None:
        bg = pg.Surface(DIMENSIONS)  # TODO: use actual background image
        bg.fill(BG_VIOLET)
        _camera_parallax_factor = 0.05  # or 1/20

        while True:
            self.display.fill(TRANSPARENT)
            self.display_2.blit(bg, (0, 0))

            # camera: update and parallax
            self.scroll.x += self.movement.right - self.movement.left  # * camera_parallax_factor
            self.scroll.y += 0
            render_scroll = pg.Vector2(int(self.scroll.x), int(self.scroll.y))

            self.tilemap.render(self.display, render_scroll)

            # enemy: update and render
            # TODO:

            # player: update and render
            if not self.dead:
                self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
                self.player.render(self.display, render_scroll)
                # debug: collission detection
                #   ta = self.tilemap.tiles_around(tuple(self.player.pos))
                #   pra = self.tilemap.physics_rects_around(tuple(self.player.pos))

            # mask: before particles!!!
            display_mask: pg.Mask = pg.mask.from_surface(self.display)  # 180 alpha to set color of outline
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_silhouette, offset)

            # particles:
            # TODO:

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_LEFT:
                        self.movement.left = True
                    if event.key == pg.K_RIGHT:
                        self.movement.right = True
                    if event.key == pg.K_UP:
                        if self.player.jump():
                            # TODO: play jump sfx
                            pass
                if event.type == pg.KEYUP:
                    if event.key == pg.K_LEFT:
                        self.movement.left = False
                    if event.key == pg.K_RIGHT:
                        self.movement.right = False

            # DISPLAY RENDERING

            # blit display on display_2 and then blit display_2 on
            # screen for depth effect.

            self.display_2.blit(self.display, (0, 0))

            # TODO: screenshake effect via offset for screen blit
            # ...
            self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), (0, 0))  # pixel art effect

            # DEBUG

            # show fps
            text = self.font.render(f"FPS {self.clock.get_fps():4.0f}", False, WHITE, None)
            self.screen.blit(text, (TILE_SIZE, TILE_SIZE * 1))
            # show render_scroll
            text = self.font.render(f"RSCROLL {str(render_scroll).ljust(4)}", False, WHITE, None)
            self.screen.blit(text, (TILE_SIZE, TILE_SIZE * 2))

            # FINAL DRAWING

            pg.display.flip()
            self.clock.tick(FPS_CAP)


if __name__ == "__main__":
    Game().run()
