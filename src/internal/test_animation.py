# file: animation.py

import logging
from typing import Any, Final, List, Sequence, Tuple, TypeAlias

import pygame as pg
import pytest
from _pytest.python_api import approx
from hypothesis import assume


_IMAGES_COUNT: Final[int] = 3


try:
    from src.internal._testutils import try_assert
    from src.internal.prelude import Animation
except ImportError or OSError as e:
    logging.error(f'something went wrong while importing module(s): {e}')
    raise


# Type aliases
_Surface: TypeAlias = pg.surface.Surface


class MockSurface:
    def __init__(self, size: Tuple[int, int] = (10, 10)):
        self.size = size


@pytest.fixture(scope='module')
def pygame_init():
    pg.init()
    yield
    pg.quit()


@pytest.fixture
def mock_images() -> Sequence[_Surface | MockSurface]:
    result: Sequence[MockSurface] = [MockSurface() for _ in range(_IMAGES_COUNT)]
    assert isinstance(result, Sequence) and isinstance(result[0], MockSurface)
    with pytest.raises(AssertionError):
        assert isinstance(result[0], _Surface)
    return result  # pyright: ignore[reportReturnType]


@pytest.fixture
def default_animation(mock_images: List[_Surface]) -> Animation:
    result = Animation(mock_images)
    return result


def test_animation_init(default_animation: Animation, mock_images: Sequence[_Surface]):
    assert isinstance(default_animation, Animation) and isinstance(mock_images, Sequence)
    assert default_animation.images == mock_images
    assert default_animation._img_duration == 5  # pyright: ignore[reportPrivateUsage]
    assert default_animation.loop is True
    assert default_animation.done is False
    assert default_animation.frame == 0


def test_animation_copy(default_animation: Animation):
    copied_animation = default_animation.copy()
    assert default_animation is not copied_animation
    for x in (default_animation, copied_animation):
        assert x.images;  assert x.loop;  assert x._img_duration;  # pyright: ignore[reportPrivateUsage] # fmt: skip
    for i, (a, b) in enumerate(zip(default_animation.images, copied_animation.images)):
        assert hash(a) == hash(b), repr((i, a, b))
    assert default_animation.images == copied_animation.images;  assert default_animation.loop == copied_animation.loop;  assert default_animation._img_duration == copied_animation._img_duration;  # pyright: ignore[reportPrivateUsage] # fmt: skip


@pytest.mark.parametrize('loop, expected_frame, expected_done', [(True, 0, False), (False, 5, True)])
def test_animation_update(mock_images: Sequence[_Surface], loop: bool, expected_frame: int, expected_done: bool):
    assert isinstance(mock_images, List)
    animation = Animation(mock_images, img_dur=2, loop=loop)
    for _ in range(6):  # Update 6 times (just over one full cycle)
        assert animation.update() == None
    assert animation.frame == expected_frame
    assert animation.done == expected_done


def test_animation_img(default_animation: Animation):
    index = int(default_animation.frame * (1 / default_animation._img_duration))  # pyright: ignore[reportPrivateUsage])
    assert index == 0, repr(index)
    assert default_animation.img() == default_animation.images[index]
    assert assume(default_animation.update() == None)
    assert default_animation.img() == default_animation.images[0]
    assert default_animation.loop

    n_imgs = len(default_animation.images)
    assume(n_imgs == _IMAGES_COUNT)

    updates_counter = n_imgs + 1
    assert updates_counter == sum(
        1
        for _ in range(updates_counter)
        if (
            anim_updated := default_animation.update() is None,
            anim_pending := try_assert(not default_animation.done),
        )
        and assume(anim_updated and anim_pending)
    ), repr(default_animation)
    assert (
        default_animation.img() == default_animation.images[1]
    ), f'should update more till next image frame can be used: {repr(default_animation)}. got: {repr(updates_counter)}'


@pytest.mark.skip(reason="unimplemented")
def test_animation_img_extended(default_animation: Animation):
    raise NotImplementedError
    assert default_animation.loop
    index = int(default_animation.frame * (1 / default_animation._img_duration))  # pyright: ignore[reportPrivateUsage])
    assert index == 0, repr(index)
    assert default_animation.img() == default_animation.images[index]
    assert assume(default_animation.update() == None)
    assert default_animation.img() == default_animation.images[0]

    counter_updates: int

    counter_updates = 0

    for i in range((_IMAGES_COUNT + 1)):
        assert i != (_IMAGES_COUNT + 1)
        if (default_animation.update() is None) and (not default_animation.done):
            counter_updates += 1

    assert default_animation.img() == default_animation.images[1]

    for i in range((_IMAGES_COUNT + 1)):
        assert i != (_IMAGES_COUNT + 1)
        if (default_animation.update() is None) and (not default_animation.done):
            counter_updates += 1
    assert counter_updates == 8

    default_animation.update()
    counter_updates += 1
    assert counter_updates == 9

    got_img = default_animation.img()
    assert got_img != default_animation.images[1]
    assert got_img == default_animation.images[2]

    default_animation.update()
    counter_updates += 1
    default_animation.update()
    counter_updates += 1
    default_animation.update()
    counter_updates += 1
    assert counter_updates == 12
    assert default_animation.img() == default_animation.images[2]

    assert default_animation.loop
    assert len(default_animation.images) == _IMAGES_COUNT


#
#
#


#
#
#


#
#
#
#
