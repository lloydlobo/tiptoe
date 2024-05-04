import cProfile  # pyright: ignore

import internal.prelude as pre  # pyright: ignore
from game import Game, StartScreen  # pyright: ignore


class Launcher(Game):
    def __init__(self) -> None:
        super().__init__()

    def start(self) -> None:
        startscreen = StartScreen(self)
        self.set_mainscreen(startscreen)


def main():
    launcher = Launcher()
    launcher.start()


if __name__ == "__main__":
    main()


# def main():
#     if pre.DEBUG_GAME_PROFILER:
#         cProfile.run("Game().load_level(0)", sort="cumulative")
#         cProfile.run("Game().run()", sort="cumulative")
#
#     game = Game()
#
#     if 0:
#         loading_screen(game)
#     start_screen = StartScreen(game).run()
#     # game.set_screen(start_screen)
#
#
# if __name__ == "__main__":
#     main()
