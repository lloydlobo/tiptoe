import itertools as it
import math
from dataclasses import dataclass
from functools import partial
from random import randint, random, uniform  # pyright:ignore


"""Noise functions for procedural generation of content
Contains native code implementations of Perlin improved noise (with
fBm capabilities) and Perlin simplex noise. Also contains a fast
"fake noise" implementation in GLSL for execution in shaders."""
import noise
import pygame as pg

import internal.prelude as pre


################################################################################
### UTILS
################################################################################


def clamp(value: int, min_val: int, max_val: int) -> int:
    return min(max(value, min_val), max_val)


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

        asset_tiles_decor_variations = ((2, pre.Palette.COLOR2, (4, 8)), (2, pre.COLOR.FLAMETORCH, pre.SIZE.FLAMETORCH), (2, pre.COLOR.FLAMETORCH, (4, 5)))  # variants 0,1 (TBD)  # variants 2,3 (torch)  # variants 4,5 (TBD)
        asset_tiles_largedecor_variations = ((2, pre.Palette.COLOR1, (32, 16)), (2, pre.Palette.COLOR1, (32, 16)), (2, pre.Palette.COLOR1, (32, 16)))  # variants 0,1 (TBD)  # variants 2,3 (TBD)  # variants 4,5 (TBD)

        return cls(
            entity=dict(),
            misc_surf=dict(),
            misc_surfs=dict(),
            tiles=dict(
                # grid tiles
                stone=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.STONE)),
                grass=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.GRASS)),
                # offgrid tiles
                decor=list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_decor_variations))),
                large_decor=list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_largedecor_variations))),
                portal=[pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1), pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2)],
                spawners=[player_spawner_surf, enemy_spawner_surf.copy(), pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1)],
            ),
            animations_entity=Assets.AnimationEntityAssets(player=dict(), enemy=dict()),
            animations_misc=Assets.AnimationMiscAssets(particle=dict()),
        )

    @classmethod
    def initialize_assets(cls):
        player_entity_surf = pre.create_surface_partialfn(size=pre.SIZE.PLAYER, fill_color=pre.COLOR.PLAYER)
        enemy_entity_surf = pre.create_surface_partialfn(size=(pre.SIZE.ENEMY), fill_color=pre.COLOR.ENEMY)

        player_idle_surf_frames = list(pre.create_surface_partialfn(size=(int(pre.SIZE.PLAYER[0] + uniform(-1, 0)), int(pre.SIZE.PLAYER[1] + uniform(-1, 1))), fill_color=pre.COLOR.PLAYER) for _ in range(9))
        player_run_surf_frames = list(pre.create_surfaces_partialfn(count=5, size=pre.SIZE.PLAYERRUN, fill_color=pre.COLOR.PLAYERRUN))
        player_jump_surf_frames = list(pre.create_surfaces_partialfn(count=5, size=pre.SIZE.PLAYERJUMP, fill_color=pre.COLOR.PLAYERJUMP))

        enemy_sleeping_surfs = cls.create_sleepy_enemy_surfaces()

        background = pre.create_surface_partialfn(size=pre.DIMENSIONS, fill_color=pre.COLOR.BACKGROUND)
        gun = pre.create_surface_partialfn(pre.SIZE.GUN, fill_color=pre.COLOR.GUN)
        misc_surf_projectile = pre.create_surface_partialfn((5, 3), fill_color=pre.Palette.COLOR0)

        stars = list(cls.create_star_surfaces())

        asset_tiles_decor_variations = ((2, pre.Palette.COLOR2, (4, 8)), (2, pre.COLOR.FLAMETORCH, pre.SIZE.FLAMETORCH), (2, pre.COLOR.FLAMETORCH, (4, 5)))  # variants 0,1 (TBD)  # variants 2,3 (torch)  # variants 4,5 (TBD)
        asset_tiles_largedecor_variations = ((2, pre.Palette.COLOR1, (32, 16)), (2, pre.Palette.COLOR1, (32, 16)), (2, pre.Palette.COLOR1, (32, 16)))  # variants 0,1 (TBD)  # variants 2,3 (TBD)  # variants 4,5 (TBD)
        # portal_surf_1 = pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1)
        # portal_surf_2 = pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2)

        flame_particles = [pre.create_circle_surf_partialfn(pre.SIZE.FLAMEPARTICLE, pre.COLOR.FLAME) for _ in range(pre.COUNT.FLAMEPARTICLE)]
        flameglow_particles = [pre.create_circle_surf_partialfn(pre.SIZE.FLAMEGLOWPARTICLE, pre.COLOR.FLAMEGLOW) for _ in range(pre.COUNT.FLAMEGLOW)]

        return cls(
            entity=dict(enemy=enemy_entity_surf, player=player_entity_surf),
            misc_surf=dict(background=background, gun=gun, projectile=misc_surf_projectile),
            misc_surfs=dict(stars=stars),
            tiles=dict(
                # grid tiles
                stone=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.STONE)),
                grass=list(pre.create_surfaces_partialfn(9, fill_color=pre.COLOR.GRASS)),
                # offgrid tiles
                decor=list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_decor_variations))),
                large_decor=list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_largedecor_variations))),
                portal=[pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1), pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2)],
            ),
            animations_entity=Assets.AnimationEntityAssets(
                player=dict(
                    idle=pre.Animation(player_idle_surf_frames, img_dur=6),
                    run=pre.Animation(player_run_surf_frames, img_dur=4),
                    jump=pre.Animation(player_jump_surf_frames, img_dur=4, loop=False),
                ),
                enemy=dict(
                    sleeping=pre.Animation(enemy_sleeping_surfs, img_dur=18),
                    idle=pre.Animation([enemy_entity_surf.copy()], img_dur=6),
                    run=pre.Animation(list(pre.create_surfaces_partialfn(count=8, fill_color=pre.COLOR.ENEMY, size=pre.SIZE.ENEMYJUMP)), img_dur=4),
                ),
            ),
            animations_misc=Assets.AnimationMiscAssets(
                particle=dict(
                    flame=pre.Animation(flame_particles, img_dur=12, loop=False),  # Set true for stress performance
                    flameglow=pre.Animation(flameglow_particles, img_dur=24, loop=False),  # Set true for stress  performance
                    # particle == player dash particle, also used for death. use longer duration to spread into the stars
                    particle=pre.Animation(list(pre.create_surfaces_partialfn(4, pre.COLOR.PLAYERSTAR, (2, 2))), img_dur=6, loop=False),
                )
            ),
        )

    @classmethod
    def create_sleepy_enemy_surfaces(cls):
        # TODO: just draw mask outlines.. KISS
        enemy_sleeping_surfs: list[pg.SurfaceType] = []
        sleepy_star_sizes = it.cycle(map(lambda x: x * 0.618 ** (1 * math.pi), (0, 1, 1, 2, 3, 5, 8, 13)))
        sleepy_star_colors = it.cycle((pre.Palette.COLOR4, pre.Palette.COLOR6, pre.Palette.COLOR5, pre.PINK, pre.Palette.COLOR3, pre.WHITE))
        sleepy_star_circle_width = 0
        for i in range(16):
            s = pre.create_surface_withalpha_partialfn(size=((pre.SIZE.ENEMY[0] - 0, pre.SIZE.ENEMY[1] - 0)), fill_color=pre.COLOR.ENEMYSLEEPING, alpha=234)
            # s.fill(pre.TRANSPARENT)
            # s = pre.create_surface_partialfn(size=(pre.SIZE.ENEMY[0], pre.SIZE.ENEMY[1] + randint(-1, 0)), fill_color=pre.COLOR.ENEMYSLEEPING)
            # s.fill(pre.COLOR.TRANSPARENTGLOW)
            srect = s.get_rect()
            a, b, c, d = srect.topleft, srect.topright, srect.bottomright, srect.bottomleft  # clockwise
            # ofst = uniform(-0.5, 0.5)
            ofst = (uniform(-16, 16), uniform(-4.5, 4.5), uniform(-2.5, 2.5))[randint(1, 2)]
            cls.render_wobbly_surface(surf=s, outline_color=(pre.WHITE), frame=i)
            cls.render_wobbly_surface(surf=s, outline_color=(pre.COLOR.TRANSPARENTGLOW), frame=i)
            cls.render_wobbly_surface(surf=s, outline_color=pre.RED, frame=i)
            for j in range(16):
                j %= 8
                # swobble.fill(pre.COLOR.TRANSPARENTGLOW)
                pg.draw.circle(s, next(sleepy_star_colors), (a[0] + ofst * j, a[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (b[0] + ofst * j, b[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (c[0] + ofst * j, c[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (d[0] + ofst * j, d[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (c[0] + ofst * j, c[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)
                pg.draw.circle(s, next(sleepy_star_colors), (b[0] + ofst * j, b[1] + ofst * j), next(sleepy_star_sizes), sleepy_star_circle_width)

            enemy_sleeping_surfs.append(s)

        # swobble = Assets.create_wobbly_surface(enemy_sleeping_surfs[-1].copy().get_rect())
        # enemy_sleeping_surfs.append(swobble)
        return enemy_sleeping_surfs

    @staticmethod
    def create_star_surfaces():
        """
        for star in stars:
            r += math.floor(rand_uniform(-4.0, 4.0))
            g += math.floor(rand_uniform(-4.0, 4.0))
            b += math.floor(rand_uniform(-4.0, 4.0))

            star.fill((r, g, b))
            r, g, b = default_color  # reset to default

        return stars

        """
        size = pre.SIZE.STAR
        r, g, b = pre.COLOR.STAR
        # Note: r overflows above 255 as r==(constant) COLOR6: tuple[Literal[255], Literal[212], Literal[163]]
        return (
            pre.create_surface_partialfn(
                size=size,
                fill_color=(
                    min(255, r + math.floor(rand_uniform(-4.0, 4.0))),
                    g + math.floor(rand_uniform(-4.0, 4.0)),
                    b + math.floor(rand_uniform(-4.0, 4.0)),
                ),
            )
            for _ in range(pre.COUNT.STAR)
        )

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

        # scale = 2 or (1 / 6) / 2
        # amplitude = amplitude - amplitude * scale
        # frequency = frequency - frequency * scale
        # print(scale, amplitude, frequency)

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


################################################################################
### ARCHIVED (throwaway)

# ASSETS_JSON_v1 = """{
#     "animations_entity": {"player": {"idle": {"img_dur": 6}, "run": {"img_dur": 4}, "jump": {"img_dur": 4, "loop": false}}, "enemy": {"idle": {"img_dur": 6}, "run": {"img_dur": 4}}},
#     "animations_misc": {"particle": {"flame": {"img_dur": 20, "loop": false}, "particle": {"img_dur": 20, "loop": false}}},
#     "entity": {"enemy": {}, "player": {}},
#     "tiles": {"stone": [], "grass": [], "decor": [], "large_decor": [], "portal": []},
#     "misc_surf": {"background": {}, "gun": {}, "projectile": {}},
#     "misc_surfs": {"stars": []},
# }"""
#
# ASSETS_JSON_v2 = """{
#     "animations_entity": {"player": {"idle": {"img_dur": 6}, "run": {"img_dur": 4}, "jump": {"img_dur": 4, "loop": false}}, "enemy": {"idle": {"img_dur": 6}, "run": {"img_dur": 4}}},
#     "animations_misc": {"particle": {"flame": {"img_dur": 20, "loop": false}, "particle": {"img_dur": 20, "loop": false}}},
#     "entity": {"enemy": {}, "player": {}},
#     "tiles": {"stone": [], "grass": [], "decor": [], "large_decor": [], "portal": []},
#     "misc_surf": {"background": {"size": [800, 600], "color": [0, 0, 0], "alpha": 255}, "gun": {"size": [14, 7], "color": [255, 255, 255], "alpha": 255}, "projectile": {"size": [5, 2], "color": [255, 255, 255], "alpha": 255}},
#     "misc_surfs": {"stars": [{"size": [100, 50], "color": [255, 255, 255], "alpha": 255}]}
# }"""

# def initialize_assets_from_json__beta():
#     json_data = json.loads(ASSETS_JSON_v2)
#
#     # Create surfaces for misc_surf
#     misc_surf: dict[str, pg.SurfaceType] = {}
#     for surf_name, surf_data in json_data["misc_surf"].items():
#         size = surf_data["size"]
#         color = surf_data["color"]
#         alpha = surf_data["alpha"]
#         surf = pg.Surface(size).convert_alpha()
#         surf.fill(color)
#         surf.set_alpha(alpha)
#         misc_surf[surf_name] = surf
#
#     # Create surfaces for misc_surfs
#     misc_surfs: dict[str, list[pg.SurfaceType]] = {}
#     for surf_name, surf_list_data in json_data["misc_surfs"].items():
#         surf_list: list[pg.SurfaceType] = []
#         for surf_data in surf_list_data:
#             size = surf_data["size"]
#             color = surf_data["color"]
#             alpha = surf_data["alpha"]
#             surf = pg.Surface(size).convert_alpha()
#             surf.fill(color)
#             surf.set_alpha(alpha)
#             surf_list.append(surf)
#         misc_surfs[surf_name] = surf_list
#
#     return Assets(
#         entity=json_data["entity"],
#         tiles=json_data["tiles"],
#         misc_surf=misc_surf,
#         misc_surfs=misc_surfs,
#         animations_entity=Assets.AnimationEntityAssets(**json_data["animations_entity"]),
#         animations_misc=Assets.AnimationMiscAssets(**json_data["animations_misc"]),
#     )

# class StarParameters:
#     def __init__(self, size: pg.Rect, color: tuple[int, int, int, int]):
#         self.size = size
#         self.color = color
#
#
# def create_star_surfaces(star_params: StarParameters, star_count: int) -> list[pg.SurfaceType]:
#     """
#     Usage:
#         import pygame as pg
#         star_params = StarParameters(pg.Rect(0, 0, 3, 3), (255, 255, 255, 255))
#         star_count = 100
#         stars = create_star_surfaces(star_params, star_count)
#     """
#     stars: list[pg.SurfaceType] = []
#     for _ in range(star_count):
#         star_surface = pg.Surface((star_params.size.x, star_params.size.y), pg.SRCALPHA)
#         star_surface.fill((0, 0, 0, 255))
#         pg.draw.rect(star_surface, star_params.color, star_params.size)
#
#         pixels = pg.surfarray.pixels3d(star_surface)
#         for x, y in it.product(range(star_params.size.x), range(star_params.size.y)):
#             r, g, b = pixels[x, y]
#             pixels[x, y] = (clamp(r + randint(-4, 4), 0, 255), clamp(g + randint(-4, 4), 0, 255), clamp(b + randint(-4, 4), 0, 255))
#
#         stars.append(star_surface)
#
#     return stars

# """
# GPT code
#
# import json
# import pygame as pg
#
# # Function to save surface properties to a JSON file
# def save_surface_properties(surface, filename):
#     properties = {
#         "size": surface.get_size(),
#         "color": surface.get_at((0, 0)),  # Get color at top-left corner
#         "alpha": surface.get_alpha()
#     }
#     with open(filename, "w") as f:
#         json.dump(properties, f)
#
# # Function to create a surface from properties
# def create_surface_from_properties(properties):
#     size = properties["size"]
#     color = properties["color"]
#     alpha = properties["alpha"]
#     surface = pg.Surface(size).convert_alpha()
#     surface.fill(color)
#     surface.set_alpha(alpha)
#     return surface
#
# # Example usage
# surface = pg.Surface((100, 100)).convert_alpha()
# surface.fill((255, 0, 0))  # Red color
# surface.set_alpha(128)  # Semi-transparent
#
# # Save surface properties to a JSON file
# save_surface_properties(surface, "surface_properties.json")
#
# # Load surface properties from JSON file
# with open("surface_properties.json", "r") as f:
#     loaded_properties = json.load(f)
#
# # Create surface from loaded properties
# loaded_surface = create_surface_from_properties(loaded_properties)
#
# # Now, loaded_surface is identical to the original surface
#
# """

# """
# GPT code
#
# from dataclasses import dataclass
# from enum import Enum, auto
# from typing import Dict, List
#
# import pygame
# from pygame.locals import QUIT
#
#
# class GameType:
#     RPG = 1
#
#
# class TileKey:
#     Grass = 1
#     Water = 2
#     Spawner = 3
#
#
# @dataclass
# class Surface:
#     size: List[int]
#
#
# @dataclass
# class Assets:
#     name: str
#     description: str
#     tiles: Dict[int, List[Surface]] = {}
#     entities: Dict[Enum, Surface] = {}
#
#
# class EntityType(Enum):
#     PLAYER = auto()
#     ENEMY = auto()
#
#
# @dataclass
# class GameAssets:
#     base: Assets
#     value: float
#     game_type: int
#
#     def load_tiles(self, tiles: Dict[int, List[Surface]]):
#         self.base.tiles = tiles
#
#     def load_entities(self, entities: Dict[Enum, Surface]):
#         self.base.entities = entities
#
#
# @dataclass
# class LevelEditorAssets:
#     base: Assets
#     value: float
#
#     @classmethod
#     def from_game_assets(cls, name: str, description: str, value: float, game_assets: GameAssets):
#         tiles = {key: value[:] for key, value in game_assets.base.tiles.items()}
#         tiles[TileKey.Spawner] = [Surface([32, 32]), Surface([32, 32])] if game_assets.game_type == GameType.RPG else []
#         return cls(Assets(name, description, tiles, game_assets.base.entities), value)
#
#
# def initialize_assets():
#     game_assets = GameAssets(Assets("Game Assets", "Assets for the game"), 1000.0, GameType.RPG)
#     tiles = {TileKey.Grass: [Surface([32, 32])], TileKey.Water: [Surface([32, 32])]}
#     player_surface, enemy_surface = Surface([32, 32]), Surface([32, 32])
#     entities = {EntityType.PLAYER: player_surface, EntityType.ENEMY: enemy_surface}
#     game_assets.load_tiles(tiles)
#     game_assets.load_entities(entities)
#     return game_assets
#
#
# def main():
#     pygame.init()
#     SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
#     screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
#     pygame.display.set_caption("Simple Game")
#     game_assets = initialize_assets()
#     running = True
#     while running:
#         for event in pygame.event.get():
#             if event.type == QUIT:
#                 running = False
#         screen.fill((255, 255, 255))
#         for entity_type, entity_surface in game_assets.base.entities.items():
#             if entity_type == EntityType.PLAYER:
#                 screen.blit(pygame.Surface(entity_surface.size), (100, 100))
#             elif entity_type == EntityType.ENEMY:
#                 screen.blit(pygame.Surface(entity_surface.size), (400, 100))
#         pygame.display.flip()
#     pygame.quit()
#
#
# if __name__ == "__main__":
#     main()
#
# """
