# vim: modeline

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import pygame as pg

import internal.prelude as pre
from internal.assets import Assets
from internal.tilemap import TileItem, Tilemap, pos_to_loc


class Editor:
    def __init__(self, level_id: Optional[int] = None) -> None:
        pg.init()

        display_flags = pg.HWSURFACE | pg.DOUBLEBUF | pg.NOFRAME

        self.screen = pg.display.set_mode(pre.DIMENSIONS, display_flags)
        pg.display.set_caption(pre.CAPTION_EDITOR)

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)

        self.font_size = pre.TILE_SIZE - 4
        self.font = pg.font.SysFont(name=("monospace" or pg.font.get_default_font()), size=self.font_size, bold=True)

        self.clock = pg.time.Clock()

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        self.assets = Assets.initialize_assets().editor_view

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.save_generation: int = 0
        self.last_save_time: None | float = None
        self.last_save_time_readable: None | str = None

        # NOTE: custom level loading from here.. available levels==[0,1]
        # level =

        self.level = level_id if level_id is not None else 0
        self.load_level(self.level)

    def load_level(self, map_id: int) -> None:
        # path=os.path.join(pre.MAP_PATH, f"{map_id}.json")
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

    def run(self) -> None:
        while True:
            self.display.fill(pre.COLOR.BACKGROUND)

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
            tile_pos = pg.Vector2(tuple(map(int, (mpos + self.scroll) // self.tilemap.tilesize)))

            # preview: at cursor the next tile to be placed
            if self.ongrid:
                self.display.blit(cur_tile_img, tile_pos * self.tilemap.tilesize - self.scroll)
            else:  # notice smooth off grid preview
                self.display.blit(cur_tile_img, mpos)

            if self.clicking and self.ongrid:  # tile: add
                self.tilemap.tilemap[pos_to_loc(tile_pos.x, tile_pos.y, None)] = TileItem(kind=pre.TileKind(self.tile_list[self.tile_group]), variant=self.tile_variant, pos=tile_pos)
            if self.right_clicking:  # tile: remove
                if (tile_loc := pos_to_loc(tile_pos.x, tile_pos.y, None)) and tile_loc in self.tilemap.tilemap:
                    del self.tilemap.tilemap[tile_loc]

                for tile in self.tilemap.offgrid_tiles.copy():
                    t_img = self.assets.tiles[tile.kind.value][tile.variant]
                    tile_r = pg.Rect(tile.pos.x - self.scroll.x, tile.pos.y - self.scroll.y, t_img.get_width(), t_img.get_height())
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
                            self.tilemap.offgrid_tiles.add(TileItem(kind=pre.TileKind(self.tile_list[self.tile_group]), variant=self.tile_variant, pos=mpos + self.scroll))
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
                    if event.key == pg.K_o:  # o: output
                        if not self.last_save_time or (t := time.time(), dt := t - self.last_save_time) and dt >= 0.12:
                            # path=os.path.join(pre.MAP_PATH, f"{self.level}.json")
                            self.tilemap.save(str(Path(pre.MAP_PATH) / f"{self.level}.json"))
                            self.last_save_time = time.time()
                            self.last_save_time_readable = time.asctime()
                            self.save_generation += 1
                        else:
                            raise ValueError(f"Something went wrong. Saving too fast. Please debounce. {t, dt}")
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

            # DISPLAY: RENDERING

            self.screen.blit(pg.transform.scale(self.display, self.screen.get_size()), (0, 0))

            # DEBUG: HUD

            if pre.DEBUG_EDITOR_HUD:
                antialias = True
                key_w = 11  # TILEVARMODE key
                val_w = 10  # LASTSAVE value | max overflow is 24 for local time readable
                key_fillchar = " "
                val_fillchar = " "  # non monospace fonts look uneven vertically in tables
                hud_elements = [
                    (f"{text.split('.')[0].rjust(key_w,key_fillchar)}{key_fillchar*2}{text.split('.')[1].rjust(val_w,val_fillchar)}" if '.' in text else f"{text.ljust(val_w,val_fillchar)}")
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
                    blit_text(self.font.render(text, antialias, pre.GREEN, None), (pre.TILE_SIZE, pre.TILE_SIZE + index * line_height))

            pg.display.flip()  # update whole screen
            self.clock.tick(pre.FPS_CAP)  # note: returns delta time (dt)


if __name__ == "__main__":
    """
    usage: editor.py [-h]

    options:
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

# The line beneath this is called `modeline`. See `:help modeline`
# vim: ts=2 sts=2 sw=2 et
