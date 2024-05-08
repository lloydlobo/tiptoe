from __future__ import annotations

import math
from functools import partial
from typing import TYPE_CHECKING, Optional

import pygame as pg

import internal.prelude as pre


if TYPE_CHECKING:
    from tiptoe import Game


def render_debug_hud(game: Game, surface: pg.SurfaceType, render_scroll: tuple[int, int], mouse_pos: Optional[tuple[int, int]] = None) -> None:
    t_size = pre.TILE_SIZE
    antialias = True
    key_w = 14
    val_w = 14
    line_height = math.floor(game.font.get_linesize() / 2)
    text_color = pre.Palette.COLOR0
    key_fillchar = " "
    val_fillchar = " "  # non monospace fonts look uneven vertically in tables

    collisions_bitmap_str = " ".join(((k[0] + ('#' if v else ' ')) for k, v in game.player.collisions.__dict__.items())).upper().split(',')[0]
    movement_bitmap_str = " ".join(list((k[0] + str(int(v))) for k, v in game.movement.__dict__.items())[0:2]).upper().split(',')[0]
    player_action = val.value.upper() if (val := game.player.action) and val else None

    hud_elements = (
        (f"{text.split('.')[0].rjust(key_w,key_fillchar)}{key_fillchar*2}{text.split('.')[1].rjust(val_w,val_fillchar)}" if '.' in text else f"{text.ljust(val_w,val_fillchar)}")
        for text in (
            ##################################
            f"CLOCK_FPS.{game.clock.get_fps():2.0f}",
            f"CLOCK_DT*1000.{game.dt*1000}",
            ###################################
            f"CAM_RSCROLL.{render_scroll.__str__()}",
            f"CAM_SCROLL.{game.scroll.__round__(0)}",
            f"MOUSE_POS.{mouse_pos.__str__()}",
            ##################################
            f"INPT_MVMNT.{movement_bitmap_str}",
            f"MAP_LEVEL.{str(game.level)}",
            ##################################
            f"PLYR_ACTION.{player_action }",
            f"PLYR_ALPHA.{game.player.animation_assets[game.player.action.value].img().get_alpha() if game.player.action else None}",
            f"PLYR_COLLIDE.{collisions_bitmap_str}",
            f"PLYR_FLIP.{str(game.player.flip).upper()}",
            f"PLYR_POS.{game.player.pos.__round__(0)}",
            f"PLYR_VEL.{str(game.player.velocity.__round__(0))}",
            f"PLYR_DASH.{str(game.player.dash_timer)}",
            ##################################
        )
    )

    # TODO: render on a surface then render surface on screen
    # blit_text_partialfn = partial(game.screen.blit)
    # render_font_partial = partial(game.font_hud.render)
    start_row = 16 * 4
    start_col = 16 // 2

    # def draw_text(self, x: int, y: int, font: pg.font.Font, color: pg.Color | pre.ColorValue | pre.ColorKind, text: str):
    font = game.font_hud
    for index, text in enumerate(hud_elements):
        game.draw_text(int(start_row), int(start_col + index * line_height), font, text_color, text)
        # surface.blit(
        #     game.font_hud.render(text, antialias, text_color, None),
        #     dest=(start_row, (start_col + index * line_height)),
        # )
