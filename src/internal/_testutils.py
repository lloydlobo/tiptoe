# file: _testutils.py

from collections.abc import Sequence
from functools import partial
from typing import Any

import pygame as pg
import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st


st_integers_rgb_val, st_floats_rgb = partial(st.integers, 0, 255), partial(st.floats, 0, 255)

st_tuples_integers_rgb = partial(st.tuples, st_integers_rgb_val(), st_integers_rgb_val(), st_integers_rgb_val())
st_list_integers_rgb = partial(st.lists, st_integers_rgb_val(), min_size=3, max_size=3)
# st.lists(st_integers_rgb_val(), min_size=3, max_size=3),
st_tuples_floats_rgb = partial(st.tuples, st_floats_rgb(), st_floats_rgb(), st_floats_rgb())
st_tuples_integers_rgba = partial(
    st.tuples, st_integers_rgb_val(), st_integers_rgb_val(), st_integers_rgb_val(), st_integers_rgb_val()
)


def is_valid_color_value(color: Any) -> bool:
    if isinstance(color, pg.Color):
        return True
    if isinstance(color, tuple) and (len(color) == 3) and all(isinstance(c, int) and (0 <= c <= 255) for c in color):
        return True
    if isinstance(color, Sequence) and (len(color) == 3) and all(isinstance(c, int) and (0 <= c <= 255) for c in color):
        return True
    return False
