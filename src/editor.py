import os
import sys

import pygame as pg

import internal.prelude as pre
from internal.tilemap import TileItem, Tilemap


class Editor:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption(pre.CAPTION)
        self.screen = pg.display.set_mode(pre.DIMENSIONS)
        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        # self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.font_size = 18
        self.font = pg.font.SysFont(name=(pg.font.get_default_font() or "monospace"), size=self.font_size, bold=False)

        self.clock = pg.time.Clock()

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

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
                grass=Tilemap.generate_surf(9, color=pre.GREEN, colorkey=None, alpha=255),
                portal=Tilemap.generate_surf(3, size=(player_size[0] + 3, pre.TILE_SIZE), color=pre.WHITE, colorkey=None, alpha=255),
                # tiles: off grid
                decor=Tilemap.generate_surf(4, color=pre.WHITE, size=(pre.TILE_SIZE // 2, pre.TILE_SIZE // 2)),
                large_decor=Tilemap.generate_surf(4, color=pre.CREAM, size=(pre.TILE_SIZE * 2, pre.TILE_SIZE * 2)),
            ),
            animations_entity=pre.Assets.AnimationEntityAssets(player=dict(), enemy=dict()),
            animations_misc=pre.Assets.AnimationMiscAssets(particle=dict()),
        )

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.level = 0
        self.load_level(self.level)

        self.screenshake = 0

    def load_level(self, map_id: int) -> None:
        if False:
            self.tilemap.load(path=os.path.join(pre.MAP_PATH, f"{map_id}.json"))

        self.scroll = pg.Vector2(0.0, 0.0)  # camera origin is top-left of screen
        self._scroll_ease = pg.Vector2(0.0625, 0.0625)  # 1/16 (as 16 is a perfect square)

        self.tile_list = list(self.assets.tiles.keys())
        assert set(self.tile_list) == set(x.value for x in pre.TileKind)
        self.tile_group = 0
        self.tile_variant = 0

        self.clicking = False
        self.right_clicking = False
        self.shift = False
        self.ongrid = True

        # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead = 0

        # note: abs(self.transition) == 30 => opaque screen see nothing
        # abs(self.transition) == 0 see eeverything; load level when completely black
        self.transition = -30

    def run(self) -> None:
        # bg = self.assets.surface["background"]
        # bg.set_colorkey(pre.BLACK)
        # bg.fill(pre.BG_DARK)

        while True:
            # self.display.fill(pre.TRANSPARENT)
            # self.display_2.blit(bg, (0, 0))
            self.display.fill(pre.BG_DARK)

            # camera: update and parallax
            self.scroll.x += round(self.movement.right - self.movement.left) * pre.CAMERA_SPEED
            self.scroll.y += round(self.movement.bottom - self.movement.top) * pre.CAMERA_SPEED
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))

            # tilemap: render
            self.tilemap.render(self.display, render_scroll)

            cur_tile_img: pg.Surface = self.assets.tiles[self.tile_list[self.tile_group]][self.tile_variant].copy()
            cur_tile_img.set_alpha(100)

            mpos = pg.Vector2(pg.mouse.get_pos())
            mpos = mpos / pre.RENDER_SCALE
            tile_pos = pg.Vector2(tuple(map(int, (mpos + self.scroll) // self.tilemap.tile_size)))

            # preview: at cursor the next tile to be placed
            if self.ongrid:
                self.display.blit(cur_tile_img, tile_pos * self.tilemap.tile_size - self.scroll)
            else:  # notice smooth off grid preview
                self.display.blit(cur_tile_img, mpos)

            if self.clicking and self.ongrid:
                self.tilemap.tilemap[f"{int(tile_pos[0])};{int(tile_pos[1])}"] = TileItem(kind=pre.TileKind(self.tile_list[self.tile_group]), variant=self.tile_variant, pos=tile_pos)
            if self.right_clicking:  # remove tile
                tile_loc = f"{int(tile_pos[0])};{int(tile_pos[1])}"
                if tile_loc in self.tilemap.tilemap:
                    del self.tilemap.tilemap[tile_loc]

                for tile in self.tilemap.offgrid_tiles.copy():
                    t_pos = tuple(tile.pos)
                    t_img = self.assets.tiles[tile.kind.value][tile.variant]
                    tile_r = pg.Rect(t_pos[0] - self.scroll[0], t_pos[1] - self.scroll[1], t_img.get_width(), t_img.get_height())
                    if tile_r.collidepoint(mpos):
                        self.tilemap.offgrid_tiles.remove(tile)

            self.display.blit(cur_tile_img, ((pre.DIMENSIONS[0] // 2 - pre.TILE_SIZE * 2), 5))  # preview current tile

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()
                if event.type == pg.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.clicking = True
                        if not self.ongrid:
                            self.tilemap.offgrid_tiles.append(TileItem(kind=pre.TileKind(self.tile_list[self.tile_group]), variant=self.tile_variant, pos=mpos + self.scroll))
                    if event.button == 3:  # 2 is when you click down on the mice
                        self.right_clicking = True
                if event.type == pg.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.clicking = False
                    if event.button == 3:
                        self.right_clicking = False
                    if self.shift:
                        if event.button == 4:
                            self.tile_variant -= 1
                            self.tile_variant %= len(self.assets.tiles[self.tile_list[self.tile_group]])
                        if event.button == 5:
                            self.tile_variant += 1
                            self.tile_variant %= len(self.assets.tiles[self.tile_list[self.tile_group]])
                    else:
                        if event.button == 4:
                            self.tile_group -= 1
                            self.tile_group %= len(self.tile_list)
                            self.tile_variant = 0
                        if event.button == 5:
                            self.tile_group += 1
                            self.tile_group %= len(self.tile_list)
                            self.tile_variant = 0
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_a:
                        self.movement.left = True
                    if event.key == pg.K_d:
                        self.movement.right = True
                    if event.key == pg.K_w:
                        self.movement.top = True
                    if event.key == pg.K_s:
                        self.movement.bottom = True
                    if event.key == pg.K_g:
                        self.ongrid = not self.ongrid
                    if event.key == pg.K_t:
                        if False:
                            self.tilemap.autotile()
                    if event.key == pg.K_o:  # o: output
                        if False:
                            self.tilemap.save("map.json")
                    if event.key == pg.K_LSHIFT:
                        self.shift = not self.shift
                if event.type == pg.KEYUP:
                    if event.key == pg.K_a:
                        self.movement.left = False
                    if event.key == pg.K_d:
                        self.movement.right = False
                    if event.key == pg.K_w:
                        self.movement.top = False
                    if event.key == pg.K_s:
                        self.movement.bottom = False

            # DISPLAY RENDERING

            # blit display on display_2 and then blit display_2 on
            # screen for depth effect.

            # self.display_2.blit(self.display, (0, 0))
            #
            # # TODO: screenshake effect via offset for screen blit
            # # ...
            # self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), (0, 0))  # pixel art effect

            # DEBUG: HUD

            self.screen.blit(pg.transform.scale(self.display, self.screen.get_size()), (0, 0))

            if not pre.DEBUG_HUD:
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
                # HUD: show mouse pos
                text = self.font.render(f"MPOS {str(mpos).ljust(4).upper()}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 5))
                # HUD: show tile pos
                text = self.font.render(f"TILEPOS {str(tile_pos).ljust(4).upper()}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 6))
                # HUD: show shift
                text = self.font.render(f"SHIFT {str(self.shift).ljust(4).upper()}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 7))
                # HUD: show if ongrid
                text = self.font.render(f"ONGRID {str(self.ongrid).ljust(4).upper()}", antialias, pre.GREEN, None)
                self.screen.blit(text, (pre.TILE_SIZE, pre.TILE_SIZE * 8))

            pg.display.flip()  # update whole screen
            self.clock.tick(pre.FPS_CAP)  # note: returns delta time (dt)


if __name__ == "__main__":
    Editor().run()
