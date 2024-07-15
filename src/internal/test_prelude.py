# file: test_prelude.py

import math
import re
import sys
import unittest
import wave  # Stuff to parse WAVE files.
from collections.abc import Sequence
from pathlib import Path
from typing import IO, Any, Dict, Final, List, Tuple, TypeAlias

import numpy as np
import pygame as pg
import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from src.internal import prelude
from src.internal._testutils import (
    is_valid_color_value,
    st_integers_rgb_val,
    st_list_integers_rgb,
    st_tuples_integers_rgb,
    st_tuples_integers_rgba,
)
from src.internal.prelude import (
    DDEBUG,
    DIMENSIONS,
    ColorValue,
    Coordinate2,
    Number,
    RGBAOutput,
    SupportsFloatOrIndex,
    UserConfig,
    global_files_visited,
    global_files_visited_update,
    load_img,
    load_imgs,
    load_music_to_mixer,
    load_sound,
)


# NOTE(Lloyd): Ported private `wave._File` from "pyright/dist/typeshed-fallback/stdlib/wave.pyi"
_File: TypeAlias = str | IO[bytes]
_Sound: TypeAlias = pg.mixer.SoundType
_Surface: TypeAlias = pg.SurfaceType


"""
TODOS::

        ### FILE I/O
        # ---------------------------------------------------------------------

    TODO:

        DDEBUG: Final[bool] = "--debug" in sys.argv

    TODO:

        def get_current_line() -> int | Any | None:
            if (caller_frame := inspect.currentframe()) and caller_frame:
                if (f_back := caller_frame.f_back) and f_back: return f_back.f_lineno
            return None

    TODO:

        def global_files_visited_update(path: str | Path, opts: Optional[TFilesVisitedOpts] = None) -> int | None:
            if "--debug" in sys.argv:
                count = len(global_files_visited.items())
                global_files_visited.update({count: (time(), path, f"{opts}" if opts else f"{opts=}")})
                return count + 1
            return None

    FIXME:

        _callable_music_load = pg.mixer.music.load
        def load_music_to_mixer(path: Path, opts: Optional[TFilesVisitedOpts] = None) -> None:
            global_files_visited_update(path, (opts if opts else dict(file_=__file__, line_=get_current_line())))
            return _callable_music_load(path)  # > None

        # ---------------------------------------------------------------------

"""

# -----------------------------------------------------------------------------
# Test Drawing Functionality
# -----------------------------------------------------------------------------


# Ported from https://renesd.blogspot.com/2019/11/draft-2-of-lets-write-unit-test.html
class TestPgDrawEllipse(unittest.TestCase):
    def test_should_draw_ellipse(self):
        import pygame.draw

        red, black = pygame.Color('red'), pygame.Color('black')
        surf = pygame.Surface((320, 200))  # NOTE: Cannont call .convert() without pygame.display initialized
        surf.fill(black)
        rect = (10, 11, 225, 95)
        pygame.draw.ellipse(surf, red, rect)
        # To preview: # >>> pygame.image.save(surf, "test_prelude_py_draw2_image.png")
        self.assertEqual(surf.get_at((0, 0)), black)
        middle_of_ellipse = (125, 55)
        self.assertEqual(surf.get_at(middle_of_ellipse), red)


# -----------------------------------------------------------------------------
# Test File I/O
# -----------------------------------------------------------------------------


