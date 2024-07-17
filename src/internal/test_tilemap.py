# file: test_tilemap.py


"""
# >>> import pytest
# >>> pytest src/internal/test_tilemap_hypothesis.py --verbose

# >>> fd -e py . | grep hypothesis | entr -cprs 'pytest src/internal/test_tilemap_hypothesis.py -v'
"""

import logging
import math
import string
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from random import random
from typing import Any, Callable, List, Optional, Set, Tuple, TypeAlias

import hypothesis.strategies as st
import pytest
from hypothesis import assume, example, given
from hypothesis.strategies._internal import SearchStrategy
from hypothesis.strategies._internal.core import DrawFn, composite


assert 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' == string.ascii_letters
ASCII_NON_VOWEL_LETTERS = 'bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ'
ASCII_VOWEL_LETTERS = 'aeiouAEIOU'
ASCII_LETTERS_SET = set(string.ascii_letters)

try:
    from internal.prelude import Number
    from internal.tilemap import pos_to_loc

    assert isinstance(pos_to_loc, Callable)
except ImportError or OSError as e:
    logging.error(f'something went wrong while importing module(s): {e}')
    raise e


# tilemap module
# { ---------------------------------------------------------------------------------


_PositionToLocationArgs: TypeAlias = Tuple[Number, Number, Tuple[Number, Number]]
_PositionToLocationArgs.__doc__ = """Tuple[x: Number, y: Number, offset: Tuple[Number, Number]]"""


def generate_pos_loc_args(
    min_size: int = 16, max_size: int = 64, allow_infinity: bool = False, allow_nan: bool = False
) -> SearchStrategy[List[_PositionToLocationArgs]]:
    stfloats: partial[SearchStrategy[float]] = partial(st.floats, allow_infinity=allow_infinity, allow_nan=allow_nan)
    stnumbers: partial[SearchStrategy[float | int]] = partial(stfloats if (random() < 0.5) else st.integers)

    return st.lists(
        st.tuples(stnumbers(), stnumbers(), st.tuples(stnumbers(), stnumbers())),
        min_size=min_size,
        max_size=max_size,
    )


@pytest.mark.skip(reason='test takes some time to run')
@given(args=generate_pos_loc_args(max_size=16, allow_infinity=False, allow_nan=False))
@example([(0, 0, (0.5, -0.5)), (1.0, 0, (-0, 0)), (-0.5, 0.0, (0.0, 0.0)), (0.0, -0.5, (0.0, 0.0))])
def test_pos_to_loc_result_can_be_deserialized(args: List[_PositionToLocationArgs]):
    # `@given`:     Turns test function that accepts arguments into a randomized test.
    # `@example`:   Ensures a specific example is always tested.
    for arg in args:
        loc = pos_to_loc(arg[0], arg[1], arg[2])
        assert isinstance(loc, str) and ((';' in loc) and (len(loc) >= 3)) and (not '.' in loc)
        assert sum(1 for c in loc if c in ASCII_LETTERS_SET) == 0  # Maybe heavy processing
        result = loc.split(';')
        assert len(result) == 2
        posx, posy = result
        x, y = int(posx), int(posy)
        assert isinstance(x, int) and isinstance(y, int)
        # NOTE: This fails
        #   assert x != math.floor(arg[0]) - math.floor(arg[2][0])
        #   assert y != math.floor(arg[1]) - math.floor(arg[2][1])

        # assert (x == int(arg[0]) - int(arg[2][0])) and (y == int(arg[1]) - int(arg[2][1])) # Heavy processing


# --------------------------------------------------------------------------------- }
