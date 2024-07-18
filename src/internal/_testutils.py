# file: _testutils.py

import logging
from collections.abc import Sequence
from functools import partial
from typing import Any

import pygame as pg
import pytest  # pyright: ignore [reportUnusedImport]
from hypothesis import assume, example, given  # pyright: ignore [reportUnusedImport]
from hypothesis import strategies as st

# from internal.prelude import ColorValue

st_integers_rgb_val, st_floats_rgb = partial(st.integers, 0, 255), partial(st.floats, 0, 255)

st_tuples_integers_rgb = partial(st.tuples, st_integers_rgb_val(), st_integers_rgb_val(), st_integers_rgb_val())
st_list_integers_rgb = partial(st.lists, st_integers_rgb_val(), min_size=3, max_size=3)
st_tuples_floats_rgb = partial(st.tuples, st_floats_rgb(), st_floats_rgb(), st_floats_rgb())
st_tuples_integers_rgba = partial(
    st.tuples, st_integers_rgb_val(), st_integers_rgb_val(), st_integers_rgb_val(), st_integers_rgb_val()
)


def is_valid_color_value(color: Any) -> bool:
    if isinstance(color, pg.Color):
        return True
    if (
        isinstance(color, tuple)
        and (len(color) == 3)  # pyright: ignore[reportUnknownArgumentType]
        and all(isinstance(c, int) and (0 <= c <= 255) for c in color)  # pyright: ignore[reportUnknownVariableType]
    ):
        return True
    if (
        isinstance(color, Sequence)
        and (len(color) == 3)  # pyright: ignore[reportUnknownArgumentType]
        and all(isinstance(c, int) and (0 <= c <= 255) for c in color)  # pyright: ignore[reportUnknownVariableType]
    ):
        return True
    return False


def try_assert(arg: Any) -> bool:
    try:
        assert arg, repr(arg)
    except AssertionError as e:
        logging.error(repr((e, arg)))
        return False
    return True