class TestFileIO(unittest.TestCase):
    def setUp(self) -> None:
        pg.mixer.pre_init()
        pg.init()
        self.test_dir = Path("test_assets")
        self.test_dir.mkdir(exist_ok=True)
        return super().setUp()

    def tearDown(self) -> None:
        pg.mixer.quit()
        pg.quit()
        if 0:  # Enable this to check content of the directory manually in the terminal
            __import__('time').sleep(10)
        for file in self.test_dir.glob('*'):
            file.unlink()
        self.test_dir.rmdir()
        return super().tearDown()

    def test_load_img(self):
        IMG_PATH: Path = self.test_dir / 'test_image.png'
        surf = pg.Surface((10, 10))
        pg.image.save(surf, IMG_PATH.__str__())
        # Set up video mode: In load_img, <Surface>.convert() requires video mode to be set.
        # ----------------------------------------------------------------------------
        self.assertTrue(pg.get_init())
        flags = pg.DOUBLEBUF | pg.RESIZABLE | pg.NOFRAME | pg.HWSURFACE  # Copied these flags from ../game.py
        screen = pg.display.set_mode(size=DIMENSIONS, flags=flags); self.assertIsInstance(screen, _Surface);  # fmt: skip
        # ----------------------------------------------------------------------------
        img          = load_img(IMG_PATH); self.assertIsInstance(img, _Surface);  # fmt: skip
        img_alpha    = load_img(IMG_PATH, with_alpha=True); self.assertIsInstance(img, _Surface);  # fmt: skip
        alpha        = img_alpha.get_alpha(); self.assertIsNotNone(alpha); self.assertEqual(alpha, 255);  # fmt: skip
        img_colorkey = load_img(IMG_PATH, colorkey=(255, 0, 255)); self.assertIsInstance(img_colorkey, _Surface);  self.assertEqual(img_colorkey.get_colorkey(), (255, 0, 255, 255));  # fmt: skip

    def test_load_imgs(self):
        for i in range(3):
            IMG_PATH: Path = self.test_dir / f'test_image_{i}.png'
            surf: _Surface = pg.Surface((10, 10)); pg.image.save(surf, IMG_PATH.__str__());  # fmt: skip
        # Set up video mode: In load_img, <Surface>.convert() requires video mode to be set.
        # ----------------------------------------------------------------------------
        self.assertTrue(pg.get_init())
        flags = pg.DOUBLEBUF | pg.RESIZABLE | pg.NOFRAME | pg.HWSURFACE  # Copied these flags from ../game.py
        screen = pg.display.set_mode(DIMENSIONS, flags); self.assertIsInstance(screen, _Surface);  # fmt: skip
        # ----------------------------------------------------------------------------
        images: List[_Surface] = load_imgs(self.test_dir.__str__()); self.assertEqual(len(images), 3);  # fmt: skip
        for img in images:
            self.assertIsInstance(img, _Surface)

    def test_load_sound(self):
        SOUND_PATH: Final[Path] = self.test_dir / 'test_sound.wav'
        sound_array: _Sound
        SAMPLING_FREQ_FRAMERATE = 44100  # sampe rate
        N_CHANNELS = 2  # 2 for stereo, 1 for mono
        SAMP_WIDTH = 2  # 16-bit
        DURATION_SEC = 1
        t = np.linspace(start=0, stop=DURATION_SEC, num=(SAMPLING_FREQ_FRAMERATE * DURATION_SEC), endpoint=False)
        stuttgart_pitch = 440  # A440 -> See also https://en.wikipedia.org/wiki/A440_(pitch_standard)
        note_sinewave = np.sin(stuttgart_pitch * (2 * np.pi) * t)
        audio_ensure_highest_16bit_range = note_sinewave * (2**15 - 1) / np.max(np.abs(note_sinewave))
        audio_16bit = audio_ensure_highest_16bit_range.astype(np.int16)
        stereo_audio = np.column_stack((audio_16bit, audio_16bit))  # Duplicate mono channel
        sound_array = pg.sndarray.make_sound(stereo_audio)  # pyright: ignore[reportUnknownMemberType]
        with wave.open(f=SOUND_PATH.__str__(), mode='w') as sfile:
            sfile.setframerate(SAMPLING_FREQ_FRAMERATE); sfile.setnchannels(N_CHANNELS); sfile.setsampwidth(SAMP_WIDTH);  # fmt: skip
            readable_buffer_data: bytes = sound_array.get_raw(); sfile.writeframesraw(readable_buffer_data)  # fmt: skip
        sound: _Sound = load_sound(SOUND_PATH)
        self.assertIsInstance(sound, _Sound)

    @unittest.skip("implementation bug: If no exception is raised, we assume it loaded successfully")
    def test_load_music_to_mixer_handles_exception_gracefully_on_corrupt_stream(self):
        music_path = self.test_dir / 'test_music.mp3'
        music_path.write_bytes(b'dummy music data')
        # FIXME: Should not raise exception, but handle error gracefully
        with self.assertRaises(Exception):  # > pygame.error: music_drmp3: corrupt mp3 file (bad stream).
            ret: None = load_music_to_mixer(music_path)
            self.fail(f'unreachable: {repr(ret)}')

    @unittest.skip("unimplemented")
    def test_user_config_from_dict(self):
        pass

    def test_user_config_read_user_config(self):
        config_content = """
        window_width        800
        window_height       600
        #-------------------------
        #player_dash        8
        #player_jump        3
        #player_speed       5
        #enemy_jump         3
        #enemy_speed        5
        star_count          18
        ####
        #drop_shadow        true
        #shadow_range       1
        #col_shadow         000000
        blur_enabled        true
        blur_size           5
        blur_passes         2
        blur_vibrancy       0.5
        screenshake         false
        #@@@
        sound_muted         true
        sound_volume        0.7
        music_muted         false
        music_volume        0.6
        """
        config_path = self.test_dir / 'config'
        config_path.write_text(config_content)
        self.assertTrue(config_path.is_file())
        config_dict = UserConfig.read_user_config(config_path)
        self.assertIsNotNone(config_dict)
        if not config_dict:
            self.fail('unreachable')
        self.assertIsInstance(config_dict, Dict)
        self.assertEqual(config_dict['music_volume'], '0.6')
        self.assertEqual(config_dict['star_count'], '18')
        self.assertEqual(config_dict['screenshake'], 'false')
        self.assertEqual(config_dict['sound_muted'], 'true')
        self.assertEqual(config_dict['window_height'], '600')
        self.assertEqual(config_dict['window_width'], '800')
        with self.assertRaises(Exception):
            self.assertEqual(
                config_dict['player_dash'], '8', msg='expected exception while accessing commented-out config-attribute'
            )

    def test_global_files_visited_update_works_with_debug_flag(self):
        sys.argv.append('--debug')
        _path: Path = self.test_dir / 'test.txt'
        result: int | None = global_files_visited_update(_path)
        self.assertIsNotNone(result); self.assertIsInstance(result,int);  # fmt: skip
        self.assertTrue(len(global_files_visited) > 0)
        sys.argv.remove('--debug')


