# file: animation.py

from typing import Final, List

import pygame as pg


class Animation:
    """Animation is a class that holds a list of images and a duration for each
    image to be displayed.

    Example::

        animation = Animation([image1, image2, image3], img_dur=5)

    Note: if img_dur is not specified then it defaults to 5
    Note: if loop is not specified then it defaults to True
    """

    def __init__(self, images: List[pg.Surface], img_dur: int = 5, loop: bool = True) -> None:
        self.images: Final[List[pg.Surface]] = images  # this is not copied
        self.loop = loop
        self._img_duration: Final = img_dur

        self._img_duration_inverse: Final = 1 / self._img_duration  # perf:minor
        self._total_frames: Final = self._img_duration * len(self.images)

        self.done = False  # fixed: should always be False at __init__

        self.frame = 0

    def copy(self) -> "Animation":
        """Return a copy of the animation."""
        return Animation(self.images, self._img_duration, self.loop)

    def update(self) -> None:
        """Increment frames like a movie screen roll or a marque."""
        if self.loop:
            self.frame += 1
            self.frame %= self._total_frames
        else:
            self.frame = min(self.frame + 1, self._total_frames - 1)
            if self.frame >= self._total_frames - 1:
                self.done = True

    def img(self) -> pg.SurfaceType:
        """Returns current image to render in animation cycle.

        Similar to render phase in the '__init__ -> update -> render' cycle
        """
        return self.images[int(self.frame * self._img_duration_inverse)]
