import sys

import pygame as pg

SCREEN_WIDTH, SCREEN_HEIGHT = 640, 480
SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
SCALE = 0.5
FPS = 60


class Game:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption("tiptoe")
        self.screen = pg.display.set_mode(SIZE)
        self.clock = pg.time.Clock()

    def run(self) -> None:
        while True:
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()

            pg.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
