# vim: modeline

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Counter, Optional, Set, Tuple

import pygame as pg

import internal.prelude as pre
from internal.assets import Assets
from internal.tilemap import TileItem, Tilemap, pos_to_loc


def validate_unique_offgrid_spawners(offgrid_tiles: Set[TileItem] | Any) -> Tuple[bool, str]:
    """Validates spawner variants in tilemap's `offgrid_tiles`."""
    if not isinstance(offgrid_tiles, Set):
        return (False, "Invalid map data format")

    if not offgrid_tiles:  # len==0
        return (False, "Map should contain at least one offgrid tile with spawners")

    spawner_variants = (x.variant for x in offgrid_tiles if x.kind == pre.TileKind.SPAWNERS)
    variant_frequency = Counter(spawner_variants)

    if variant_frequency[pre.SpawnerKind.PLAYER.value] != 1:
        return (False, "There should be exactly one player spawner (variant 0)")
    if variant_frequency[pre.SpawnerKind.ENEMY.value] == 0:
        return False, "There should be atleast one enemy spawner (variant 1)"
    if variant_frequency[pre.SpawnerKind.PORTAL.value] > 1:
        return (False, "Spawner portal should not have multiple instances (variant 2)")

    if variant_frequency[3] != 0:  # 3: flag is collect
        return (False, "There should be no 'flag is collect' spawner (variant 3)")  # not a `SpawnerKind`
    return (True, "")


