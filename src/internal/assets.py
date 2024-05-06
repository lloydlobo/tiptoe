import itertools as it
import logging
import math
from dataclasses import dataclass
from functools import partial
from random import randint, random, uniform  # pyright: ignore
from typing import Final, Optional  # pyright:ignore

import pygame as pg

import internal.prelude as pre
from internal.spritesheet import Spritesheet


rand_uniform = partial(uniform)
rand_uniform.__doc__ = """New partial function for random.uniform to get a random number in the range [a, b) or [a, b] depending on rounding."""


################################################################################
### ASSETS CLASS
################################################################################


@dataclass
class Assets:
    animations_entity: "AnimationEntityAssets"
    animations_misc: "AnimationMiscAssets"

    entity: dict[str, pg.SurfaceType]
    tiles: dict[str, list[pg.SurfaceType]]

    misc_surf: dict[str, pg.SurfaceType]
    misc_surfs: dict[str, list[pg.SurfaceType]]

    @dataclass
    class AnimationEntityAssets:
        player: dict[str, pre.Animation]
        enemy: dict[str, pre.Animation]

        @property
        def elems(self):
            return {pre.EntityKind.PLAYER.value: self.player, pre.EntityKind.ENEMY.value: self.enemy}

        # skipping error handling for performance
        def __getitem__(self, key: str) -> dict[str, pre.Animation]:
            return self.elems[key]

    @dataclass
    class AnimationMiscAssets:
        particle: dict[str, pre.Animation]

    @classmethod
    def initialize_editor_assets(cls):
        player_spawner_surf = pre.create_surface_partialfn(size=pre.SIZE.PLAYER, fill_color=pre.COLOR.PLAYER)
        enemy_spawner_surf = pre.create_surface_partialfn(size=pre.SIZE.ENEMY, fill_color=pre.COLOR.ENEMY)

        asset_tiles_decor_variations = ((2, pre.Palette.COLOR2, (4, 8)), (2, pre.COLOR.FLAMETORCH, pre.SIZE.FLAMETORCH), (2, pre.COLOR.FLAMETORCH, (4, 5)))
        asset_tiles_largedecor_variations = ((2, pre.Palette.COLOR1, (32, 16)), (2, pre.Palette.COLOR1, (32, 16)), (2, pre.Palette.COLOR1, (32, 16)))

        asset_tiles_decor_variations = ((2, pre.Palette.COLOR2, (4, 8)), (2, pre.COLOR.FLAMETORCH, pre.SIZE.FLAMETORCH), (2, pre.COLOR.FLAMETORCH, (4, 5)))
        decor = list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_decor_variations)))

        # #########################################3
        # ### without pixelart
        # #########################################3
        # if 0:
        #     asset_tiles_largedecor_variations = ((2, pre.RED, (16, 16 - 4)), (2, pre.RED, (32, 16)), (2, pre.RED, (32, 16)))
        #     large_decor = list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_largedecor_variations)))
        # #########################################3
        # ### with pixelart
        # #########################################3
        # ld0 = pre.load_img((pre.IMGS_PATH / "tiles" / "large_decor" / "0.png").__str__(), with_alpha=False, colorkey=pre.BLACK)
        # ld1 = pre.load_img((pre.IMGS_PATH / "tiles" / "large_decor" / "0.png").__str__(), with_alpha=False, colorkey=pre.BLACK)
        # ld2 = pre.load_img((pre.IMGS_PATH / "tiles" / "large_decor" / "0.png").__str__(), with_alpha=False, colorkey=pre.BLACK)
        # large_decor = [ld0, ld1, ld2]
        spritesheet_large_decor = Spritesheet(
            sheet_path=pre.IMGS_PATH / "spritesheets" / "large_decor.png",
            metadata_path=pre.IMGS_PATH / "spritesheets" / "large_decor.json",
        )
        ld_sprites: list[pg.SurfaceType] = []
        for group in ["tree", "bush", "pileofbricks"]:
            ld_sprites.extend(spritesheet_large_decor.load_sprites("large_decor", group))

        spritesheet_tileset = Spritesheet(
            sheet_path=pre.IMGS_PATH / "spritesheets" / "tileset.png",
            metadata_path=pre.IMGS_PATH / "spritesheets" / "tileset.json",
        )
        # grass_sprites: list[pg.SurfaceType] = spritesheet_tileset.load_sprites("tiles", "grass")
        granite_sprites: list[pg.SurfaceType] = spritesheet_tileset.load_sprites("tiles", "granite")
        stone_sprites: list[pg.SurfaceType] = spritesheet_tileset.load_sprites("tiles", "stone")

        spritesheet_tileset_greenvalley = Spritesheet(
            sheet_path=pre.IMGS_PATH / "spritesheets" / "tilesetmapdecorations.png",
            metadata_path=pre.IMGS_PATH / "spritesheets" / "tilesetmapdecorations.json",
        )
        grass_sprites: list[pg.SurfaceType] = spritesheet_tileset_greenvalley.load_sprites("tiles", "grass")
        grassplatform_sprites = spritesheet_tileset_greenvalley.load_sprites("tiles", "grassplatform")

        return cls(
            entity=dict(),
            misc_surf=dict(),
            misc_surfs=dict(),
            tiles=dict(
                # grid tiles
                # stone=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.STONE)),
                stone=stone_sprites,
                # granite=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.GRANITE)),
                granite=granite_sprites,
                grass=grass_sprites,  # NOTE: if sprite isn't loaded, it is still a physical tile but transparent
                grassplatform=grassplatform_sprites,
                spike=cls.create_spike_surfaces(),
                # offgrid tiles
                decor=decor,
                large_decor=ld_sprites,
                portal=[pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1), pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2)],
                spawners=[
                    player_spawner_surf,
                    enemy_spawner_surf.copy(),
                    pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1),
                    pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2),
                ],
            ),
            animations_entity=Assets.AnimationEntityAssets(player=dict(), enemy=dict()),
            animations_misc=Assets.AnimationMiscAssets(particle=dict()),
        )

    @classmethod
    def initialize_assets(cls):
        player_entity_surf = pre.create_surface_partialfn(size=pre.SIZE.PLAYER, fill_color=pre.COLOR.PLAYER)
        enemy_entity_surf = pre.create_surface_partialfn(size=(pre.SIZE.ENEMY), fill_color=pre.COLOR.ENEMY)

        player_idle_surf_frames = list(
            pre.create_surface_partialfn(
                size=(int(pre.SIZE.PLAYER[0] + uniform(-1, 0)), int(pre.SIZE.PLAYER[1] + uniform(-1, 1))),
                fill_color=pre.COLOR.PLAYER,
            )
            for _ in range(9)
        )
        player_run_surf_frames = list(pre.create_surfaces_partialfn(count=5, size=pre.SIZE.PLAYERRUN, fill_color=pre.COLOR.PLAYERRUN))
        player_jump_surf_frames = list(pre.create_surfaces_partialfn(count=5, size=pre.SIZE.PLAYERJUMP, fill_color=pre.COLOR.PLAYERJUMP))

        esleepcount = 16
        if randint(0, 1):
            if randint(0, 1):
                enemy_sleeping_surfs = cls.create_sleepy_enemy_surfaces(esleepcount)
            else:
                enemy_outline_surf = pre.surfaces_get_outline_mask_from_surf(surf=enemy_entity_surf, color=pre.WHITE, width=1, loc=(0, 0))
                enemy_sleeping_surfs = [(enemy_outline_surf.copy()) for _ in range(esleepcount)]
        else:
            enemy_sleeping_surfs = list(pre.surfaces_vfx_outline_offsets_animation_frames(surf=enemy_entity_surf, color=pre.Palette.COLOR5, width=3, iterations=esleepcount))

        if 0:
            background = pre.create_surface_partialfn(size=pre.DIMENSIONS, fill_color=pre.COLOR.BACKGROUND)

        filename_bg1 = "bg1_320x240.png" if pre.SCREEN_RESOLUTION_MODE == 1 else "bg1_480x315.png"
        filename_bg2 = "bg2_320x240.png" if pre.SCREEN_RESOLUTION_MODE == 1 else "bg2_480x315.png"
        filename_bg3 = "bg3_320x240.png" if pre.SCREEN_RESOLUTION_MODE == 1 else "bg3_480x315.png"
        # filename_bg4 = "bg4_480x315.png" if pre.SCREEN_RESOLUTION_MODE == 1 else "bg4_480x315.png"

        background = pre.load_img((pre.IMGS_PATH / "background" / filename_bg1).__str__())
        bg1 = pre.load_img((pre.IMGS_PATH / "background" / filename_bg1).__str__()).convert()
        bg1.set_colorkey(pre.BLACK)
        bg2 = pre.load_img((pre.IMGS_PATH / "background" / filename_bg2).__str__()).convert()
        bg2.set_colorkey(pre.BLACK)
        bg3 = pre.load_img((pre.IMGS_PATH / "background" / filename_bg3).__str__()).convert()
        bg3.set_colorkey(pre.BLACK)
        # bg4 = pre.load_img((pre.IMGS_PATH / "background" / filename_bg4).__str__()).convert()
        # bg4.set_colorkey(pre.BLACK)

        gun = pre.create_surface_partialfn(pre.SIZE.GUN, fill_color=pre.COLOR.GUN)
        misc_surf_projectile = pre.create_surface_partialfn((5, 3), fill_color=pre.Palette.COLOR0)

        stars = list(cls.create_star_surfaces())

        flame_particles = [pre.create_circle_surf_partialfn(pre.SIZE.FLAMEPARTICLE, pre.COLOR.FLAME) for _ in range(pre.COUNT.FLAMEPARTICLE)]
        flameglow_particles = [pre.create_circle_surf_partialfn(pre.SIZE.FLAMEGLOWPARTICLE, pre.COLOR.FLAMEGLOW) for _ in range(pre.COUNT.FLAMEGLOW)]

        asset_tiles_decor_variations = ((2, pre.Palette.COLOR2, (4, 8)), (2, pre.COLOR.FLAMETORCH, pre.SIZE.FLAMETORCH), (2, pre.COLOR.FLAMETORCH, (4, 5)))
        decor = list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_decor_variations)))

        logging.basicConfig(level=logging.DEBUG)
        spritesheet_large_decor = Spritesheet(sheet_path=pre.IMGS_PATH / "spritesheets" / "large_decor.png", metadata_path=pre.IMGS_PATH / "spritesheets" / "large_decor.json")
        large_decor_surfaces: list[pg.SurfaceType] = []
        for group in ["tree", "bush", "pileofbricks"]:
            large_decor_surfaces.extend(spritesheet_large_decor.load_sprites("large_decor", group))

        spritesheet_tileset = Spritesheet(sheet_path=pre.IMGS_PATH / "spritesheets" / "tileset.png", metadata_path=pre.IMGS_PATH / "spritesheets" / "tileset.json")
        granite_sprites = spritesheet_tileset.load_sprites("tiles", "granite")
        stone_sprites = spritesheet_tileset.load_sprites("tiles", "stone")

        spritesheet_player = Spritesheet(sheet_path=pre.IMGS_PATH / "spritesheets" / "player.png", metadata_path=pre.IMGS_PATH / "spritesheets" / "player.json")
        player_idle_sprites = spritesheet_player.load_sprites("player", "idle")
        player_run_sprites = spritesheet_player.load_sprites("player", "run")
        player_jump_sprites = spritesheet_player.load_sprites("player", "jump")

        for i, p in enumerate(player_idle_sprites.copy()):
            x = pg.transform.scale_by(p, 0.64)
            player_idle_sprites[i] = x
        for i, p in enumerate(player_run_sprites.copy()):
            x = pg.transform.scale_by(p, 0.64)
            player_run_sprites[i] = x
        for i, p in enumerate(player_jump_sprites.copy()):
            x = pg.transform.scale_by(p, 0.64)
            player_jump_sprites[i] = x

        spritesheet_enemy_slime_idle = Spritesheet(sheet_path=pre.IMGS_PATH / "spritesheets" / "enemy_slime_idle.png", metadata_path=pre.IMGS_PATH / "spritesheets" / "enemy_slime_idle.json")
        enemy_slime_idle_sprites = spritesheet_enemy_slime_idle.load_sprites("enemy", "idle")

        spritesheet_enemy_idle_run = Spritesheet(sheet_path=pre.IMGS_PATH / "spritesheets" / "enemy_idle_run.png", metadata_path=pre.IMGS_PATH / "spritesheets" / "enemy_idle_run.json")
        enemy_idle_sprites = spritesheet_enemy_idle_run.load_sprites("enemy", "idle")
        enemy_run_sprites = spritesheet_enemy_idle_run.load_sprites("enemy", "run")

        spritesheet_tileset_greenvalley = Spritesheet(sheet_path=pre.IMGS_PATH / "spritesheets" / "tilesetmapdecorations.png", metadata_path=pre.IMGS_PATH / "spritesheets" / "tilesetmapdecorations.json")
        grass_sprites = spritesheet_tileset_greenvalley.load_sprites("tiles", "grass")
        grassplatform_sprites = spritesheet_tileset_greenvalley.load_sprites("tiles", "grassplatform")

        return cls(
            entity=dict(enemy=enemy_entity_surf, player=player_entity_surf),
            misc_surf=dict(
                background=background.copy(),
                bg1=bg1,
                bg2=bg2,
                bg3=bg3,
                # bg4=bg4,
                gun=gun,
                projectile=misc_surf_projectile,
            ),
            misc_surfs=dict(stars=stars),
            tiles=dict(
                # grid tiles
                # stone=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.STONE)),
                stone=stone_sprites,
                # granite=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.GRANITE)),
                grass=grass_sprites,
                grassplatform=grassplatform_sprites,
                granite=granite_sprites,
                # spike=cls.create_spike_surfaces(),
                spike=[
                    pre.load_img(str(pre.IMGS_PATH / "tiles" / "spikes" / "0.png"), colorkey=pre.BLACK),
                ],
                # offgrid tiles
                decor=decor,
                large_decor=large_decor_surfaces,
                portal=[pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1), pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2)],
            ),
            animations_entity=Assets.AnimationEntityAssets(
                player=dict(
                    # idle=pre.Animation(player_idle_surf_frames, img_dur=6),
                    # run=pre.Animation(player_run_surf_frames, img_dur=4),
                    # jump=pre.Animation(player_jump_surf_frames, img_dur=4, loop=False),
                    # idle=pre.Animation(pre.load_imgs(str(pre.IMGS_PATH / "entities" / "player" / "idle"), colorkey=pre.BLACK), img_dur=6),
                    # run=pre.Animation(pre.load_imgs(str(pre.IMGS_PATH / "entities" / "player" / "run"), colorkey=pre.BLACK), img_dur=4),
                    # jump=pre.Animation(pre.load_imgs(str(pre.IMGS_PATH / "entities" / "player" / "jump"), colorkey=pre.BLACK), img_dur=6, loop=False),
                    idle=pre.Animation(player_idle_sprites, img_dur=12),
                    run=pre.Animation(player_run_sprites, img_dur=4),
                    jump=pre.Animation(player_jump_sprites, img_dur=6, loop=False),
                ),
                enemy=dict(
                    # sleeping=pre.Animation(enemy_sleeping_surfs, img_dur=18),
                    # sleeping=pre.Animation(enemy_sleeping_sprites, img_dur=18),
                    # sleeping=pre.Animation(pre.load_imgs(str(pre.IMGS_PATH / "entities" / "enemy" / "idle"), colorkey=pre.BLACK), img_dur=18),
                    # idle=pre.Animation([enemy_entity_surf.copy()], img_dur=6),
                    # run=pre.Animation(list(pre.create_surfaces_partialfn(count=8, fill_color=pre.COLOR.ENEMY, size=pre.SIZE.ENEMYJUMP)), img_dur=4),
                    # idle=pre.Animation(pre.load_imgs(str(pre.IMGS_PATH / "entities" / "enemy" / "idle"), colorkey=pre.BLACK), img_dur=6),
                    # run=pre.Animation(pre.load_imgs(str(pre.IMGS_PATH / "entities" / "enemy" / "run"), colorkey=pre.BLACK), img_dur=6),
                    sleeping=pre.Animation(enemy_slime_idle_sprites, img_dur=12),
                    idle=pre.Animation(enemy_slime_idle_sprites, img_dur=6),
                    run=pre.Animation(enemy_slime_idle_sprites, img_dur=4),
                ),
            ),
            animations_misc=Assets.AnimationMiscAssets(
                particle=dict(
                    flame=pre.Animation(flame_particles, img_dur=12, loop=False),  # Set true for stress performance
                    flameglow=pre.Animation(flameglow_particles, img_dur=24, loop=False),  # Set true for stress  performance
                    particle=pre.Animation(list(pre.create_surfaces_partialfn(4, pre.COLOR.PLAYERSTAR, (2, 2))), img_dur=6, loop=False),
                )
            ),
        )

    @classmethod
    def create_sleepy_enemy_surfaces(cls, count: int):
        enemy_sleeping_surfs: list[pg.SurfaceType] = []
        sleepy_star_sizes = it.cycle(map(lambda x: x * 0.618 ** (1 * math.pi), (0, 1, 1, 2, 3, 5, 8, 13)))
        sleepy_star_colors = it.cycle((pre.Palette.COLOR4, pre.Palette.COLOR6, pre.Palette.COLOR5, pre.PINK, pre.Palette.COLOR3, pre.WHITE))
        sleepy_star_circle_width = 0

        for i in range(count):
            if randint(0, 1):
                s = pre.create_surface_withalpha_partialfn(size=((pre.SIZE.ENEMY[0] - 0, pre.SIZE.ENEMY[1] - 0)), fill_color=pre.COLOR.ENEMYSLEEPING, alpha=234)
            else:
                s = pre.create_surface_partialfn(size=(pre.SIZE.ENEMY[0], pre.SIZE.ENEMY[1] + randint(-1, 0)), fill_color=pre.COLOR.TRANSPARENTGLOW)
            srect = s.get_rect()
            # clockwise
            a, b, c, d = (srect.topleft, srect.topright, srect.bottomright, srect.bottomleft)

            ofst = (uniform(-16, 16), uniform(-4.5, 4.5), uniform(-2.5, 2.5))[randint(1, 2)]

            if 0:
                cls.render_wobbly_surface(surf=s, outline_color=(pre.WHITE), frame=i)
                cls.render_wobbly_surface(surf=s, outline_color=(pre.COLOR.TRANSPARENTGLOW), frame=i)
                cls.render_wobbly_surface(surf=s, outline_color=pre.RED, frame=i)

            for j in range(16):
                j %= 8
                pg.draw.circle(s, next(sleepy_star_colors), (a[0] + ofst * j, a[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (b[0] + ofst * j, b[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (c[0] + ofst * j, c[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (d[0] + ofst * j, d[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (c[0] + ofst * j, c[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (b[0] + ofst * j, b[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)

            enemy_sleeping_surfs.append(s)

        return enemy_sleeping_surfs

    @classmethod
    def create_spike_surfaces_from_config(cls) -> list[pg.SurfaceType]:
        spike_surfaces: list[pg.SurfaceType] = []
        side_length = 16
        spike_length = 6

        # Create base surface for spikes
        base_surf = pg.Surface((side_length, side_length)).convert()
        base_surf.set_colorkey(pg.Color("black"))

        # Create spike surface
        spike_surf = pg.Surface((side_length, spike_length)).convert()
        spike_surf.set_colorkey(pg.Color("black"))
        spike_surf.fill(pg.Color("red"))

        for config in pre.SPIKE_CONFIGURATIONS:
            surf_surf = base_surf.copy()  # Create a copy of the base surface

            spos = config['position']
            assert len(spos) == 2
            # size = config['size']
            orientation = config['orientation']

            x, y = int(spos[0]), int(spos[1])
            if orientation == 'bottom':
                surf_surf.blit(spike_surf, (x, y + side_length - spike_length))
            elif orientation == 'top':
                surf_surf.blit(spike_surf, (x, y))
            elif orientation == 'left':
                rotated_spike = pg.transform.rotate(spike_surf, 90)
                surf_surf.blit(rotated_spike, (x, y))
            elif orientation == 'right':
                rotated_spike = pg.transform.rotate(spike_surf, -90)
                surf_surf.blit(rotated_spike, (x + side_length - spike_length, y))
            else:
                raise ValueError(f"Invalid spike orientation: {orientation}")

            spike_surfaces.append(surf_surf)

        return spike_surfaces

    @staticmethod
    def create_spike_surfaces() -> list[pg.SurfaceType]:
        spike: list[pg.SurfaceType] = []
        orientations: Final = 4

        def spikey_lines(
            spike_surf: pg.SurfaceType,
            orientation: int,
            tipcount: int,
            length: int,
            thickness: int,
            color: pre.ColorKind | pre.ColorValue,
            outline_width: int,
        ):
            rect = spike_surf.get_rect()
            spike_len = rect.w // tipcount
            match orientation:
                case 0:  # bottom
                    for i in range(0, rect.w, spike_len):
                        pg.draw.polygon(surf, color, [(rect.left + i, rect.bottom), (rect.left + i + spike_len // 2, rect.top), (rect.left + i + spike_len, rect.bottom)])
                        pg.draw.polygon(
                            surf, color, [(rect.left + i, rect.bottom // 2 + thickness // 4), (rect.left + i + spike_len // 2, 4 * rect.top), (rect.left + i + spike_len, rect.bottom // 2 + thickness // 4)]
                        )
                    pass
                case 1:  # top
                    for i in range(0, rect.w, spike_len):
                        pg.draw.polygon(surf, color, [(rect.left + i, -2 * rect.top), (rect.left + i + spike_len // 2, rect.bottom // 2 + thickness // 4), (rect.left + i + spike_len, -2 * rect.top)])
                    pass
                case 2:  # left
                    # surf.fill(pre.COLOR.SPIKE)  # add filler
                    for i in range(0, rect.w, spike_len):
                        pg.draw.polygon(surf, color, [(rect.left + i, -2 * rect.top), (rect.left + i + spike_len // 2, rect.bottom // 2 + thickness // 4), (rect.left + i + spike_len, -2 * rect.top)])
                case 3:  # right
                    for i in range(0, rect.w, spike_len):
                        pg.draw.polygon(surf, color, [(rect.left + i, -2 * rect.top), (rect.left + i + spike_len // 2, rect.bottom // 2 + thickness // 4), (rect.left + i + spike_len, -2 * rect.top)])
                case _:
                    raise ValueError(f"invalid spike orientation. got {orientation=}")
            surf.set_colorkey(pre.COLOR.TRANSPARENTGLOW)  # remove filler
            # pg.draw.polygon(spike_surf, color, outline, outline_width)

        for orient in range(orientations):
            surf_16x16 = pg.Surface((pre.TILE_SIZE, pre.TILE_SIZE)).convert()
            surf_16x16.set_colorkey(pre.BLACK)

            length, thickness = (16, 6)
            tipcount = int(min(4, 16 // 4))
            surf = pg.Surface((length, thickness)).convert()
            surf.set_colorkey(pre.BLACK)
            # surf.fill(pre.COLOR.SPIKE)
            surf.fill(pre.COLOR.TRANSPARENTGLOW)  # add filler
            # surf.fill(pre.BLACK)
            color = pre.COLOR.SPIKE

            match orient:
                case 0:  # bottom
                    spikey_lines(surf, orient, tipcount, length, thickness, color, 1)
                    surf_16x16.blit(surf, (0, surf_16x16.get_size()[1] - surf.get_size()[1]))
                case 1:  # top (normal behavior, when height is less. reduced at bottom)
                    spikey_lines(surf, orient, tipcount, length, thickness, color, 1)
                    surf_16x16.blit(surf, (0, 0))
                case 2:  # left
                    spikey_lines(surf, orient, tipcount, length, thickness, color, 1)
                    surf_16x16.blit(pg.transform.rotate(surf.copy(), 90), (0, 0))
                case 3:  # right
                    spikey_lines(surf, orient, tipcount, length, thickness, color, 1)
                    surf_16x16.blit(pg.transform.rotate(surf.copy(), -90.0), (16 - 6, 0))
                case _:
                    raise ValueError(f"unreachable value. have {orientations} sides. got {orient=}")
            spike.append(surf_16x16)

        return spike

    @staticmethod
    def create_star_surfaces():
        size = pre.SIZE.STAR
        r, g, b = pre.COLOR.STAR
        return (
            pre.create_surface_partialfn(size=size, fill_color=(min(255, r + math.floor(rand_uniform(-4.0, 4.0))), g + math.floor(rand_uniform(-4.0, 4.0)), b + math.floor(rand_uniform(-4.0, 4.0))))
            for _ in range(pre.COUNT.STAR)
        )  # Note: r overflows above 255 as r==(constant) COLOR6: tuple[Literal[255], Literal[212], Literal[163]]

    @staticmethod
    def create_wobbly_surface_outline():
        pass

    @classmethod
    def render_wobbly_surface(cls, surf: pg.SurfaceType, outline_color: pre.ColorValue = (20, 20, 20), frame: int = 0) -> None:
        pre_surf_scale = 8
        amplitude = 10  # Adjust this value to control the wobbliness
        frequency = 0.1  # Adjust this value to control the frequency of wobbles
        amplitude *= 1
        frequency *= 1
        line_color = outline_color
        ofst = (frame / frequency) + (amplitude / pre.FPS_CAP)
        surf_ = pg.transform.smoothscale_by(surf.copy(), pre_surf_scale)
        pgrect = surf_.get_rect().copy()
        # Draw the wobbly rectangle
        for x in range(pgrect.left, pgrect.right):
            # Top side
            y1 = y2 = pgrect.top + int(amplitude * math.sin(frequency * (x - pgrect.left)))
            pg.draw.line(surf_, line_color, ((x + ofst) % pgrect.right, y1), ((x + ofst) % pgrect.right + 1, y2))
            # Bottom side
            y1 = y2 = pgrect.bottom + int(amplitude * math.sin(frequency * (x - pgrect.left + pgrect.height)))
            pg.draw.line(surf_, line_color, ((x - ofst) % (pgrect.left + 1), y1), ((x + 1 - ofst) % (pgrect.left + 1), y2))
        for y in range(pgrect.top, pgrect.bottom):
            # Left side
            x1 = x2 = pgrect.left + int(amplitude * math.sin(frequency * (y - pgrect.top)))
            pg.draw.line(surf_, line_color, (x1, (y - ofst)), (x2, y + 1 - ofst))
            # Right side
            x1 = x2 = pgrect.right + int(amplitude * math.sin(frequency * (y - pgrect.top + pgrect.width)))
            pg.draw.line(surf_, line_color, (x1, y + ofst), (x2, y + 1 + ofst))
        surf_ = pg.transform.smoothscale_by(surf_.copy(), (1 / pre_surf_scale) * uniform(1.2, 1.2))  # to decrease *0.99999
        dest = surf_.copy().get_rect().topleft
        surf.blit(surf_, (dest[0] - 1, dest[1] - 1))
