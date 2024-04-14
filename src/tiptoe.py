import os
import sys

import pygame as pg

from internal.assets_util import Assets, load_img, load_imgs
from internal.entities import Player
# fmt: off
from internal.prelude import (CAMERA_SCROLL_SPEED, CAPTION, CHARCOAL,
                              DATA_IMAGES_PATH, DIMENSIONS, DIMENSIONS_HALF,
                              FPS_CAP, RED, TILE_SIZE, TRANSPARENT, WHITE,
                              Movement)
# fmt: on
from internal.tilemap import Tilemap


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

        player_sprite = pg.Surface((8, 15)) or load_img(path=os.path.join(DATA_IMAGES_PATH, "entities", "player.png"), with_alpha=True, colorkey=(0, 0, 0))
        player_sprite.fill(RED)
        enemy_sprite = pg.Surface((8, 15)) or load_img(path=os.path.join(DATA_IMAGES_PATH, "entities", "enemy.png"), with_alpha=True, colorkey=(0, 0, 0))
        enemy_sprite.fill(WHITE)

        grass_sprites = load_imgs(path=os.path.join(DATA_IMAGES_PATH, "tiles", "grass"), with_alpha=True, colorkey=(0, 0, 0))
        stone_sprites = load_imgs(path=os.path.join(DATA_IMAGES_PATH, "tiles", "stone"), with_alpha=True, colorkey=(0, 0, 0))
        decor_sprites = load_imgs(path=os.path.join(DATA_IMAGES_PATH, "tiles", "decor"), with_alpha=True, colorkey=(0, 0, 0))
        large_decor_sprites = load_imgs(path=os.path.join(DATA_IMAGES_PATH, "tiles", "large_decor"), with_alpha=True, colorkey=(0, 0, 0))

        self.assets = Assets(
            surface=dict(
                # entity
                player=player_sprite,
                enemy=enemy_sprite,
            ),
            surfaces=dict(
                # tiles
                grass=grass_sprites,
                stone=stone_sprites,
                decor=decor_sprites,
                large_decor=large_decor_sprites,
            ),
            animation=None,
        )

        self.player = Player(self, pg.Vector2(50, 50), pg.Vector2(8, 15))

        self.tilemap = Tilemap(self, TILE_SIZE)

        self.scroll = pg.Vector2(0.0, 0.0)  # or use [0, 0]

        self.dead = 0  # tracks if the player died -> 'reloads level' - which than resets this counter to zero

    def run(self) -> None:
        bg = pg.Surface(DIMENSIONS)  # TODO: use actual background image
        bg.fill(CHARCOAL)
        _camera_parallax_factor = 1 / 20

        while True:
            self.display.fill(TRANSPARENT)
            self.display_2.blit(bg, (0, 0))

            # camera: update and parallax
            self.scroll.x += -self.movement.left + self.movement.right  # * camera_parallax_factor
            render_scroll = pg.Vector2(int(self.scroll.x), int(self.scroll.y))

            self.tilemap.render(self.display, render_scroll)

            # enemy: update and render
            # TODO:

            # player: update and render
            if not self.dead:
                self.player.update(self.tilemap, pg.Vector2(-self.movement.left + self.movement.right, 0))
                self.player.render(self.display, render_scroll)

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