# -----------------------------------------------------------------------------
# Test Global Flags
# -----------------------------------------------------------------------------


class TestDebugFlags:

    def test_truthy_DDEBUG_if_debug_option_stdin_sys_argv(self):
        assert DDEBUG if "--debug" in sys.argv else not DDEBUG

    @pytest.mark.skipif(DDEBUG, reason="Expected debug flags in prelude to be set as follows for public build")
    def test_expect_debug_flags_for_public_build(self):
        # example lines: "skipif(condition): skip the given test if..."
        # or "hypothesis: tests which use Hypothesis", so to get the
        # marker name we split on both `:` and `(`.
        prelude.DEBUG_EDITOR_ASSERTS = False
        prelude.DEBUG_EDITOR_HUD = False
        prelude.DEBUG_GAME_ASSERTS = False
        prelude.DEBUG_GAME_CACHEINFO = False
        prelude.DEBUG_GAME_CAMERA = False
        prelude.DEBUG_GAME_CPROFILE = False
        prelude.DEBUG_GAME_HUD = False
        prelude.DEBUG_GAME_LOGGING = False
        prelude.DEBUG_GAME_PRINTLOG = False
        prelude.DEBUG_GAME_STRESSTEST = False
        prelude.DEBUG_GAME_TRACEMALLOC = False
        prelude.DEBUG_GAME_TRANSITION = False
        prelude.DEBUG_GAME_UNITTEST = False


# -----------------------------------------------------------------------------
# Test Custom Type Aliases
# -----------------------------------------------------------------------------


