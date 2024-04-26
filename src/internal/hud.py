from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Optional

import internal.prelude as pre


if TYPE_CHECKING:
    from tiptoe import Game


def render_debug_hud(game: Game, render_scroll: tuple[int, int], mouse_pos: Optional[tuple[int, int]] = None) -> None:
    t_size = pre.TILE_SIZE
    antialias = False
    key_w = 14
    val_w = 14
    line_height = game.font.get_linesize()
    text_color = pre.CREAM
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
            f"CLOCK_DT.{game.clock_dt:2.0f}",
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
            f"PLYR_DASH.{str(game.player.dash_time)}",
            ##################################
        )
    )

    # TODO: render on a surface then render surface on screen
    blit_text_partialfn = partial(game.screen.blit)
    render_font_partial = partial(game.font_hud.render)
    start_row = start_col = t_size * 0.5

    for index, text in enumerate(hud_elements):
        blit_text_partialfn(
            render_font_partial(text, antialias, text_color, None),
            dest=(start_row, (start_col + index * line_height)),
        )
