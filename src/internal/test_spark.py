# file: test_spark.py
#
# Usage:
#       pytest --verbose src/internal/test_spark.py

import logging
import math

import pygame as pg
import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st


# NOTE(Lloyd): Errors occur due to using imports:
#   LIKE THIS (error):            from internal import prelude as pre
#   INSTEAD USE THIS (no error):  from . import prelude as pre
try:
    from src.internal._testutils import (
        st_floats_rgb,
        st_integers_rgb_val,
        st_tuples_floats_rgb,
        st_tuples_integers_rgb,
    )
    from src.internal.prelude import WHITE, ColorValue, Number
    from src.internal.spark import Spark
except ImportError or OSError as e:
    logging.error(f'Import error: {e}')
    raise

# -----------------------------------------------------------------------------
# Module Helper Functions Implementation
# -----------------------------------------------------------------------------


def create_spark(pos: pg.Vector2 = pg.Vector2(0, 0), angle: Number = 0, speed: Number = 0, color: ColorValue = WHITE):
    return Spark(pg.Vector2(pos[0], pos[1]), angle, speed, color)


# -----------------------------------------------------------------------------
# Module Test Functions Implementation
# -----------------------------------------------------------------------------


def test_warmup_assume_pygame_version():
    assume(f'{pg.ver}' == '2.5.1')


def test_spark_init_default():
    spark = create_spark()
    assert isinstance(spark.pos, pg.Vector2) and (spark.angle == 0) and (spark.speed == 0)
    assert spark.color == WHITE == (255, 255, 255)


@pytest.mark.parametrize("initial_speed, expected_speed", [(1, 0.9), (0.05, 0), (0, 0)])
def test_spark_update(initial_speed: Number, expected_speed: Number):
    spark = create_spark(speed=initial_speed)
    animation_stopped = spark.update()
    assert math.isclose(spark.speed, expected_speed, abs_tol=1e-6)
    assert animation_stopped == (expected_speed == 0)


@given(pos=st.tuples(st.floats(-1000, 1000), st.floats(-1000, 1000)), angle=st.floats(0, 2 * math.pi), speed=st.floats(0, 60))  # fmt: skip
@example(pos=(0.0, 0.0), angle=0.0, speed=0.0625)
@example(pos=(1.0, 0.0), angle=0.0, speed=1.0)
def test_spark_position_update(pos: pg.Vector2, angle: Number, speed: Number):
    spark = create_spark(pos, angle, speed)
    initial_pos: pg.Vector2 = spark.pos.copy();  assert isinstance(initial_pos, pg.Vector2);  # fmt: skip
    animation_stopped = spark.update()
    assert (animation_stopped if (spark.speed <= 0) else (not animation_stopped)), 'want spark animation to stop if speed is 0 or not moving'  # fmt: skip
    want_x, want_y = (initial_pos.x + math.cos(angle) * speed), (initial_pos.y + math.sin(angle) * speed)
    abs_tol: float = (1e-1 + 1e-2);  assert math.isclose(1.9, 2.0, abs_tol=abs_tol);  # fmt: skip
    assert math.isclose(spark.pos.x, want_x, abs_tol=abs_tol) and math.isclose(spark.pos.y, want_y, abs_tol=abs_tol)


@given(w=st.integers(16, 960), h=st.integers(16, 960))
def test_spark_render_modifies_surface_not_full_black(w: int, h: int):
    spark, surf = create_spark(), pg.Surface((w, h))
    spark.render(surf)
    assert any(surf.get_at((x, y)) != (0, 0, 0, 255) for x in range(100) for y in range(100)), 'Check if the surface has been modified (not completely black)'  # fmt: skip


@pytest.mark.skip(reason='I do not understand why this works')
@given(w=st.integers(min_value=16, max_value=48), h=st.integers(min_value=16, max_value=48))
def test_spark_render_modifies_surface_is_full_default_white(w: int, h: int):
    spark, surf = create_spark(), pg.Surface((w, h))
    spark.render(surf)
    assert 4 == sum((surf.get_at((x, y)) == pg.Color(255, 255, 255, 255)) for x in range(w) for y in range(h))


@given(c_int=st_tuples_integers_rgb(), c_float=st_tuples_floats_rgb(), c_mix=st.tuples(st_integers_rgb_val(), st_floats_rgb(), st_integers_rgb_val()))  # fmt: skip
def test_spark_color_assigns(c_int: pg.Color, c_float: pg.Color, c_mix: pg.Color):
    for color in (c_int, c_float, c_mix):
        assert create_spark(color=color).color == color
