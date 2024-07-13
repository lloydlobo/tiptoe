# file: test_prelude.py

"""TODOS

    ### FILE I/O

    TFilesVisitedOpts = Dict[str, (int | Any | None)]
    TFilesVisitedDict = Dict[int, Tuple[float, (str | Path), str]]

    global_files_visited: TFilesVisitedDict = dict()

    import inspect

    def get_current_line() -> int | Any | None:
        if (caller_frame := inspect.currentframe()) and caller_frame:
            if (f_back := caller_frame.f_back) and f_back: return f_back.f_lineno
        return None

    def global_files_visited_update(path: str | Path, opts: Optional[TFilesVisitedOpts] = None) -> int | None:
        if "--debug" in sys.argv:
            count = len(global_files_visited.items())
            global_files_visited.update({count: (time(), path, f"{opts}" if opts else f"{opts=}")})
            return count + 1
        return None

    DONE:
        _callable_sound = pg.mixer.Sound
        def load_sound(path: Path, opts: Optional[TFilesVisitedOpts] = None) -> pg.mixer.Sound:
            global_files_visited_update(path, opts=(opts if opts else dict(file_=__file__, line_=get_current_line())))
            return _callable_sound(path)  # > Callable[Sound]

    _callable_music_load = pg.mixer.music.load
    def load_music_to_mixer(path: Path, opts: Optional[TFilesVisitedOpts] = None) -> None:
        global_files_visited_update(path, (opts if opts else dict(file_=__file__, line_=get_current_line())))
        return _callable_music_load(path)  # > None

    def load_img(path: str | Path, with_alpha: bool = False, colorkey: Union[ColorValue, None] = None) -> pg.Surface:
        path = Path(path)
        global_files_visited_update(path, opts=dict(file_=__file__, line_=get_current_line()))
        img = pg.image.load(path).convert_alpha() if with_alpha else pg.image.load(path).convert()
        if colorkey is not None: img.set_colorkey(colorkey)
        return img

    def load_imgs( path: str, with_alpha: bool = False, colorkey: Union[tuple[int, int, int], None] = None) -> list[pg.Surface]:
        return [ load_img(f"{path}/{img_name}", with_alpha, colorkey) for img_name in sorted(os.listdir(path)) if img_name.endswith(".png")
    ]
"""

import unittest
import wave  # Stuff to parse WAVE files.
from pathlib import Path
from typing import IO, Final, List, TypeAlias

import numpy as np
import pygame as pg

from src.internal.prelude import (
    DIMENSIONS,
    load_img,
    load_imgs,
    load_music_to_mixer,
    load_sound,
)


_File: TypeAlias = str | IO[bytes]  # Ported private `wave._File` from "pyright/dist/typeshed-fallback/stdlib/wave.pyi"
_Sound: TypeAlias = pg.mixer.SoundType
_Surface: TypeAlias = pg.SurfaceType


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


class TestFileIO(unittest.TestCase):
    def setUp(self) -> None:
        pg.init()
        pg.mixer.init()
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


if __name__ == "__main__":
    unittest.main()
