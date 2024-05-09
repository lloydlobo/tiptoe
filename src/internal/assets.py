import itertools as it
import logging
import math
from dataclasses import dataclass
from random import uniform
from typing import Dict, Final, List

import pygame as pg

import internal.prelude as pre
from internal.spritesheet import Spritesheet


@dataclass
class Assets:
    entity: Dict[str, pg.SurfaceType]
    misc_surf: Dict[str, pg.SurfaceType]

    tiles: Dict[str, List[pg.SurfaceType]]
    misc_surfs: Dict[str, List[pg.SurfaceType]]

    animations_entity: "AnimationEntity"
    animations_misc: "AnimationMisc"

    @dataclass
    class AnimationMisc:
        particle: Dict[str, pre.Animation]

    @dataclass
    class AnimationEntity:
        enemy: Dict[str, pre.Animation]
        player: Dict[str, pre.Animation]

        @property
        def elems(self) -> Dict[str, Dict[str, pre.Animation]]:
            return {
                pre.EntityKind.PLAYER.value: self.player,
                pre.EntityKind.ENEMY.value: self.enemy,
            }

        def __getitem__(self, key: str) -> Dict[str, pre.Animation]:
            return self.elems[key]  # skipping error handling for performance

    @classmethod
    def initialize_assets(cls) -> "Assets":
        logging.basicConfig(level=logging.DEBUG)

        resolution: Final = f"{pre.SCREEN_WIDTH//2}x{pre.SCREEN_HEIGHT//2}"
        bg_path: Final = pre.IMGS_PATH / "background"
        sheets_path: Final = pre.IMGS_PATH / "spritesheets"

        spritesheet_bouncepad = Spritesheet(sheets_path / "bouncepad.png", sheets_path / "bouncepad.json")
        spritesheet_enemy = Spritesheet(sheets_path / "enemy.png", sheets_path / "enemy.json")
        spritesheet_large_decor = Spritesheet(sheets_path / "large_decor.png", sheets_path / "large_decor.json")
        spritesheet_player = Spritesheet(sheets_path / "player1.png", sheets_path / "player1.json")
        spritesheet_tileset = Spritesheet(sheets_path / "tileset.png", sheets_path / "tileset.json")
        spritesheet_tileset_greenvalley = Spritesheet(sheets_path / "tilesetmapdecorations.png", sheets_path / "tilesetmapdecorations.json")

        return cls(
            entity=dict(
                enemy=pre.create_surface_partialfn(size=(pre.SIZE.ENEMY), fill_color=pre.COLOR.ENEMY),
                player=pre.create_surface_partialfn(size=pre.SIZE.PLAYER, fill_color=pre.COLOR.PLAYER),
            ),
            misc_surf=dict(
                background=pre.load_img(bg_path / f"bg1_{resolution}.png", colorkey=pre.BLACK),
                bg1=pre.load_img(bg_path / f"bg1_{resolution}.png", colorkey=pre.BLACK),
                bg2=pre.load_img(bg_path / f"bg2_{resolution}.png", colorkey=pre.BLACK),
                bg3=pre.load_img(bg_path / f"bg3_{resolution}.png", colorkey=pre.BLACK),
                gun=pre.create_surface_partialfn(pre.SIZE.GUN, fill_color=pre.COLOR.GUN),
                projectile=pre.create_surface_partialfn((5, 3), fill_color=pre.Palette.COLOR0),
            ),
            misc_surfs=dict(
                stars=cls.create_star_surfaces(),
            ),
            tiles=dict(
                # ongrid physics tiles
                granite=spritesheet_tileset.load_sprites("tiles", "granite"),
                grass=spritesheet_tileset_greenvalley.load_sprites("tiles", "grass"),
                grassplatform=spritesheet_tileset_greenvalley.load_sprites("tiles", "grassplatform"),
                stone=spritesheet_tileset.load_sprites("tiles", "stone"),
                # offgrid interactive
                bouncepad=spritesheet_bouncepad.load_sprites("tiles", "bouncepad"),
                portal=[pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1), pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2)],
                spike=[pre.load_img(str(pre.IMGS_PATH / "tiles" / "spikes" / "0.png"), colorkey=pre.BLACK)],
                # offgrid decoration
                decor=list(
                    it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, ((2, pre.Palette.COLOR2, (4, 8)), (2, pre.COLOR.FLAMETORCH, pre.SIZE.FLAMETORCH), (2, pre.COLOR.FLAMETORCH, (4, 5)))))
                ),
                large_decor=[sprite for group in ["tree", "bush", "pileofbricks"] for sprite in spritesheet_large_decor.load_sprites("large_decor", group)],
            ),
            animations_entity=cls.AnimationEntity(
                enemy=dict(
                    idle=pre.Animation(spritesheet_enemy.load_sprites("enemy", "idle"), img_dur=6),
                    run=pre.Animation(spritesheet_enemy.load_sprites("enemy", "idle"), img_dur=4),
                    sleeping=pre.Animation(spritesheet_enemy.load_sprites("enemy", "idle"), img_dur=12),
                ),
                player=dict(
                    idle=pre.Animation(spritesheet_player.load_sprites("player", "idle"), img_dur=6),
                    jump=pre.Animation(spritesheet_player.load_sprites("player", "idle"), img_dur=6, loop=False),
                    run=pre.Animation(spritesheet_player.load_sprites("player", "idle"), img_dur=4),
                ),
            ),
            animations_misc=cls.AnimationMisc(
                particle=dict(
                    flame=pre.Animation([pre.create_circle_surf_partialfn(pre.SIZE.FLAMEPARTICLE, pre.COLOR.FLAME) for _ in range(pre.COUNT.FLAMEPARTICLE)], img_dur=12, loop=False),
                    flameglow=pre.Animation([pre.create_circle_surf_partialfn(pre.SIZE.FLAMEGLOWPARTICLE, pre.COLOR.FLAMEGLOW) for _ in range(pre.COUNT.FLAMEGLOW)], img_dur=24, loop=False),
                    particle=pre.Animation(list(pre.create_surfaces_partialfn(4, pre.COLOR.PLAYERSTAR, (2, 2))), img_dur=6, loop=False),
                )
            ),
        )

    @property
    def editor_view(self) -> "Assets":
        self.tiles["spawners"] = [
            self.entity["player"],
            self.entity["enemy"],
            pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL1),
            pre.create_surface_partialfn(size=pre.SIZE.PORTAL, fill_color=pre.COLOR.PORTAL2),
        ]
        return self

    @staticmethod
    def create_star_surfaces() -> List[pg.SurfaceType]:
        size: Final = pre.SIZE.STAR

        r, g, b = pre.COLOR.STAR

        return [
            pre.create_surface_partialfn(
                size=size,
                fill_color=(
                    max(0, min(255, r + math.floor(uniform(-4.0, 4.0)))),
                    g + math.floor(uniform(-4.0, 4.0)),
                    b + math.floor(uniform(-4.0, 4.0)),
                ),
            )
            for _ in range(pre.COUNT.STAR)
        ]
