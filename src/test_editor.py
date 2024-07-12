# file: test_editor.py

# Usage:
#   fd -e py . | entr -cprs make -j4 test

import time
import unittest

import pygame


class TestEditor(unittest.TestCase):
    def setUp(self) -> None:
        if pygame.get_init():
            pygame.quit()
        return super().setUp()

    def tearDown(self) -> None:
        if pygame.get_init():
            pygame.quit()
        return super().tearDown()

    def test_editor_init_with_level_id(self):
        import editor
        from game import quit_exit

        ed_with_level_id = editor.Editor(level_id=1)
        self.assertEqual(ed_with_level_id.level, 1)
        with self.assertRaises(SystemExit):
            quit_exit()

    def test_editor_init_without_level_id(self):
        import editor
        from game import quit_exit

        ed_without_level_id = editor.Editor(level_id=None)
        self.assertEqual(ed_without_level_id.level, 0)
        with self.assertRaises(SystemExit):
            quit_exit()


if __name__ == "__main__":
    from pathlib import Path

    FILENAME: str = Path(__file__).name
    print(f"{time.process_time():.5f}", "[debug]", time.monotonic_ns(), time.ctime(), f"in {FILENAME}")

    unittest.main()
