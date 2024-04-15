import os
import sys

import pygame as pg

import internal.prelude as pre
from internal.entities import Player
from internal.tilemap import Tilemap


class Game:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption(pre.CAPTION)
        self.screen = pg.display.set_mode(pre.DIMENSIONS)
        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.font_size = 18
        self.font = pg.font.SysFont(name=(pg.font.get_default_font() or "monospace"), size=self.font_size, bold=False)

        self.clock = pg.time.Clock()

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)  # figure how to make it optional. have to assign regardless of None

        # need these for reference for animation workaround
        player_size = (8, pre.TILE_SIZE - 1)
        enemy_size = (8, pre.TILE_SIZE - 1)
        player_color = pre.YELLOW
        player_alpha = 255 // 1
        player_surf = Tilemap.generate_surf(1, player_color, size=player_size, alpha=player_alpha)[0]
        enemy_surf = Tilemap.generate_surf(1, pre.CREAM, size=enemy_size, alpha=(255 // 2))[0]

        self.assets = pre.Assets(
            surface=dict(
                # entity
                background=pg.Surface(pre.DIMENSIONS),  # TODO: use actual background image
                enemy=enemy_surf.copy(),
                player=player_surf.copy(),
                portal=Tilemap.generate_surf(1, size=(player_size[0] + 3, pre.TILE_SIZE), color=pre.WHITE, colorkey=None, alpha=255)[0],
                # tbd
                gun=pg.Surface((14, 7)),
                projectile=pg.Surface((5, 2)),
            ),
            tiles=dict(
                # tiles: on grid
                stone=Tilemap.generate_surf(9, color=pre.BLACK, colorkey=None, alpha=200),
                grass=Tilemap.generate_surf(9, color=pre.BLACK, colorkey=None, alpha=255),
                portal=Tilemap.generate_surf(3, size=(player_size[0] + 3, pre.TILE_SIZE), color=pre.WHITE, colorkey=None, alpha=255),
                # tiles: off grid
                decor=Tilemap.generate_surf(4, color=pre.WHITE, size=(pre.TILE_SIZE // 2, pre.TILE_SIZE // 2)),
                large_decor=Tilemap.generate_surf(4, color=pre.BLACK, size=(pre.TILE_SIZE * 2, pre.TILE_SIZE * 2)),
            ),
            animations_entity=pre.Assets.AnimationEntityAssets(
                player=dict(
                    idle=pre.Animation(Tilemap.generate_surf(count=8, color=player_color, size=(player_size[0], player_size[1]), alpha=player_alpha), img_dur=6),
                    run=pre.Animation(Tilemap.generate_surf(count=8, color=player_color, size=(player_size[0] - 1, player_size[1]), alpha=player_alpha), img_dur=4),
                    jump=pre.Animation(Tilemap.generate_surf(count=5, color=player_color, size=(player_size[0] - 1, player_size[1] + 1), alpha=player_alpha)),
                    # slide=pre.Animation(),
                    # wall_slide=pre.Animation(),
                ),
                enemy=dict(
                    idle=pre.Animation(Tilemap.generate_surf(count=8, color=enemy_surf.get_colorkey(), size=(enemy_size[0], enemy_size[1] - 1)), img_dur=6),
                    run=pre.Animation(Tilemap.generate_surf(count=8, color=enemy_surf.get_colorkey(), size=(enemy_size[0], enemy_size[1] - 1)), img_dur=4),
                ),
            ),
            animations_misc=pre.Assets.AnimationMiscAssets(
                particle=dict(),
            ),
        )

        self.player: Player = Player(self, pg.Vector2(50, 50), pg.Vector2(player_size))

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.level = 0
        self.load_level(self.level)

        self.screenshake = 0

    def load_level(self, map_id: int) -> None:
        if False:
            self.tilemap.load(path=os.path.join(pre.MAP_PATH, f"{map_id}.json"))

        self.enemies = []
        self.portals = []
        if False:
            for spawner in self.tilemap.extract([("spawners", 0), ("spawners", 1), ("spawners,2")]):  # spawn player[1] and enemy[1] and portal[2]
                match spawner["variant"]:
                    case 0:  # player
                        self.player.pos = list(spawner["pos"])
                        self.player.air_time = 0  # reset time to avoid multiple spawning after falling down
                    case 1:  # enemy
                        self.enemies.append(Enemy(self, spawner["pos"], (8, 16)))
                    case 2:  # portal
                        self.portals.append((pg.Surface((8, 16)), pg.Vector2(spawner["pos"])))
                        pass
                    case _:
                        raise ValueError(f'expect a valid spawners variant. got {spawner["variant"]}')

        self.scroll = pg.Vector2(0.0, 0.0)  # camera origin is top-left of screen
        self._scroll_ease = pg.Vector2(0.0625, 0.0625)  # 1/16 (as 16 is a perfect square)

        # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead = 0

        # note: abs(self.transition) == 30 => opaque screen see nothing
        # abs(self.transition) == 0 see eeverything; load level when completely black
        self.transition = -30

    def run(self) -> None:
        bg = self.assets.surface["background"]
        bg.set_colorkey(pre.BLACK)
        bg.fill(pre.BG_DARK)

        while True:
            self.display.fill(pre.TRANSPARENT)
            self.display_2.blit(bg, (0, 0))

            # camera: update and parallax
            #
            # 'where we want camera to be' - 'where we are or what we have' / '20', so further player is faster camera moves and vice-versa
            # we can use round on scroll increment to smooth out jumper scrolling & also multiplying by point zero thirty two instead of dividing by thirty
            # if camera is off by 1px not an issue, but rendering tiles could be.
            self.scroll.x += round((self.player.rect().centerx - (self.display.get_width() * 0.5) - self.scroll.x) * self._scroll_ease.x, 2)
            self.scroll.y += round((self.player.rect().centery - (self.display.get_height() * 0.5) - self.scroll.y) * self._scroll_ease.y, 2)
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))

            # tilemap: render
            self.tilemap.render(self.display, render_scroll)

            # portal: render
            """
            self.tilemap[f"{20+i};{6}"] = TileItem(kind=pre.TileKind.STONE, variant=0, pos=pg.Vector2(20 + i, 6))
            self.tilemap[f"{20+i};{5}"] = TileItem(kind=pre.TileKind.STONE, variant=0, pos=pg.Vector2(20 + i, 5))
            """
            # self.tilemap.offgrid_tiles.append(TileItem(kind=pre.TileKind.PORTAL, variant=0, pos=pg.Vector2(21, 4)))
            self.portal = self.assets.surface["portal"]
            self.portal_pos = pg.Vector2(int(21 * self.tilemap.tile_size), int(4 * self.tilemap.tile_size))
            self.display.blit(self.portal, self.portal_pos - render_scroll)

            # enemy: update and render
            # TODO:

            # player: update and render
            if not self.dead:
                self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
                self.player.render(self.display, render_scroll)
                # self.display.blit(self.assets.animations_entity.player[Action.IDLE.value].copy().img(), (50, 50) or render_scroll)
                # debug: collission detection
                #   ta = self.tilemap.tiles_around(tuple(self.player.pos))
                #   pra = self.tilemap.physics_rects_around(tuple(self.player.pos))

            if self.player.rect().collidepoint(self.portal_pos):
                print(f"CLEARED {self.level}")
            # print(f"{self.player.pos/self.tilemap.tile_size, (self.portal.get_rect().x,self.portal.get_locked) = }")

            # mask: before particles!!!
            display_mask: pg.Mask = pg.mask.from_surface(self.display)  # 180 alpha to set color of outline or use 255//2
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_silhouette, offset)

            # particles:
            # TODO:

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_LEFT:
                        self.movement.left = True
                    if event.key == pg.K_RIGHT:
                        self.movement.right = True
                    if event.key == pg.K_UP:
                        if self.player.jump():
                            # TODO: play jump sfx
                            pass
                if event.type == pg.KEYUP:
                    if event.key == pg.K_LEFT:
                        self.movement.left = False
                    if event.key == pg.K_RIGHT:
                        self.movement.right = False

            # DISPLAY RENDERING

            # blit display on display_2 and then blit display_2 on
            # screen for depth effect.

            self.display_2.blit(self.display, (0, 0))

            # TODO: screenshake effect via offset for screen blit
            # ...
            self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), (0, 0))  # pixel art effect

            # DEBUG: HUD

            if pre.DEBUG_HUD:
                antialias = True  # for text
                # HUD: show fps
                text = self.font.render(f"FPS {self.clock.get_fps():4.0f}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 1))
                # HUD: show self.scroll
                text = self.font.render(f"SCROLL {str(self.scroll).ljust(4)}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 2))
                # HUD: show render_scroll
                text = self.font.render(f"RSCROLL {str(render_scroll).ljust(4)}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 3))
                # HUD: show self.movement
                text = self.font.render(f"{str(self.movement).ljust(4).upper()}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 4))
                # HUD: show self.player.pos
                text = self.font.render(f"POS {str(self.player.pos).ljust(4)}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 5))
                # HUD: show self.player.velocity
                text = self.font.render(f"VELOCITY {str(self.player.velocity).ljust(4)}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 6))
                # HUD: show self.player.action
                text = self.font.render(f"{str(self.player.action).ljust(4).upper()}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 7))
                # HUD: show self.player.flip
                text = self.font.render(f"FLIP {str(self.player.flip).ljust(4).upper()}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 8))

            # FINAL DRAWING

            pg.display.flip()  # update whole screen
            self.clock.tick(pre.FPS_CAP)  # note: returns delta time (dt)


if __name__ == "__main__":
    Game().run()
