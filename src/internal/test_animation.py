# file: animation.py

import logging
import re
import time
from typing import Any, Final, List, Sequence, Tuple, TypeAlias

import pygame as pg
import pytest
from _pytest.python_api import approx
from hypothesis import assume, example, given
from hypothesis import strategies as st
from hypothesis.strategies._internal.collections import ListStrategy


"""class Animation

    Note: if img_dur is not specified then it defaults to 5
    Note: if loop is not specified then it defaults to True
"""

_IMAGES_COUNT: Final[int] = 3

try:
    from internal._testutils import try_assert
    from internal.prelude import Animation, Coordinate2
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
    msg = f'should keep updating till next image frame can be used: {repr(default_animation)}. got: {repr(updates_counter)}'
    assert default_animation.img() == default_animation.images[1], msg


def test_animation_init_without_images():
    animation = Animation(images=list(), img_dur=5, loop=True)

    with pytest.raises(IndexError, match=re.escape('list index out of range')):
        _ = animation.images[0]
        pytest.fail('unreachable')


def generate_strategy_dataobject_image(img_size: Coordinate2 = (16, 16)):
    """NOTE: For 'list' of 'list of _Surface images'
    Alternatives:
     - return st.builds(st.lists, result)
     - return st.lists(result, min_size=min_size)
    """
    imgs: Sequence[_Surface] = [pg.Surface(img_size), pg.Surface(img_size)]
    result: st.SearchStrategy[_Surface] = st.sampled_from(imgs)
    return result


@given(
    imgs=st.lists(generate_strategy_dataobject_image(img_size=(32, 32)), min_size=5, max_size=16),
    img_dur=st.integers(5, 32),
    loop=st.booleans(),
)
@example(
    imgs=[pg.Surface((32, 32)), pg.Surface((32, 32)), pg.Surface((32, 32)), pg.Surface((32, 32)), pg.Surface((32, 32))],
    img_dur=12,
    loop=False,
)
def test_animation_init_assume_same_images_dimensions(imgs: List[Any], img_dur: int, loop: bool):
    anim = Animation(images=imgs, img_dur=img_dur, loop=loop)
    n_imgs: Final = len(imgs)
    anim_total_frames: Final = img_dur * n_imgs
    want: _Surface
    got: _Surface
    iteration = 0
    anim_frame = 0
    while iteration < (n_imgs - 1):
        want = anim.images[iteration]
        # NOTE(Lloyd): Check for off-by-one error when range(img_dur+1)
        for _ in range(img_dur):
            assume(anim.update() is None)  # Do the actual work
            anim_frame += 1
            assert anim.frame == anim_frame
        got = anim.img()
        assert got.get_parent() == want.get_parent()
        assert got.get_size() == want.get_size()
        (got_w, got_h) = got.get_size()
        # FIXME(Lloyd): This does not seem right. Does python zip, cover the
        # whole 2D grid pixel coordinate or just when x == y?
        assert all((got.get_at((x, y)) == want.get_at((x, y))) for x, y in zip(range(got_w), range(got_h)))
        if loop:
            assert not anim.done
        else:
            assert anim.done if (anim.frame >= anim_total_frames) else not anim.done
        iteration += 1