class TestTypeAliases:

    # Colors
    # -----------------------------------------------------------------------------
    class TestColorValue:

        @given(
            st.one_of(
                st.builds(pg.Color, st_integers_rgb_val(), st_integers_rgb_val(), st_integers_rgb_val()),
                st_tuples_integers_rgb(),
                st_list_integers_rgb(),
            )
        )
        def test_valid_color_value(self, color: ColorValue):
            assert is_valid_color_value(color)

        @given(
            st.one_of(
                st.tuples(st.integers(0, 255), st.integers(0, 255), st.integers(-255, -1)),
                st.lists(st.integers(-255, -1), min_size=3, max_size=3),
                st.tuples(st.integers(0, 255), st.integers(0, 255)),
                st.tuples(st.integers(0, 255), st.integers(0, 255), st.text()),
                st.lists(st.integers(0, 255), min_size=4, max_size=6),
            )
        )
        def test_invalid_color_value(self, color: ColorValue):
            assert not is_valid_color_value(color)

        @given(args=st_tuples_integers_rgba())
        def test_RGBAOutput(self, args: Tuple[int, int, int, int]):
            assert len(args) == 4, repr(RGBAOutput)
            with pytest.raises(TypeError, match=re.escape("Type Tuple cannot be instantiated; use tuple() instead")):
                RGBAOutput(0, 0, 0, 0)  # pyright: ignore[reportCallIssue,reportGeneralTypeIssues]

    # -----------------------------------------------------------------------------

    # Rest of type aliases
    # -----------------------------------------------------------------------------

    @given(st.integers(-(1 << 4096), (1 << 4096)), st.floats(-math.inf, math.inf))
    @example(1, 0.0)
    def test_Number_and_SupportsFloatOrIndex(self, st_int: int, st_float: float):
        assert not isinstance(st_int, float)
        assert not isinstance(st_float, int)
        for test in (st_int, st_float):
            assert isinstance(test, Number)
            assert isinstance(test, SupportsFloatOrIndex)
        assert isinstance((st_int // st_int) if (st_int != 0) else st_int, int)
        assert isinstance((st_float / st_float) if (st_float != 0.0) else st_float, float)

    @pytest.mark.parametrize(
        "c_tuple, c_sequence, c_pygame_vector2",
        [
            ((1, 1), [1, 1], pg.Vector2(1, 1)),
            ((1.11, 1.11), [1.11, 1.11], pg.Vector2(1.11, 1.11)),
            ((1, 0.1), [1, 0.1], pg.Vector2(1, 0.1)),
            ((0.0, 0.0), [0.0, 0.0], pg.Vector2(0.0)),
            (tuple([1, 0.1]), list((1, 0.1)), pg.Vector2(1, 0.1)),
        ],
    )
    def test_coordinate(self,c_tuple: Tuple, c_sequence: Sequence, c_pygame_vector2: pg.Vector2,):  # pyright: ignore[reportMissingTypeArgument,reportUnknownParameterType] # fmt: skip
        """test_coordinate

        FIXME:

            - Sequence[Number] seems buggy since:
              - Coordinate2 *must* have only 2 coordinates
        """
        for coord in (c_tuple, c_sequence, c_pygame_vector2):  # pyright: ignore[reportUnknownVariableType]
            assert (
                isinstance(coord, (tuple, list, pg.Vector2))
                and len(coord) == 2  # pyright: ignore[reportUnknownArgumentType]
                and all(
                    isinstance(x, (int, float, Number)) for x in coord  # pyright: ignore[reportUnknownVariableType]
                )
            )
        assert isinstance(c_tuple, Tuple); assert isinstance(c_sequence, Sequence); assert isinstance(c_pygame_vector2, pg.Vector2);  # fmt: skip
        assert (len(c_tuple) == len(c_sequence) == len(c_pygame_vector2) == 2)  # pyright: ignore[reportUnknownArgumentType] # fmt: skip
        assert (c_tuple[0] == c_sequence[0] == c_pygame_vector2[0]); assert (c_tuple[1] == c_sequence[1] == c_pygame_vector2[1]);  # fmt: skip
        with pytest.raises(TypeError, match=re.escape('Cannot instantiate typing.Union')):
            Coordinate2(0, 0)  # pyright: ignore[reportCallIssue,reportGeneralTypeIssues]

    # -----------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
