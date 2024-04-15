import sys

import pygame as pg

import internal.prelude as pre


class Editor:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption(pre.CAPTION_EDITOR)
        self.screen = pg.display.set_mode(pre.DIMENSIONS)
        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_outline = pg.Surface(pre.DIMENSIONS_HALF)

        self.font = pg.font.SysFont("monospace", pre.TILE_SIZE)

        self.clock = pg.time.Clock()

        self.movement = pre.Movement(left=False, right=False)

        self.scroll = pg.Vector2(0.0, 0.0)

    def run(self) -> None:
        bg = pg.Surface(pre.DIMENSIONS)  # TODO: use actual background image
        bg.fill(pre.BG_DARK)

        while True:
            self.display.fill(pre.TRANSPARENT)
            self.display_outline.blit(bg, (0, 0))

            self.scroll.x += (-self.movement.left + self.movement.right) * pre.CAMERA_SPEED
            render_scroll = (int(self.scroll.x), int(self.scroll.y))

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

            # pixel art effect
            self.screen.blit(pg.transform.scale(self.display_outline, self.screen.get_size()), (0, 0))

            # DEBUG: HUD

            antialias = True

            # HUD: show fps
            text = self.font.render(f"FPS {self.clock.get_fps():4.0f}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 1))
            # HUD: show render_scroll
            text = self.font.render(f"RSCROLL {str(render_scroll).ljust(4)}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 2))
            # HUD: show self.movement
            text = self.font.render(f"{str(self.movement).ljust(4).upper()}", antialias, pre.GREEN, None)
            self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 3))

            # FINAL DRAWING

            pg.display.flip()  # update whole screen
            _ = self.clock.tick(pre.FPS_CAP)  # note: returns delta time (dt)


if __name__ == "__main__":
    Editor().run()
