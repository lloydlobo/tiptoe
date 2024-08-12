# vim: modeline

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Counter, Dict, List, Optional, Set, Tuple

import pygame as pg

import internal.prelude as pre
from internal.assets import Assets
from internal.tilemap import TileItem, Tilemap, pos_to_loc


# spawner_variant_ids = [entity.variant for entity in offgrid_entities if entity.kind == pre.TileKind.SPAWNERS]
#         spawner_variant_frequency = Counter(spawner_variant_ids)
def validate_unique_spawners(map_data: Tilemap | Any) -> Tuple[bool, str]:
    """Validates spawner variants in the map data."""
    print('validating')
    if not isinstance(map_data, Tilemap):
        return (False, "Invalid map data format")

    offgrid_entities = map_data.offgrid_tiles
    if not offgrid_entities:
        return (False, "Map should contain at least one offgrid tile with spawners")

    spawner_variants: List[int] = [x.variant for x in offgrid_entities if x.kind == pre.TileKind.SPAWNERS]
    variant_counts = Counter(spawner_variants)

    print(variant_counts, variant_counts[0])

    # check for specific variant requirements
    if variant_counts[0] != 1:  # 0: PLAYER
        return (False, "There should be exactly one player spawner (variant 0)")
    if variant_counts[1] == 0:  # 1: ENEMY
        return False, "There should be atleast one enemy spawner (variant 1)"
    if variant_counts[2] > 1:  # 2: PORTAL
        return (False, "Spawner portal should not have multiple instances (variant 2)")
    if variant_counts[3] != 0:  # 3: flag is collect
        return (False, "There should be no 'flag is collect' spawner (variant 3)")  # not a `SpawnerKind`

    # unique_variant_count, expected_variant_count = len(set(variant_counts.keys())), len(pre.SpawnerKind._member_map_)
    # if expected_variant_count and unique_variant_count > expected_variant_count:
    #     error_message = f"Invalid unique spawner variant count. Expected: '{expected_variant_count}', Actual: '{unique_variant_count}'."
    #     print(error_message, file=sys.stderr)
    #     return (False, error_message)

    if 0:
        expected_variants: Set[str] = set(pre.SpawnerKind._member_map_.keys())
        actual_variants: Set[str] = {x.kind.value for x in offgrid_entities}
        if not actual_variants.issubset(expected_variants):
            unexpected: Set[str] = actual_variants - expected_variants
            print(actual_variants, expected_variants)
            return (False, f"Unexpected spawner variants found: {unexpected}")

    print(f"Spawner variant frequency: {variant_counts}")
    return (True, "")


def contains_unique_spawners(map_data: Tilemap | Dict[str, Any] | Any) -> Tuple[bool, str]:
    """Checks if map data spawner variants are unique."""
    offgrid_tiles: Set[TileItem] | List[Dict[str, Any]]
    if isinstance(map_data, Tilemap):
        offgrid_tiles = map_data.offgrid_tiles
        if not offgrid_tiles:
            return (False, "Should atleast have offgrid_tiles with spawners")
        print(f"{offgrid_tiles =}")
        spawner_variants: List[int] = [tile.variant for tile in offgrid_tiles if tile.kind == pre.TileKind.SPAWNERS]
        spawner_variants_counter = Counter(spawner_variants)
        actual_total_variants = len(set(spawner_variants_counter.keys()))
        # actual_total_variants = spawner_variants_counter.total()
        if (
            expected_total_variants := len(pre.SpawnerKind._member_map_)
        ) and actual_total_variants > expected_total_variants:
            errmsg = f"Invalid unique spawner variant count. Expected: '{expected_total_variants}', Actual: '{actual_total_variants}'."
            print(
                errmsg,
                file=sys.stderr,
            )
            return (False, errmsg)
        print(f"{spawner_variants_counter, actual_total_variants =}")
        return (True, "")
        # """
        # assert seen_variant_0_count == 1, f"Should have only 1 player spawner"
        # assert seen_variant_1_count == 1, f"Should have only 1 'flag is win' spawner"
        # assert seen_variant_2_count == 0, f"Should have no 'flag is collect' spawner" # note: better to remove it from editor assets
        #
        # """
        # ok = len(spawner_variants) == len(set(spawner_variants))
        # return (ok, "Oops") if not ok else (ok, "")
    elif isinstance(map_data, Dict):  # pyright:ignore[reportUnnecessaryIsInstance]
        offgrid_tiles = map_data["offgrid"]
        assert isinstance(offgrid_tiles, List)
        spawner_variants = [tile["variant"] for tile in offgrid_tiles if tile["kind"] == "spawners"]
        ok = len(spawner_variants) == len(set(spawner_variants))
        return (ok, "Oops") if not ok else (ok, "")
    return False, "oops"


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
                    if event.key == pg.K_o:  # o: output
                        if not self.last_save_time or (t := time.time(), dt := t - self.last_save_time) and dt >= 0.12:
                            # allow_to_save, errmsg = contains_unique_spawners(self.tilemap)
                            allow_to_save, errmsg = validate_unique_spawners(self.tilemap)
                            self.error_message = errmsg if errmsg else ""
                            print(f"{allow_to_save,errmsg = }")
                            if allow_to_save:
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
            # ------------------------------------------------------------------
            if self.error_message:
                center_x = self.display.get_width() // 2
                top_margin = 8
                error_text_surface, error_text_rect = self.to_text(
                    center_x, top_margin, self.font_sm, pre.BLACK, self.error_message
                )

                error_background = pg.Surface(error_text_rect.size).convert_alpha()
                error_background.set_colorkey(pre.BLACK)
                error_background.set_alpha(180)
                error_background.fill(pg.Color("maroon"))

                self.display.blit(error_background, (error_text_rect.x, error_text_rect.y))
                self.display.blit(error_text_surface, error_text_rect)

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
            # ------------------------------------------------------------------
            pg.display.flip()  # update whole screen
            self.clock.tick(pre.FPS_CAP)  # note: returns delta time (dt)
            # ------------------------------------------------------------------


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
