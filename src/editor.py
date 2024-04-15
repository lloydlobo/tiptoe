import sys

import pygame as pg

from internal.prelude import (
    BG_VIOLET,
    BLACK,
    CAMERA_SPEED,
    CAPTION,
    CAPTION_EDITOR,
    DIMENSIONS,
    DIMENSIONS_HALF,
    FPS_CAP,
    TILE_SIZE,
    TRANSPARENT,
    WHITE,
    Movement,
)


class Editor:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption(CAPTION_EDITOR)
        self.screen = pg.display.set_mode(DIMENSIONS)
        self.display = pg.Surface(DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_outline = pg.Surface(DIMENSIONS_HALF)

        self.font = pg.font.SysFont("monospace", TILE_SIZE)

        self.clock = pg.time.Clock()

        self.movement = Movement(left=False, right=False)

        self.scroll = pg.Vector2(0.0, 0.0)

    def run(self) -> None:
        bg = pg.Surface(DIMENSIONS)  # TODO: use actual background image
        bg.fill(BG_VIOLET)

        while True:
            self.display.fill(TRANSPARENT)
            self.display_outline.blit(bg, (0, 0))

            self.scroll.x += (-self.movement.left + self.movement.right) * CAMERA_SPEED
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

            # DEBUG

            # show fps
            text = self.font.render(f"FPS {self.clock.get_fps():4.0f}", False, WHITE, None)
            self.screen.blit(text, (TILE_SIZE, TILE_SIZE * 1))
            # show render_scroll
            text = self.font.render(f"RSCROLL {str(render_scroll).ljust(4)}", False, WHITE, None)
            self.screen.blit(text, (TILE_SIZE, TILE_SIZE * 2))

            pg.display.flip()
            self.clock.tick(FPS_CAP)


if __name__ == "__main__":
    Editor().run()
