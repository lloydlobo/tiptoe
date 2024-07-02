# file: hud.py

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    LiteralString,
    Optional,
)

import pygame as pg

import internal.prelude as pre


if TYPE_CHECKING:
    from game import Game

# TOP


def draw_text(
    surface: pg.SurfaceType,
    x: int,
    y: int,
    font: pg.font.Font,
    color: pre.ColorValue,
    text: str,
    antialias: bool = True,
) -> pg.Rect:
    textsurf = font.render(text, antialias, color)
    textrect = textsurf.get_rect()
    textrect.midtop = (x, y)
    return surface.blit(textsurf, textrect)


def render_debug_hud(
    game: Game,
    surface: Optional[pg.SurfaceType] = None,
    render_scroll: tuple[int, int] = (0, 0),
    mouse_pos: Optional[tuple[int, int]] = None,
) -> None:
    # Since non-monospace fonts look uneven vertically in tables
    keyfillchar, valfillchar = " ", " "
    keywidth, valwidth = 14, 14

    # Get line height with math.floor(game.font.get_linesize() / 2)
    lineheight = 9
    textcolor = (127, 255, 127)

    playeraction: LiteralString | None = (
        actionkind.value.upper() if ((actionkind := game.player.action) and actionkind) else None
    )

    collisions: Dict[str, Any] = game.player.collisions.__dict__
    collisions_items = collisions.items()
    collisions_iter: Generator[str, None, None] = ((key[0] + ('#' if val else ' ')) for key, val in collisions_items)

    movement: Dict[str, Any] = game.movement.__dict__
    movement_items = movement.items()
    movements_iter: Generator[str, None, None] = ((key[0] + str(int(val))) for key, val in movement_items)

    huditems_iter: Generator[str, None, None] = (
        (
            f"""{key}{spacechars}{val}"""
            if ('.' in item)
            and (
                keyval := item.split('.'),
                key := keyval[0].rjust(keywidth, keyfillchar),
                val := keyval[1].rjust(valwidth, valfillchar),
                spacechars := (2 * keyfillchar),
            )
            else f"{item.ljust(valwidth, valfillchar)}"
        )
        for item in (
            # HUD items
            # -----------------------------------------------------------------
            f"CAM_RSCROLL.{render_scroll.__str__()}",
            f"CAM_SCROLL.{game.scroll.__round__(0)}",
            f"CLOCK_DT*1000.{game.dt*1000}",
            f"CLOCK_FPS.{game.clock.get_fps():2.0f}",
            f"INPT_MVMNT.{' '.join(tuple(movements_iter)[0:2]).upper().split(',')[0]}",  # L0 R0 | L1 R0 | L0 R1 | L1 R1
            f"MAP_LEVEL.{str(game.level)}",
            f"MOUSE_POS.{mouse_pos.__str__()}",
            f"PLYR_ACTION.{playeraction }",
            f"PLYR_COLLIDE.{' '.join(collisions_iter).upper().split(',')[0]}",  # L  R  U  D  | L1 R  U  D  | L  R1  U  D1
            f"PLYR_DASH.{str(game.player.dash_timer)}",
            f"PLYR_FLIP.{str(game.player.flip).upper()}",
            f"PLYR_POS.{game.player.pos.__round__(0)}",
            f"PLYR_VEL.{str(game.player.velocity.__round__(0))}",
            # -----------------------------------------------------------------
        )
    )

    # Draw HUD
    # -------------------------------------------------------------------------
    rowstart, colstart = (16 * 4), (16 // 2)
    rowstart = surface.get_width() - rowstart
    colstart = surface.get_height() - colstart - (13 * lineheight)  # 13 items

    if surface is not None:
        for index, text in enumerate(huditems_iter):
            draw_text(
                surface,
                int(rowstart),
                int(colstart + index * lineheight),
                game.font_hud,
                textcolor,
                text,
            )
    else:
        for index, text in enumerate(huditems_iter):
            game.draw_text(
                int(rowstart),
                int(colstart + index * lineheight),
                game.font_hud,
                textcolor,
                text,
            )
    # -------------------------------------------------------------------------


# BOT
