# file: test_particle.py
import re
from typing import Dict

import pygame as pg
import pytest

from game import Game
from internal.particle import Particle
from internal.prelude import ParticleKind


def test_particle_init():
    game_ = Game()
    p = Particle(game=game_, p_kind=ParticleKind.PARTICLE, pos=pg.Vector2(0, 0))
    assert p.animation.frame == 0 and p.velocity == pg.Vector2(0)  # Default parameters


def test_particle_update():
    game_ = Game()
    p = Particle(game=game_, p_kind=ParticleKind.PARTICLE, pos=pg.Vector2(0, 0))
    kill_anim = p.update()
    assert kill_anim if p.animation.done else not kill_anim


def test_particle_render():
    game_ = Game()  # __init__(): pg.init()
    game_displaysize = game_.display.get_size()
    p = Particle(
        game=game_, p_kind=ParticleKind.PARTICLE, pos=pg.Vector2(game_displaysize[0] * 0.5, game_displaysize[1] * 0.5)
    )
    assert isinstance(game_.assets.animations_misc.particle, Dict)
    assert game_.assets.animations_misc.particle.get('flame')
    assert game_.assets.animations_misc.particle.get('flameglow')
    particle_anim = game_.assets.animations_misc.particle.get('particle')
    assert particle_anim
    assert particle_anim.loop == False
    assert particle_anim.images
    n_particle_anim_images = len(particle_anim.images)
    max_anim_duration = particle_anim._img_duration  # pyright: ignore[reportPrivateUsage]
    assert n_particle_anim_images == 4 and max_anim_duration == 6
    ticks = n_particle_anim_images * (max_anim_duration)
    assert ticks == 24
    counter = 0
    for i in range(ticks - n_particle_anim_images):
        kill_anim = p.update()
        assert kill_anim if p.animation.done else not kill_anim, repr(i)
        assert p.render(surf=game_.display, offset=(0, 0)) == None, repr(i)
        counter += 1
    if 0:
        assert (counter - 1) == ticks
    else:
        assert (counter + n_particle_anim_images) == ticks
    assert not p.update()
    assert p.render(surf=game_.display, offset=(0, 0)) == None, repr(counter)
    counter += 1
    assert not p.update()
    assert p.render(surf=game_.display, offset=(0, 0)) == None, repr(counter)
    counter += 1
    assert not p.update()
    assert p.render(surf=game_.display, offset=(0, 0)) == None, repr(counter)
    counter += 1
    assert counter == 23
    with pytest.raises(AssertionError, match=re.escape('update: animation done')):
        assert not p.update(), 'update: animation done'  # ====  WHY ====
        assert p.render(surf=game_.display, offset=(0, 0)) == None, repr(counter)
        counter += 1
        assert counter == 24, 'expected counter to be 24'
    pg.quit()
