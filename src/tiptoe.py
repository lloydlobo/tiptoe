import sys

import pygame as pg

import internal.prelude as pre
from internal.entities import Player
from internal.tilemap import Tilemap


class Game:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption(pre.CAPTION)
        self.screen = pg.display.set_mode(pre.DIMENSIONS)
        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.font_size = 18
        self.font = pg.font.SysFont(name=(pg.font.get_default_font() or "monospace"), size=self.font_size, bold=False)

        self.clock = pg.time.Clock()

        self.movement = pre.Movement(left=False, right=False)

        self.assets = pre.Assets(
            surface=dict(
                # entity
                player=Tilemap.generate_tiles(1, pre.RED, size=(8, pre.TILE_SIZE - 1), alpha=(255 // 2))[0],
                enemy=Tilemap.generate_tiles(1, pre.CREAM, size=(8, pre.TILE_SIZE - 1), alpha=(255 // 2))[0],
            ),
            surfaces=dict(
                # tiles: on grid
                grass=(Tilemap.generate_tiles(9, base_color=pre.GRAY, alpha=64)),
                stone=Tilemap.generate_tiles(9, base_color=pre.SILVER, alpha=64),
                # tiles: off grid
                decor=Tilemap.generate_tiles(4, base_color=pre.WHITE, size=(pre.TILE_SIZE // 2, pre.TILE_SIZE // 2)),  # offgrid (plant,box,..)
                large_decor=Tilemap.generate_tiles(4, base_color=pre.BLACK, size=(pre.TILE_SIZE * 2, pre.TILE_SIZE * 2)),  # offgrid (tree,boulder,bush..)
            ),
            animation=None,  # TODO:
        )

        self.player = Player(self, pg.Vector2(50, 50), pg.Vector2(self.assets.surface[pre.EntityKind.PLAYER.value].get_size()))

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.scroll = pg.Vector2(0.0, 0.0)  # camera origin is top-left of screen

        self.dead = 0  # tracks if the player died -> 'reloads level' - which than resets this counter to zero

    def run(self) -> None:
        bg = pg.Surface(pre.DIMENSIONS)  # TODO: use actual background image
        bg.fill(pre.BG_DARK)
        _camera_parallax_factor = pg.Vector2(0.0625, 0.0625)  # 1/16 (as 16 is a perfect square)

        while True:
            self.display.fill(pre.TRANSPARENT)
            self.display_2.blit(bg, (0, 0))

            # camera: update and parallax
            #
            # 'where we want camera to be' - 'where we are or what we have' / '20',
            # so further player is faster camera moves and vice-versa
            # we can use round on scroll increment to smooth out jumper scrolling & also
            # multiplying by point zero thirty two instead of dividing by thirty
            # if camera is off by 1px not an issue, but rendering tiles could be.
            self.scroll.x += (self.player.rect().centerx - (self.display.get_width() * 0.5) - self.scroll.x) * _camera_parallax_factor.x
            self.scroll.y += (self.player.rect().centery - (self.display.get_height() * 0.5) - self.scroll.y) * _camera_parallax_factor.y
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))

            # tilemap: render
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

            # DEBUG: HUD

            antialias = True

            # HUD: show fps
            text = self.font.render(f"FPS {self.clock.get_fps():4.0f}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 1))
            # HUD: show self.scroll
            text = self.font.render(f"SCROLL {str(self.scroll).ljust(4)}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 2))
            # HUD: show render_scroll
            text = self.font.render(f"RSCROLL {str(render_scroll).ljust(4)}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 3))
            # HUD: show self.movement
            text = self.font.render(f"{str(self.movement).ljust(4).upper()}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 4))
            # HUD: show self.player.pos
            text = self.font.render(f"POS {str(self.player.pos).ljust(4)}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 5))
            # HUD: show self.player.velocity
            text = self.font.render(f"VELOCITY {str(self.player.velocity).ljust(4)}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 6))

            # FINAL DRAWING

            pg.display.flip()  # update whole screen
            _ = self.clock.tick(pre.FPS_CAP)  # note: returns delta time (dt)


if __name__ == "__main__":
    Game().run()
