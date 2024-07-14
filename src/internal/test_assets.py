# file: test_assets.py

import logging
from typing import Dict, Tuple

import pygame as pg
import pytest
from hypothesis import assume

from src.internal.prelude import EntityKind


try:
    from src.internal.assets import Assets
    from src.internal.prelude import COUNT, IMGS_PATH, Animation
except ImportError or OSError as e:
    logging.error(f'something went wrong while importing module(s): {e}')
    raise e
else:
    print(f'imported modules')


@pytest.fixture(scope="module")
def assets() -> Assets:
    ret: Tuple[int, int] = pg.init()
    assert assume(ret == (5, 0))
    assert isinstance(
        pg.display.set_mode((960, 630), pg.DOUBLEBUF), pg.SurfaceType
    ), 'cannot load the spritesheet: cannot convert without pygame.display initialized'
    return Assets.initialize_assets()


def test_assets_initialization(assets: Assets):
    assert isinstance(assets, Assets)

    # Test entity surfaces
    assert all(x in assets.entity for x in ('enemy', 'player'))
    assert isinstance(assets.entity['enemy'], pg.Surface)
    assert isinstance(assets.entity['player'], pg.Surface)

    # Test misc surfaces
    assert all(x in assets.misc_surf for x in ('gun', 'projectile'))
    assert isinstance(assets.misc_surf['gun'], pg.Surface)
    assert isinstance(assets.misc_surf['projectile'], pg.Surface)

    # Test tile surfaces
    assert all(x in assets.tiles for x in ('granite', 'grass'))
    assert len(assets.tiles['granite']) > 0
    assert all(isinstance(tile, pg.Surface) for tile in assets.tiles['granite'])
    assert len(assets.tiles['grass']) > 0
    assert all(isinstance(tile, pg.Surface) for tile in assets.tiles['grass'])

    # Test animations
    enemy_actions = ('idle', 'run', 'sleeping')
    player_actions = ('idle', 'run', 'jump', 'wallslide')
    particle_animation_kind = ('flame', 'flameglow', 'particle')

    assert all((key in keyval) and isinstance(keyval.get(key), Animation) 
        for key in enemy_actions if (keyval := assets.animations_entity.enemy))  # fmt: skip
    assert all((key in keyval) and isinstance(keyval.get(key), Animation) 
        for key in player_actions if (keyval := assets.animations_entity.player))  # fmt: skip
    assert all((key in keyval) and isinstance(keyval.get(key), Animation) 
        for key in particle_animation_kind if (keyval := assets.animations_misc.particle))  # fmt: skip

    # Test animation entity property
    enemydict = assets.animations_entity.elems[EntityKind.ENEMY.value]
    playerdict = assets.animations_entity.elems[EntityKind.PLAYER.value]
    assert isinstance(enemydict, Dict) and isinstance(playerdict, Dict)
    assert enemy_actions == tuple(assets.animations_entity.elems[EntityKind.ENEMY.value].keys())
    assert player_actions == tuple(assets.animations_entity.elems[EntityKind.PLAYER.value].keys())

    # Test specific properties
    assert len(assets.misc_surfs['stars']) == COUNT.STAR
    assert all(isinstance(star, pg.Surface) and (star.get_size() == (2, 2)) for star in assets.misc_surfs['stars'])

    # Test editor view
    editor_assets = assets.editor_view
    assert 'spawners' in editor_assets.tiles
    assert len(editor_assets.tiles['spawners']) >= 4  # player, enemy, two portal types

    # Test file loading
    assert (IMGS_PATH / "spritesheets" / "enemy.png").exists()
    assert (IMGS_PATH / "spritesheets" / "player.png").exists()
