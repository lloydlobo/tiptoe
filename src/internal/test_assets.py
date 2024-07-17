# file: test_assets.py

import logging
from pathlib import Path
from typing import Any, Dict, Final, Iterable, Tuple

import pygame as pg
import pytest
from hypothesis import assume


try:
    from internal.assets import Assets
    from internal.prelude import (
        COUNT,
        IMGS_PATH,
        SIZE,
        Animation,
        EntityKind,
    )
except ImportError or OSError as e:
    logging.error(f'something went wrong while importing module(s): {e}')
    raise e
else:
    print(f'imported modules')


@pytest.fixture(scope="module")
def assets() -> Assets:
    assert assume(pg.init() == (5, 0))
    assert isinstance(
        pg.display.set_mode((960, 630), pg.DOUBLEBUF), pg.SurfaceType
    ), 'cannot load the spritesheet: cannot convert without pygame.display initialized'
    return Assets.initialize_assets()


def all_surfaces(surfaces: Iterable[Any]):
    return all(isinstance(surface, pg.Surface) for surface in surfaces)


def test_assets_initialization(assets: Assets):
    assert isinstance(assets, Assets)
    assert all(
        all(isinstance(category_dict.get(item), pg.Surface) for item in items)
        for category, items in {'entity': ('enemy', 'player'), 'misc_surf': ('gun', 'projectile')}.items()
        if (category_dict := getattr(assets, category))
    )
    assert all(
        (tile_type in assets.tiles) and assets.tiles[tile_type] and all_surfaces(assets.tiles[tile_type])
        for tile_type in ('granite', 'grass')
    )
    animation_tests: Final = {
        'enemy': ('idle', 'run', 'sleeping'),
        'player': ('idle', 'run', 'jump', 'wallslide'),
        'particle': ('flame', 'flameglow', 'particle'),
    }
    assert all(
        all(isinstance(anim.get(action), Animation) for action in actions)
        for (anim_type, actions) in animation_tests.items()
        if (anim := getattr(assets.animations_entity, anim_type, None) or getattr(assets.animations_misc, anim_type))
    )
    for e_kind in (EntityKind.ENEMY, EntityKind.PLAYER):  # Test animation entity property
        anim_elems = assets.animations_entity.elems[e_kind.value]
        assert isinstance(anim_elems, Dict) and set(animation_tests[e_kind.value.lower()]) == set(anim_elems.keys())
    stars = assets.misc_surfs['stars'];  assert all_surfaces(stars);  # fmt: skip
    assert len(stars) == COUNT.STAR and all(star.get_size() == SIZE.STAR for star in stars);  # fmt: skip
    editor_assets = assets.editor_view  # vvvv player, enemy, two portal types vvvvv
    assert editor_assets.tiles.get('spawners') and len(editor_assets.tiles['spawners']) >= 4


@pytest.mark.parametrize("entity", ['enemy', 'player'])
def test_file_loading(entity: str):
    assert Path(IMGS_PATH, "spritesheets", f"{entity}.png").exists()