class Editor:
    def __init__(self, level_id: Optional[int] = None) -> None:
        pg.init()

        display_flags = pg.HWSURFACE | pg.DOUBLEBUF | pg.NOFRAME
        self.screen = pg.display.set_mode(pre.DIMENSIONS, display_flags)
        pg.display.set_caption(pre.CAPTION_EDITOR)
        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)

        self.font_size = pre.TILE_SIZE - 4
        self.font_base = pg.font.SysFont(
            name=("monospace" or pg.font.get_default_font()), size=self.font_size, bold=True
        )
        self.font_sm = pg.font.SysFont(
            name=("monospace" or pg.font.get_default_font()), size=self.font_size - 3, bold=True
        )

        self.clock = pg.time.Clock()

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)
        self.assets = Assets.initialize_assets().editor_view
        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.save_generation: int = 0
        self.last_save_time: None | float = None
        self.last_save_time_readable: None | str = None

        self.level = level_id if level_id is not None else 0
        self.load_level(self.level)

    def run(self) -> None:
        while True:
            self.display.fill(pre.COLOR.BACKGROUND)

            # Camera: Update and Parallax
            self.scroll.x += round(self.movement.right - self.movement.left) * pre.CAMERA_SPEED
            self.scroll.y += round(self.movement.bottom - self.movement.top) * pre.CAMERA_SPEED
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))

            # Tilemap: Render
            self.tilemap.render(self.display, render_scroll)
            cur_tile_img_surf: pg.Surface = self.assets.tiles[self.tile_list[self.tile_group]][self.tile_variant].copy()
            cur_tile_img_surf.set_alpha(255 // 2)
            mpos = pg.Vector2(pg.mouse.get_pos())
            mpos = mpos / pre.RENDER_SCALE
            tile_pos = pg.Vector2(tuple(map(int, (mpos + self.scroll) // self.tilemap.tilesize)))

            # Preview: at cursor the next tile to be placed
            if self.ongrid:
                self.display.blit(cur_tile_img_surf, tile_pos * self.tilemap.tilesize - self.scroll)
            else:
                self.display.blit(cur_tile_img_surf, mpos)  # Notice smooth off-grid preview

            if self.clicking and self.ongrid:  # Tile: add
                ongrid_tile = TileItem(
                    kind=pre.TileKind(self.tile_list[self.tile_group]), variant=self.tile_variant, pos=tile_pos
                )
                self.tilemap.tilemap[pos_to_loc(tile_pos.x, tile_pos.y, None)] = ongrid_tile

            if self.right_clicking:  # tile: remove
                if (tile_loc := pos_to_loc(tile_pos.x, tile_pos.y, None)) and tile_loc in self.tilemap.tilemap:
                    del self.tilemap.tilemap[tile_loc]

                for tile in self.tilemap.offgrid_tiles.copy():
                    t_img = self.assets.tiles[tile.kind.value][tile.variant]
                    tile_r = pg.Rect(
                        tile.pos.x - self.scroll.x, tile.pos.y - self.scroll.y, t_img.get_width(), t_img.get_height()
                    )
                    if tile_r.collidepoint(mpos):
                        self.tilemap.offgrid_tiles.remove(tile)

            # preview current tile
            self.display.blit(cur_tile_img_surf, ((self.display.get_width() - pre.TILE_SIZE * 3), 16))

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    pg.quit()
                    sys.exit()

                if event.type == pg.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.clicking = True
                        if not self.ongrid:
                            offgrid_tile = TileItem(
                                kind=pre.TileKind(self.tile_list[self.tile_group]),
                                variant=self.tile_variant,
                                pos=mpos + self.scroll,
                            )
                            # TODO: validate this tile
                            self.tilemap.offgrid_tiles.add(offgrid_tile)
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
                        self.tilemap.autotile()
                    if event.key == pg.K_LSHIFT:
                        self.shift = not self.shift
                    if event.key == pg.K_o:  # o: output
                        # TODO: push this up if statements and run it on each edit? reason: with error, tiles are still saved
                        if not self.last_save_time or (t := time.time(), dt := t - self.last_save_time) and dt >= 0.12:
                            is_valid, errmsg = validate_unique_offgrid_spawners(self.tilemap.offgrid_tiles)
                            if is_valid and errmsg == "":
                                self.tilemap.save(str(Path(pre.MAP_PATH) / f"{self.level}.json"))
                                self.last_save_time = time.time()
                                self.last_save_time_readable = time.asctime()
                                self.save_generation += 1
                            self.error_message = "" if not errmsg else errmsg
                        else:
                            raise RuntimeError(f"File saved too frequently. Crashing instance intentionally. {t, dt}")
                if event.type == pg.KEYUP:
                    if event.key == pg.K_a:
                        self.movement.left = False
                    if event.key == pg.K_d:
                        self.movement.right = False
                    if event.key == pg.K_w:
                        self.movement.top = False
                    if event.key == pg.K_s:
                        self.movement.bottom = False

            # DISPLAY: RENDERING
            # ------------------------------------------------------------------
            if self.error_message:
                center_x, top_margin = self.display.get_width() // 2, 8
                error_text_surface, error_text_rect = self.to_text(
                    center_x, top_margin, self.font_sm, pre.BLACK, self.error_message
                )
                error_background = pg.Surface(error_text_rect.size).convert_alpha()
                error_background.set_colorkey(pre.BLACK)
                error_background.set_alpha(180)
                error_background.fill(pg.Color("maroon"))
                self.display.blit(error_background, (error_text_rect.x, error_text_rect.y))
                self.display.blit(error_text_surface, error_text_rect)

            if self.last_save_time:
                if time.time() - self.last_save_time <= 2.0:  # show toast for 2 seconds
                    center_x, top_margin = self.display.get_width() // 2, 8
                    self.draw_text(
                        center_x,
                        top_margin,
                        self.font_sm,
                        pg.Color("pink"),
                        f"{self.last_save_time_readable}: '{self.level}.json' saved",
                    )
            self.screen.blit(pg.transform.scale(self.display, self.screen.get_size()), (0, 0))

            if pre.DEBUG_EDITOR_HUD:
                antialias = True
                key_w = 11  # TILEVARMODE key
                val_w = 10  # LASTSAVE value | max overflow is 24 for local time readable
                key_fillchar = " "
                val_fillchar = " "  # Non monospace fonts look uneven vertically in tables
                hud_elements = [
                    (
                        f"{text.split('.')[0].rjust(key_w,key_fillchar)}{key_fillchar*2}{text.split('.')[1].rjust(val_w,val_fillchar)}"
                        if '.' in text
                        else f"{text.ljust(val_w,val_fillchar)}"
                    )
                    for text in [
                        f"FPS.{self.clock.get_fps():2.0f}",
                        f"GRIDMODE.{str(self.ongrid).upper()}",
                        f"LEVEL.{str(self.level)}",
                        f"MPOS.{str(mpos)}",
                        f"RSCROLL.{str(render_scroll)}",
                        f"SAVES.{str(self.save_generation).rjust(2,'0')}",
                        f"SAVETIME.{str(self.last_save_time)}",
                        f"SAVETIMELOC.{str(self.last_save_time_readable)}",
                        f"SCROLL.{str(self.scroll)}",
                        f"TILEGRP.{str(self.tile_group).upper()}",
                        f"TILEGRPNAME.{str(self.tile_list[self.tile_group]).upper()}",
                        f"TILEPOS.{str(tile_pos).upper()}",
                        f"TILEVAR.{str(self.tile_variant).upper()}",
                        f"TILEVARMODE.{str(self.shift).upper()}",
                    ]
                ]

                blit_text, line_height = self.screen.blit, min(self.font_size, pre.TILE_SIZE)
                for index, text in enumerate(hud_elements):
                    blit_text(
                        self.font_base.render(text, antialias, pre.GREEN, None),
                        (pre.TILE_SIZE, pre.TILE_SIZE + index * line_height),
                    )

            pg.display.flip()  # update whole screen
            self.clock.tick(pre.FPS_CAP)  # note: returns delta time (dt)
            # ------------------------------------------------------------------

    def load_level(self, map_id: int) -> None:
        try:
            self.tilemap.load(path=str(Path(pre.MAP_PATH) / f"{map_id}.json"))
        except FileNotFoundError:
            pass

        self.scroll = pg.Vector2(0.0, 0.0)  # camera origin is top-left of screen
        self._scroll_ease = pg.Vector2(0.0625, 0.0625)  # 1/16 (as 16 is a perfect square)
        self.tile_list = list(self.assets.tiles.keys())
        if pre.DEBUG_EDITOR_ASSERTS:
            assert set(self.tile_list) == set(x.value for x in pre.TileKind)

        self.tile_group = 0
        self.tile_variant = 0
        self.clicking = False
        self.right_clicking = False
        self.shift = False
        self.ongrid = True
        self.error_message = ""

    def to_text(
        self,
        x: int,
        y: int,
        font: pg.font.Font,
        color: pre.ColorValue,
        text: str,
        antialias: bool = True,
    ) -> Tuple[pg.SurfaceType, pg.Rect]:
        """Copied from game.py `Game`"""
        surf: pg.SurfaceType = font.render(text, antialias, color)
        rect: pg.Rect = surf.get_rect()
        rect.midtop = (x, y)
        return (surf, rect)

    def draw_text(
        self,
        x: int,
        y: int,
        font: pg.font.Font,
        color: pre.ColorValue,
        text: str,
        antialias: bool = True,
    ) -> pg.Rect:
        """Copied from game.py `Game`"""
        surf = font.render(text, antialias, color)
        rect: pg.Rect = surf.get_rect()
        rect.midtop = (x, y)
        return self.display.blit(surf, rect)


if __name__ == "__main__":
    """Usage: editor.py [-h]

    Options:
      -h, --help  show this help message and exit

    Example::

       $ python src/editor.py 0
       $ python src/editor.py 1

    """
    parser = argparse.ArgumentParser()
    parser.add_argument("level", help="edit map for given level id", type=int)

    args = parser.parse_args()

    ed = Editor(level_id=int(args.level))
    ed.run()
