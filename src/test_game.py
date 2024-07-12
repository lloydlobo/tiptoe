# file: test_game.py

# Usage:
#   fd -e py . | entr -cprs 'python src/test_game.py'

import inspect
import time
import unittest
from pathlib import Path

import game
from internal.prelude import CONFIG_PATH, UserConfig


FILENAME: str = Path(__file__).name
TRACELOG: bool = True


def lineno() -> int:
    result: int
    cf = inspect.currentframe()
    if not cf:
        result = -1
        return result
    cfback = cf.f_back
    if not cfback:
        result = -1
        return result
    result = cfback.f_lineno
    assert isinstance(result, int)
    return result


class TestWarmup(unittest.TestCase):
    def test_positive_number(self):
        self.assertEqual(abs(10), 10)

    def test_negative_number(self):
        self.assertEqual(abs(-10), 10)

    def test_zero(self):
        self.assertEqual(abs(0), 0)


class TestGameEnums(unittest.TestCase):
    def setUp(self) -> None:
        if TRACELOG:
            print(f"\n{time.process_time():.5f}", f'[debug] in {FILENAME}: line {lineno()}:', 'Starting: ', self)
        return super().setUp()

    def tearDown(self) -> None:
        if TRACELOG:
            print(f"{time.process_time():.5f}", f'[debug] in {FILENAME}: line {lineno()}:', 'Finished: ', self)
        return super().tearDown()

    def test_game_enums(self):
        self.assertEqual(game.AppState.GAMESTATE.value, 1)
        self.assertEqual(game.GameState.PLAY.value, 1)

    def test_game_intenums(self):
        self.assertEqual(game.FontType.XS, 0)
        self.assertEqual(game.MenuItemType.PLAY, 0)
        self.assertEqual(game.SettingsNavitemType.MUTE_MUSIC, 0)


class TestGameFileIO(unittest.TestCase):
    def setUp(self) -> None:
        if TRACELOG:
            print(f"\n{time.process_time():.5f}", f'[debug] in {FILENAME}: line {lineno()}:', 'Starting: ', self)
        return super().setUp()

    def tearDown(self) -> None:
        if TRACELOG:
            print(f"{time.process_time():.5f}", f'[debug] in {FILENAME}: line {lineno()}:', 'Finished: ', self)
        return super().tearDown()

    def test_game_get_user_config(self):
        cfg: UserConfig = game.get_user_config(CONFIG_PATH)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.window_width, 960)
        self.assertEqual(cfg.window_height, 630)
        self.assertGreaterEqual(cfg.star_count, 16)
        self.assertLessEqual(cfg.star_count, 64)
        self.assertTrue(cfg.screenshake)


class TestGameSyscalls(unittest.TestCase):
    def setUp(self) -> None:
        if TRACELOG:
            print(f"\n{time.process_time():.5f}", f'[debug] in {FILENAME}: line {lineno()}:', 'Starting: ', self)
        return super().setUp()

    def tearDown(self) -> None:
        if TRACELOG:
            print(f"{time.process_time():.5f}", f'[debug] in {FILENAME}: line {lineno()}:', 'Finished: ', self)
        return super().tearDown()

    def test_game_quit_exit(self):
        import pygame

        self.assertFalse(pygame.get_init())
        pygame.init()
        self.assertTrue(pygame.get_init())
        with self.assertRaises(SystemExit):
            game.quit_exit()

    def test_game_quit_exit_raises_runtime_error(self):
        import pygame

        self.assertFalse(pygame.get_init())
        # NOTE(Lloyd): Assume we forget to initialize pygame before quit call
        #   pygame.init()
        with self.assertRaises(RuntimeError):
            game.quit_exit()


if __name__ == "__main__":
    print(f"{time.process_time():.5f}", "[debug]", time.monotonic_ns(), time.ctime())
    unittest.main()

