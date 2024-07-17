# file: test_game.py

import inspect
import logging
import re
import time
import unittest
from typing import Any, NoReturn
from unittest.mock import patch

import pytest

import game
from internal.prelude import CONFIG_PATH, DDEBUG, UserConfig


glogger: logging.Logger = logging.getLogger("test_game")


# Suppress tests that opens pygame display screen
FLAG_OPEN_WINDOW: bool = False

TRACELOG: bool = False

FILENAME: str = __import__('pathlib').Path(__file__).name


def tracelog(level: str, message: str) -> None:
    return (
        logging.log(lvl, msg)
        if (
            lvl := logging.getLevelNamesMapping().get(level),
            _LINE_ := (-1 if ((cf := inspect.currentframe()) is None or cf.f_back is None) else cf.f_back.f_lineno),
            msg := f"{time.process_time():.5f} {_LINE_} {message}",
        )
        and lvl
        else logging.log(logging.DEBUG, msg) if TRACELOG else None
    )


def lineno() -> int:
    """Return the current line number."""
    frame = inspect.currentframe()
    if frame is None or frame.f_back is None:
        return -1
    return frame.f_back.f_lineno


class TestGameEnums:
    def test_game_enums(self):
        assert game.AppState.GAMESTATE.value == 1
        assert game.GameState.PLAY.value == 1

    def test_game_intenums(self):
        assert game.FontType.XS == 0
        assert game.MenuItemType.PLAY == 0
        assert game.SettingsNavitemType.MUTE_MUSIC == 0


class TestGameFileIO:
    @pytest.mark.skipif(DDEBUG, reason="Expected debug flags in prelude to be set as follows for public build")
    def test_game_get_user_config(self):
        cfg: UserConfig
        cfg = game.get_user_config(CONFIG_PATH)
        assert cfg
        assert cfg.window_width == 960
        assert cfg.window_height == 630
        assert 16 <= cfg.star_count <= 64
        assert cfg.screenshake


class TestGameSyscalls(unittest.TestCase):
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
        # Assume we forgot to initialize pygame before quitting
        with self.assertRaises(RuntimeError, msg=re.escape('pygame.error: pygame is not initialized')):
            self.assertNotIsInstance(
                game.quit_exit(),
                type(NoReturn),
                f'assertion is reachable if quit_exit is patched while testing to prevent RunTimeError via NoReturn',
            )


def mock_quit_exit(*args: Any):
    _LINE_ = (-1) if ((frame := inspect.currentframe()) is None or frame.f_back is None) else (frame.f_back.f_lineno)
    glogger.debug(
        "@patch('game.quit_exit', mock_quit_exit)\n"
        f"[info] patched Callable game.quit_exit in {FILENAME} on line {_LINE_} while testing: {repr(args)}"
    )


class TestGameSetMainScreen:
    """FIXME: This passes but is not what we want.... So, screen is none is possible when:
    - Player quits the game
    - While initial Launcher loading??
    - At any assertions or exceiptions.. not implemented yet
    """

    def test_game_set_main_screen_to_none(self):
        g = game.Game()
        screen = None
        if got := game.set_mainscreen(g, scr=screen):
            want = (game.AppState.GAMESTATE, game.GameState.NEXTLEVEL)
            assert got == want
        assert g.mainscreen is None

    # @unittest.skipUnless(FLAG_OPEN_WINDOW, "Skipping test that opens pygame display screen")
    @pytest.mark.skipif(not FLAG_OPEN_WINDOW, reason="Skipping test that opens pygame display screen")
    def test_game_set_main_screen_to_startscreen_with_manual_sigkill(self):
        g = game.Game()
        screen = game.StartScreen(g)
        assert (screen.w, screen.h) == game.pre.DIMENSIONS_HALF
        assert screen.menuitem_offset == 0
        assert screen.selected_menuitem == game.MenuItemType.PLAY
        assert screen.running

        with pytest.raises(SystemExit):
            _ = game.set_mainscreen(g, scr=screen)
            pytest.fail("unreachable since quit_exit() calls sys.exit()")

    # @unittest.skipUnless(FLAG_OPEN_WINDOW, "Skipping test that opens pygame display screen")
    @pytest.mark.skipif(not FLAG_OPEN_WINDOW, reason="Skipping test that opens pygame display screen")
    def test_set_main_screen_exits_after_gameover(self):
        g = game.Game()
        g.gameover = True
        screen = game.StartScreen(g)

        with pytest.raises(SystemExit):
            _ = game.set_mainscreen(g, scr=screen)
            pytest.fail("unreachable since quit_exit() calls sys.exit()")
        assert g.mainscreen == screen

    @patch('game.quit_exit', mock_quit_exit)
    def test_patch_quit_exit(self):
        g = game.Game()
        g.gameover = True
        screen = game.StartScreen(g)

        try:
            with pytest.raises(AssertionError):
                assert game.quit_exit() != None, f"expected game.quit_exit(...) patched in {self}"
        except Exception as e:
            pytest.fail(f"unreachable: {e}")
        finally:  # NOTE: Using finally as `try..else..` block honors the `NoReturn` return type of game.quit_exit()
            if not FLAG_OPEN_WINDOW:
                assert (g.mainscreen) is None
            else:
                got = game.set_mainscreen(g, scr=screen)
                assert g.mainscreen == screen
                tracelog("INFO", f"bypassed game.quit_exit in {FILENAME} while testing: {self}")
                assert got is None if (not got) else (got == (game.AppState.MENUSTATE, game.GameState.EXIT))


if __name__ == "__main__":
    tracelog("INFO", f"{time.monotonic_ns()} {time.ctime()} in {FILENAME}")
    unittest.main()
