from typing import Final, Optional

import pygame as pg

import internal.prelude as pre


__all__ = [
    "SimpleCamera",
]


vec2 = pg.Vector2


def pan_smooth(value: int | float, target: int, dt: Optional[float], smoothness: int | float = 1) -> int | float:
    if dt is None:
        dt = smoothness
    value += (target - value) / smoothness * min(dt, smoothness)
    return value


class SimpleCamera:
    def __init__(self, size: tuple[int, int]) -> None:
        self.size = vec2(size)
        self.camera = pg.Rect(0, 0, self.size.x, self.size.y)
        self.render_scroll = (0, 0)
        self.scroll = vec2(0, 0)

        # Players can tolerate more horizontal camera offset than vertical.
        _ease_x = 2**5 - 2**3  # ideal 28..40
        _ease_y = round(_ease_x * 0.618)  # ideal 16..25
        self.scroll_ease: Final = vec2((1 / _ease_x), 1 / _ease_y)

        self._tmp_target_xy = (0, 0)
        self._camera_font = pg.font.SysFont("monospace", 9, bold=True)
        self.CONST = (self.size.x, self.size.y)

    def reset(self):
        self.scroll = vec2(0, 0)
        self.render_scroll = (0, 0)
        self._tmp_target_xy = (0, 0)

    # map_size: (476, 312)
    def update(
        self, target_pos: tuple[int, int], map_size: Optional[tuple[int, int]] = None, dt: Optional[float] = None
    ) -> None:
        """Update the camera's position based on the target position.

        Args:
            target_pos (tuple[int, int]): The position (x, y) of the target object.

        Simple Version::

            self.scroll.x += (self.player.rect.centerx - (self.display.get_width() * 0.5) - self.scroll.x) * self.scroll_ease.x
            self.scroll.y += (self.player.rect.centery - (self.display.get_height() * 0.5) - self.scroll.y) * self.scroll_ease.y
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))
        """

        # TODO: put player at 1/3 y offset

        target_x = target_pos[0] - self.CONST[0] / 2
        target_y = target_pos[1] - self.CONST[1] / 2

        if map_size:
            # print(map_size,target_pos)
            # This fixes the camera to move to target position, if camera size is buggy or not set based on map/level size
            # smoothness_manual_factor = 2 or pre.FPS_CAP
            # if not dt:
            #     dt = 0.016
            # target_x = pan_smooth(self.scroll.x, target_pos[0], (1000 * dt), 0.5 * smoothness_manual_factor)
            # target_y = pan_smooth(self.scroll.y, target_pos[1], (1000 * dt), 0.5 * smoothness_manual_factor)

            target_x = max(target_x, 0)
            target_x = min(target_x, (map_size[0] - self.CONST[0]))
            target_y = max(target_y, 0)
            target_y = min(target_y, (map_size[1] - self.CONST[1]))
        self._tmp_target_xy = (target_x, target_y)

        self.scroll.x += (target_x - self.scroll.x) * self.scroll_ease.x
        self.scroll.y += (target_y - self.scroll.y) * self.scroll_ease.y
        self.render_scroll = (int(self.scroll.x), int(self.scroll.y))

    def debug(self, surf: pg.SurfaceType, target_pos: tuple[int, int]) -> None:
        """
        Usage::

            self.camera.debug(self.display_2, (int(_target.x), int(_target.y)))
        """
        tx = target_pos[0] - (self.size.x * 0.5)
        ty = target_pos[1] - (self.size.y * 0.5)
        rect = pg.Rect(tx - self.scroll.x, ty - self.scroll.y, self.size.x, self.size.y)

        # draw the boundary
        pg.draw.rect(surf, pre.RED, self.camera, width=2)
        pg.draw.rect(surf, pre.GREEN, rect, width=1)

        # self._draw_text(surf, int(tx), int(ty), self._camera_font, pre.RED, f"Offset {tx,ty}")
        self._draw_text(
            surf,
            int(self.size.x // 2),
            int(self.size.y // 2) - 16 * 4,
            self._camera_font,
            pre.RED,
            f"{self._tmp_target_xy=}",
        )
        self._draw_text(
            surf,
            int(self.size.x // 2),
            int(self.size.y // 2) - 16 * 3,
            self._camera_font,
            pre.RED,
            f"{self.render_scroll=}",
        )
        self._draw_text(
            surf, int(self.size.x // 2), int(self.size.y // 2) - 16 * 2, self._camera_font, pre.GREEN, f"{rect}"
        )
        self._draw_text(
            surf, int(self.size.x // 2), int(self.size.y // 2) - 16 * 1, self._camera_font, pre.BLUE, f"{tx,ty=}"
        )

        # draw target focus point
        pg.draw.circle(surf, pre.GREEN, (tx, ty), 4)

    def _draw_text(
        self,
        surf: pg.SurfaceType,
        x: int,
        y: int,
        font: pg.font.Font,
        color: pg.Color | pre.ColorValue | pre.ColorKind,
        text: str,
    ):
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        rect.midtop = (x, y)
        surf.blit(surface, rect)
