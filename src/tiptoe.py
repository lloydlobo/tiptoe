import sys

import pygame as pg

FPS = 60

SCALE = 0.5
SCREEN_WIDTH, SCREEN_HEIGHT = 640, 480
SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
SIZE_HALF = (int(SCREEN_WIDTH * SCALE), int(SCREEN_HEIGHT * SCALE))

TILE_SIZE = 16

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
TRANSPARENT = (0, 0, 0, 0)


class Game:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption("tiptoe")
        self.screen = pg.display.set_mode(SIZE)
        self.display = pg.Surface(SIZE_HALF, pg.SRCALPHA)
        self.display_outline = pg.Surface(SIZE_HALF)

        self.font = pg.font.SysFont("monospace", TILE_SIZE)

        self.clock = pg.time.Clock()

    def run(self) -> None:
        bg = pg.Surface(SIZE)  # TODO: use actual background image
        bg.fill(BLACK)

        while True:
            self.display.fill(TRANSPARENT)
            self.display_outline.blit(bg, (0, 0))

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()

            # pixel art effect
            self.screen.blit(
                pg.transform.scale(self.display_outline, self.screen.get_size()), (0, 0)
            )

            # show fps
            text = self.font.render(
                f"FPS: {self.clock.get_fps():4.0f}", False, WHITE, None
            )
            self.screen.blit(text, (TILE_SIZE, TILE_SIZE))

            pg.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
