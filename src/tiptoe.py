import cProfile
import os
import sys
from time import time
from typing import Final

import pygame as pg

import internal.prelude as pre
from internal.entities import Enemy, PhysicalEntity, Player
from internal.tilemap import TileItem, Tilemap


class Game:
    def __init__(self) -> None:
        pg.init()

        pg.display.set_caption(pre.CAPTION)
        self.screen = pg.display.set_mode(pre.DIMENSIONS)
        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.font_size = pre.TILE_SIZE - 4
        self.font = pg.font.SysFont(name=("monospace"), size=self.font_size, bold=True)  # or name=pg.font.get_default_font()

        self.clock = pg.time.Clock()

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)  # figure how to make it optional. have to assign regardless of None

        # need these for reference for animation workaround
        tiles_alpha = 180
        player_size = (8, pre.TILE_SIZE - 1)
        player_run_size = (player_size[0] + 1, player_size[1] - 1)
        player_jump_size = (player_size[0] - 1, player_size[1])
        enemy_size = (8, pre.TILE_SIZE - 1)
        portal_size = (pre.TILE_SIZE, pre.TILE_SIZE)
        player_color = pre.TEAL
        player_run_color = pre.BLACKMID  # use black for invisibility
        player_jump_color = pre.RED
        enemy_color = pre.CREAM
        portal_color = pre.WHITE
        player_alpha = 190

        player_surf = Tilemap.generate_surf(1, player_color, size=player_size, alpha=player_alpha)[0]
        player_run_surf = pg.Surface(player_run_size).convert()
        player_run_surf.set_colorkey(pre.BLACK)
        player_run_surf.fill(player_run_color)
        player_run_surf.set_alpha(11)
        player_jump_surf = pg.Surface(player_jump_size).convert()
        player_jump_surf.set_colorkey(pre.BLACK)
        player_jump_surf.fill(player_jump_color)
        player_jump_surf.set_alpha(player_alpha - 40)

        enemy_surf = pg.Surface(enemy_size).convert()
        enemy_surf.set_colorkey(pre.BLACK)
        enemy_surf.fill(enemy_color)
        portal_surf = pg.Surface(portal_size).convert()
        portal_surf.set_colorkey(pre.BLACK)
        portal_surf.fill(portal_color)

        jump_down_1 = pg.Surface(player_jump_size).convert()
        jump_down_1.set_colorkey(pre.BLACK)
        jump_down_1.fill(player_jump_color)
        jump_down_1.set_alpha(player_alpha - 70)
        jump_down_2 = pg.Surface(player_jump_size).convert()
        jump_down_2.set_colorkey(pre.BLACK)
        jump_down_2.fill(player_jump_color)
        jump_down_2.set_alpha(player_alpha - 80)
        jump_down_3 = pg.Surface(player_jump_size).convert()
        jump_down_3.set_colorkey(pre.BLACK)
        jump_down_3.fill(player_jump_color)
        jump_down_3.set_alpha(player_alpha - 90)
        jump_down_4 = pg.Surface(player_jump_size).convert()
        jump_down_4.set_colorkey(pre.BLACK)
        jump_down_4.fill(player_jump_color)
        jump_down_4.set_alpha(player_alpha - 100)
        jump_down_5 = pg.Surface(player_jump_size).convert()
        jump_down_5.set_colorkey(pre.BLACK)
        jump_down_5.fill(player_jump_color)
        jump_down_5.set_alpha(player_alpha - 140)
        jump_frames = [player_jump_surf, jump_down_1, jump_down_2, jump_down_3, jump_down_4, jump_down_5]

        self.assets = pre.Assets(
            entity=dict(
                # entity
                background=pg.Surface(pre.DIMENSIONS),  # TODO: use actual background image
                enemy=enemy_surf.copy(),
                player=player_surf.copy(),
                # tbd
                gun=pg.Surface((14, 7)),
                projectile=pg.Surface((5, 2)),
            ),
            tiles=dict(
                grass=Tilemap.generate_surf(9, color=pre.BLACK, alpha=tiles_alpha),
                stone=Tilemap.generate_surf(9, color=pre.BLACK, alpha=tiles_alpha),
                decor=Tilemap.generate_surf(4, color=pre.WHITE, size=(pre.TILE_SIZE // 2, pre.TILE_SIZE // 2)),
                large_decor=Tilemap.generate_surf(4, color=pre.BLACK, size=(pre.TILE_SIZE * 2, pre.TILE_SIZE * 2)),
                portal=[portal_surf.copy()],
            ),
            animations_entity=pre.Assets.AnimationEntityAssets(
                player=dict(
                    idle=pre.Animation(Tilemap.generate_surf(9, color=player_color, size=(player_size[0], player_size[1]), alpha=player_alpha, variance=1), img_dur=6),
                    run=pre.Animation(
                        [player_run_surf.copy(), player_run_surf.copy()] or Tilemap.generate_surf(9, color=pre.WHITE, size=player_run_size, alpha=player_alpha + 20, variance=2), img_dur=4
                    ),  # or Tilemap.generate_surf(1, color=player_color, size=player_jump_size, alpha=player_alpha, variance=20),
                    jump=pre.Animation(jump_frames, img_dur=4, loop=False),
                ),
                enemy=dict(
                    idle=pre.Animation([enemy_surf.copy()] or Tilemap.generate_surf(count=8, color=enemy_color, size=(enemy_size[0], enemy_size[1] - 1)), img_dur=6),
                    run=pre.Animation(Tilemap.generate_surf(count=8, color=enemy_color, size=(enemy_size[0], enemy_size[1] - 1)), img_dur=4),
                ),
            ),
            animations_misc=pre.Assets.AnimationMiscAssets(particle=dict()),
        )

        self.sfx = {}

        self.player: Player = Player(self, pg.Vector2(50, 50), pg.Vector2(player_size))

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        # transition: abs(self.transition) == 30 => opaque screen see nothing | abs(self.transition) == 0 see eeverything; load level when completely black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        # load_level: declares and initializes level specific members
        self.level = 1
        self.load_level(self.level)
        self._level_map_count = len(os.listdir(pre.MAP_PATH))
        print(f"{self._level_map_count=}")

        self.screenshake = 0

    def render_debug_hud(self, render_scroll: tuple[int, int]):
        antialias = True
        key_w = 8  # VELOCITY key
        val_w = 10  # LASTSAVE value | max overflow is 24 for local time readable
        key_fillchar = ":"
        val_fillchar = ":"  # non monospace fonts look uneven vertically in tables
        movement_bitmap_str = ':'.join(list((k[0] + str(int(v))) for k, v in self.movement.__dict__.items())[0:2]).upper().split(',')[0]
        player_action = val.value.upper() if (val := self.player.action) and val else None
        hud_elements = [
            (f"{text.split('.')[0].rjust(key_w,key_fillchar)}{key_fillchar*2}{text.split('.')[1].rjust(val_w,val_fillchar)}" if '.' in text else f"{text.ljust(val_w,val_fillchar)}")
            for text in [
                f"ACTION.{player_action }",
                f"FLIP.{str(self.player.flip).upper()}",
                f"FPS.{self.clock.get_fps():2.0f}",
                f"LEVEL.{str(self.level)}",
                f"MVMNT.{movement_bitmap_str}",
                f"POS.{self.player.pos.__round__(0)}",
                f"RSCROLL.{render_scroll.__str__()}",
                f"SCROLL.{self.scroll.__round__(0)}",
                f"VELOCITY.{str(self.player.velocity.__round__(0))}",
            ]
        ]
        blit_text, line_height = self.screen.blit, min(self.font_size, pre.TILE_SIZE)
        for index, text in enumerate(hud_elements):
            blit_text(self.font.render(text, antialias, pre.GREEN, None), (pre.TILE_SIZE, pre.TILE_SIZE + index * line_height))  # note: returns delta time (dt)

    def load_level(self, map_id: int) -> None:
        self.tilemap.load(path=os.path.join(pre.MAP_PATH, f"{map_id}.json"))

        # hack: to avoid resetting the level when `not len(self.enemies)` triggers transition to change level.
        # have to implement enemy spawning and all that jazz

        self.enemies: list[Enemy] = []  # self.enemies.append(Enemy(self, pg.Vector2(50, 50), pg.Vector2(8, 16)))  # FIXME: TEMPORARY HACK
        self.portals: list[TileItem] = []  # unimplemented
        self.spawner_id_pairs = (
            (pre.TileKind.SPAWNERS.value.__str__(), pre.SpawnerKind.PLAYER.value.__int__()),
            (pre.TileKind.SPAWNERS.value.__str__(), pre.SpawnerKind.ENEMY.value.__int__()),
            (pre.TileKind.SPAWNERS.value.__str__(), pre.SpawnerKind.PORTAL.value.__int__()),
        )
        for spawner in self.tilemap.extract(self.spawner_id_pairs, keep_tile=False):
            match spawner.variant:
                case pre.SpawnerKind.PLAYER.value:  # player
                    self.player.pos = spawner.pos.copy()
                    # Implement this to avoid infinite spawns when nowhere to fall aka free fall
                    # note: reset time to avoid multiple spawning after falling down
                    self.player.air_time = 0
                case pre.SpawnerKind.ENEMY.value:  # enemy
                    self.enemies.append(Enemy(self, spawner.pos, pg.Vector2(8, 16)))
                case pre.SpawnerKind.PORTAL.value:  # enemy
                    portal = TileItem(pre.TileKind.PORTAL, variant=spawner.variant, pos=spawner.pos.copy())
                    self.portals.append(portal)
                case _:
                    raise ValueError(f'expect a valid spawners variant. got {spawner.variant, spawner}')
        if pre.DEBUG_GAME_ASSERTS:
            assert (val := len(self.enemies)) and val > 0, f"want atleast 1 spawned enemy. got {val}"
            assert (val := len(self.portals)) and 0 < val < 2, f"want only 1 spawned portal tile. got {val}"

        # 1/16 on y axis make camera less choppy and also doesn't hide player falling off the screen at free fall. 1/30 for x axis, gives fast
        # horizontal slinky camera motion! Also 16 is a perfect square. note: camera origin is top-left of screen
        self.scroll = pg.Vector2(0.0, 0.0)
        self._scroll_ease = pg.Vector2(1 / 30, 1 / 16)

        # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead = 0
        self.transition = self._transition_lo  # -30

    def run(self) -> None:
        bg: pg.Surface = self.assets.entity["background"]
        bg.set_colorkey(pre.BLACK)
        _ = bg.fill(pre.BG_DARK)
        # TODO: parallax clouds like background

        while True:
            _ = self.display.fill(pre.TRANSPARENT)
            _ = self.display_2.blit(bg, (0, 0))

            self.screenshake = max(0, self.screenshake - 1)

            # transitions: game level
            if len(self.portals) == 1 and (p := self.portals[0]):
                if self.player.rect().collidepoint(p.pos):
                    level_clear_time = time().__round__()
                    print(f"==INFO== {level_clear_time} level {self.level} clear")
                    self.transition += 1
                    if self.transition > self._transition_hi:
                        self.level = min(self.level + 1, self._level_map_count - 1)
                        self.load_level(self.level)
            if not len(self.enemies):
                self.transition += 1
                if self.transition > self._transition_hi:
                    self.level = min(self.level + 1, self._level_map_count - 1)
                    self.load_level(self.level)
            if self.transition < self._transition_mid:
                self.transition += 1

            if self.dead:
                self.dead += 1
                if self.dead >= self._dead_mid:  # ease into incrementing for level change till _hi
                    self.transition = min(self._transition_hi, self.transition + 1)
                if self.dead >= self._dead_hi:
                    self.load_level(self.level)

            # camera: update and parallax
            # 'where we want camera to be' - 'where we are or what we have' / '30', so further player is faster camera moves and vice-versa we
            # can use round on scroll increment to smooth out jumper scrolling & also multiplying by point zero thirty two instead of dividing by
            # thirty if camera is off by 1px not an issue, but rendering tiles could be. note: use 0 round off for smooth camera
            #
            self.scroll.x += (self.player.rect().centerx - (self.display.get_width() * 0.5) - self.scroll.x) * self._scroll_ease.x
            self.scroll.y += (self.player.rect().centery - (self.display.get_height() * 0.5) - self.scroll.y) * self._scroll_ease.y
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))

            # tilemap: render
            self.tilemap.render(self.display, render_scroll)

            # portal: update and render
            if len(self.portals) == 1 and (portal := self.portals[0]):
                self.display.blit(source=self.assets.tiles[portal.kind.value][0], dest=portal.pos - render_scroll)

            # if (_enabled_tmp := 0) and _enabled_tmp:
            #     self.portal = self.assets.entity["portal"]
            #     self.portal_pos = pg.Vector2(int(21 * self.tilemap.tile_size), int(4 * self.tilemap.tile_size))
            #     self.display.blit(self.portal, self.portal_pos - render_scroll)

            # enemy: update and render todo:
            # ...

            # player: update and render
            if not self.dead:
                self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
                self.player.render(self.display, render_scroll)

            # if (_enabled_tmp := 0) and _enabled_tmp:
            #     if self.player.rect().collidepoint(self.portal_pos):  # FIXME: Temporary game over hack
            #         print(f"CLEARED {self.level}")
            #         if len(self.enemies):
            #             self.enemies.pop()

            # mask: before particles
            display_mask: pg.Mask = pg.mask.from_surface(self.display)  # 180 alpha to set color of outline or use 255//2
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_silhouette, offset)

            # particles: todo:
            # ...

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
                            pass  # todo: play jump sfx
                if event.type == pg.KEYUP:
                    if event.key == pg.K_LEFT:
                        self.movement.left = False
                    if event.key == pg.K_RIGHT:
                        self.movement.right = False

            # RENDER: DISPLAY
            self.display_2.blit(self.display, (0, 0))  # blit display on display_2 and then blit display_2 on # screen for depth effect.
            # todo: screenshake effect via offset for screen blit
            self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), (0, 0))  # pixel art effect

            if pre.DEBUG_GAME_HUD:
                self.render_debug_hud(render_scroll)

            # DRAW: FINAL DISPLAY
            pg.display.flip()  # update whole screen
            self.clock.tick(pre.FPS_CAP)


if __name__ == "__main__":
    if pre.DEBUG_GAME_PROFILER:
        cProfile.run("Game().load_level(0)", sort="cumulative")

    Game().run()
