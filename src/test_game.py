# file: test_game.py

# Usage:
#   fd -e py . | entr -cprs 'python src/test_game.py'

import inspect
import logging
import time
import unittest
from typing import Any, Never, NoReturn
from unittest.mock import patch

import game
from internal.prelude import CONFIG_PATH, UserConfig


FILENAME: str = __import__('pathlib').Path(__file__).name
glogger: logging.Logger = logging.getLogger("test_game")

FLAG_OPEN_WINDOW: bool = False  # Suppress tests that opens pygame display screen
TRACELOG: bool = False


def lineno() -> int:
    """Return the current line number."""
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        return -1
    return frame.f_back.f_lineno


class TestWarmup(unittest.TestCase):
    def test_absolute_values(self):
        self.assertEqual(abs(10), 10)
        self.assertEqual(abs(-10), 10)
        self.assertEqual(abs(0), 0)


class TestGameEnums(unittest.TestCase):
    def setUp(self) -> None:
        if TRACELOG:
            print(f"\n{time.process_time():.5f}", f'[info] in {FILENAME}: line {lineno()}:', 'Starting: ', self)
        super().setUp()

    def tearDown(self) -> None:
        if TRACELOG:
            print(f"{time.process_time():.5f}", f'[info] in {FILENAME}: line {lineno()}:', 'Finished: ', self)
        super().tearDown()

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
            print(f"\n{time.process_time():.5f}", f'[info] in {FILENAME}: line {lineno()}:', 'Starting: ', self)
        super().setUp()

    def tearDown(self) -> None:
        if TRACELOG:
            print(f"{time.process_time():.5f}", f'[info] in {FILENAME}: line {lineno()}:', 'Finished: ', self)
        super().tearDown()

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
            print(f"\n{time.process_time():.5f}", f'[info] in {FILENAME}: line {lineno()}:', 'Starting: ', self)
        super().setUp()

    def tearDown(self) -> None:
        if TRACELOG:
            print(f"{time.process_time():.5f}", f'[info] in {FILENAME}: line {lineno()}:', 'Finished: ', self)
        super().tearDown()

    def test_game_quit_exit(self):
        import pygame

        pygame.quit()  # Cleanup any initialized test side-effects
        self.assertFalse(pygame.get_init())
        pygame.init()
        self.assertTrue(pygame.get_init())
        with self.assertRaises(SystemExit):
            game.quit_exit()

    def test_game_quit_exit_raises_runtime_error(self):
        self.assertFalse(__import__('pygame').get_init())
        with self.assertRaises(RuntimeError):  # Assume we forgot to initialize pygame before quitting
            game.quit_exit()
        with self.assertRaises(AssertionError):
            assert 0, 'reachable only while testing after RunTimeError'


def mock_quit_exit(*kwargs: Any):
    glogger.debug("@patch('game.quit_exit', mock_quit_exit)")
    print(
        f"{time.process_time():.5f} [info] patched Callable game.quit_exit in {FILENAME} on line {lineno()} while testing: {kwargs}"
    )


class TestGameSetMainScreen(unittest.TestCase):
    def test_game_set_main_screen_to_none(self):
        """FIXME: This passes but is not what we want.... So, screen is none is possible when:
        - Player quits the game
        - While initial Launcher loading??
        - At any assertions or exceiptions.. not implemented yet
        """
        g = game.Game()
        screen = None
        if got := game.set_mainscreen(g, scr=screen):
            want = (game.AppState.GAMESTATE, game.GameState.NEXTLEVEL)
            self.assertTupleEqual(got, want)
        self.assertIs(g.mainscreen, None)

    @unittest.skipUnless(FLAG_OPEN_WINDOW, "Skipping test that opens pygame display screen")
    def test_game_set_main_screen_to_startscreen_with_manual_sigkill(self):
        g = game.Game()
        screen = game.StartScreen(g)
        self.assertTupleEqual((screen.w, screen.h), game.pre.DIMENSIONS_HALF)
        self.assertIs(screen.menuitem_offset, 0)
        self.assertIs(screen.selected_menuitem, game.MenuItemType.PLAY)
        self.assertTrue(screen.running)

        with self.assertRaises(SystemExit):
            got = game.set_mainscreen(g, scr=screen)
            self.assertTrue(False, "unreachable since, internally quit_exit() calls sys.exit()")
            self.assertIs(g.mainscreen, screen)
            if got:
                want = (game.AppState.GAMESTATE, game.GameState.NEXTLEVEL)
                self.assertTupleEqual(got, want)

    @unittest.skipUnless(FLAG_OPEN_WINDOW, "Skipping test that opens pygame display screen")
    def test_set_main_screen_exits_after_gameover(self):
        g = game.Game()
        g.gameover = True
        screen = game.StartScreen(g)

        with self.assertRaises(SystemExit):
            got: Any = None
            try:
                got = game.set_mainscreen(g, scr=screen)
                self.assertTrue(False, "unreachable since, internally quit_exit() calls sys.exit()")
            except SystemExit as e:
                self.assertIs(g.mainscreen, screen)
                self.assertIsNone(got)
                raise e

    @patch('game.quit_exit', mock_quit_exit)
    def test_set_main_screen_patch_quit_exit(self):
        g = game.Game()
        g.gameover = True
        screen = game.StartScreen(g)

        try:
            with self.assertLogs(logger=glogger, level=logging.DEBUG):
                self.assertIsNone(game.quit_exit(), f"expected game.quit_exit(...) patched in {self}")
        except Exception as e:
            self.fail(f"unreachable: {e}")
        finally:  # NOTE: Using finally as `try..else..` block honors the `NoReturn` return type of game.quit_exit()
            if not FLAG_OPEN_WINDOW:
                self.assertIsNone(g.mainscreen)
            else:
                got = game.set_mainscreen(g, scr=screen)
                self.assertIs(g.mainscreen, screen)
                print(f"{time.process_time():.5f} [info] bypassed game.quit_exit in {FILENAME} while testing: {self}")
                if got:
                    want = (game.AppState.MENUSTATE, game.GameState.EXIT)
                    self.assertTupleEqual(got, want)
                    return
                self.assertIsNone(got)


if __name__ == "__main__":
    print(f"{time.process_time():.5f} [info] {time.monotonic_ns()} {time.ctime()} in {FILENAME}")
    unittest.main()
