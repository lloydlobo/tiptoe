import cProfile
import itertools as it
from collections import deque
from functools import partial
from os import listdir, path
from random import randint, random
from sys import exit
from typing import Final, Optional

import pygame as pg

import internal.prelude as pre
from internal.clouds import Clouds
from internal.entities import Enemy, Player
from internal.spawner import Portal
from internal.tilemap import TileItem, Tilemap


class Game:
    def __init__(self) -> None:
        pg.init()

        display_flags = pg.HWSURFACE | pg.DOUBLEBUF | pg.NOFRAME

        self.screen = pg.display.set_mode(pre.DIMENSIONS, pg.RESIZABLE, display_flags)
        pg.display.set_caption(pre.CAPTION)
        pg.display._set_autoresize(False)
        # ^ see github:pygame/examples/resizing_new.py
        # | Diagnostics: "_set_autoresize" is not a known member of module "pygame.display" [reportAttributeAccessIssue]
        # ====

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.font_size = pre.TILE_SIZE - 4
        self.font = pg.font.SysFont(name=("monospace"), size=self.font_size, bold=True)  # or name=pg.font.get_default_font()

        self.clock = pg.time.Clock()
        self._clock_dt = 0
        if pre.DEBUG_GAME_HUD:
            self.clock_dt_recent_values: deque[int] = deque([self._clock_dt, self._clock_dt])

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)  # perf: figure how to make it optional. have to assign regardless of None

        self._enemy_size: Final = pg.Vector2(8, 16)
        self._cloud_count: Final = 16 * 2
        self._bg_color: Final = pre.hsl_to_rgb(240, 0.3, 0.10)

        cloud_color = pre.hsl_to_rgb(60 * 5, 0.26, 0.18)
        cloud_size = (69 / 1.618, 69 / 1.618)
        # print(f"{cloud_size=}")
        cloud_size = tuple(map(lambda x: x**0.328, (69 / 1.618, 69 / 1.618)))
        cloud_surf = pg.Surface(cloud_size).convert()
        cloud_surf.set_colorkey(self._bg_color)
        cloud_surf.fill(cloud_color)  # awesome

        # need these for reference for animation workaround

        player_size = (8, pre.TILE_SIZE - 1)

        enemy_size = (8, pre.TILE_SIZE - 1)
        player_jump_size = (player_size[0] - 1, player_size[1])
        player_run_size = (player_size[0] + 1, player_size[1] - 1)
        portal_size = (max(5, round(player_size[0] * 1.618)), max(18, round(pre.TILE_SIZE + 2)))

        enemy_color = pre.TEAL or pre.CREAM
        player_color = pre.BLACKMID or pre.TEAL
        player_jump_color = pre.RED
        player_run_color = pre.BLACKMID  # use black for invisibility
        portal_1_color = pre.WHITE
        portal_2_color = pre.BEIGE

        player_alpha = 190

        player_surf = list(pre.create_surfaces(1, player_color, size=player_size))[0]
        player_run_surf = pg.Surface(player_run_size).convert()
        player_run_surf.set_colorkey(pre.BLACK)
        player_run_surf.fill(player_run_color)
        player_run_surf.set_alpha(0)
        player_jump_surf = pg.Surface(player_jump_size).convert()
        player_jump_surf.set_colorkey(pre.BLACK)
        player_jump_surf.fill(player_jump_color)
        player_jump_surf.set_alpha(player_alpha - 40)

        enemy_surf = pg.Surface(enemy_size).convert()
        enemy_surf.set_colorkey(pre.BLACK)
        enemy_surf.fill(enemy_color)
        portal_surf_1 = pg.Surface(portal_size).convert()
        portal_surf_1.set_colorkey(pre.BLACK)
        portal_surf_1.fill(portal_1_color)
        portal_surf_2 = pg.Surface(portal_size).convert()
        portal_surf_2.set_colorkey(pre.BLACK)
        portal_surf_2.fill(portal_2_color)

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

        asset_tiles_decor_variations = (
            (2, pre.GREEN, (4, 8)),  # variants 0,1
            (2, pre.YELLOW, (3, 8)),  # variants 2,3
            (2, pre.TEAL, (4, 5)),  # variants 4,5
        )
        asset_tiles_largedecor_variations = (
            (2, pre.GRAY, (32, 16)),  # variants 0,1
            (2, pre.BG_DARK, (32, 16)),  # variants 2,3
            (2, pre.BEIGE, (32, 16)),  # variants 4,5
        )
        decors: list[pg.SurfaceType] = list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_decor_variations)))
        large_decors: list[pg.SurfaceType] = list(it.chain.from_iterable(it.starmap(pre.create_surfaces_partialfn, asset_tiles_largedecor_variations)))

        self.assets = pre.Assets(
            entity=dict(
                enemy=enemy_surf.copy(),
                player=player_surf.copy(),
            ),
            misc_surf=dict(
                background=pg.Surface(pre.DIMENSIONS),  # note: use actual background image
                gun=pg.Surface((14, 7)),
                projectile=pg.Surface((5, 2)),
            ),
            misc_surfs=dict(
                clouds=[cloud_surf.copy() for _ in range(self._cloud_count)],
            ),
            tiles=dict(
                # grid tiles
                stone=list(pre.create_surfaces_partialfn(9, color=pre.BLACKMID or pre.PURPLEMID)),
                grass=list(pre.create_surfaces_partialfn(9, color=pre.BLACKMID or pre.GREEN)),
                # offgrid tiles
                decor=decors,
                large_decor=large_decors,
                portal=[portal_surf_1.copy(), portal_surf_2.copy()],
            ),
            animations_entity=pre.Assets.AnimationEntityAssets(
                player=dict(
                    idle=pre.Animation(list(pre.create_surfaces_partialfn(9, color=player_color, size=(player_size[0], player_size[1]))), img_dur=6),
                    run=pre.Animation([player_run_surf.copy(), player_run_surf.copy()], img_dur=4),
                    jump=pre.Animation(jump_frames, img_dur=4, loop=False),
                ),
                enemy=dict(
                    idle=pre.Animation([enemy_surf.copy()], img_dur=6),
                    run=pre.Animation(list(pre.create_surfaces_partialfn(count=8, color=enemy_color, size=(enemy_size[0], enemy_size[1] - 1))), img_dur=4),
                ),
            ),
            animations_misc=pre.Assets.AnimationMiscAssets(
                particle=dict(
                    flame=pre.Animation(list(pre.create_surfaces_partialfn(4, pre.YELLOW, (1, 1))), img_dur=20, loop=False),  # torch flame particle
                    particle=pre.Animation(list(pre.create_surfaces_partialfn(4, pre.CHARCOAL, (2, 2))), img_dur=20, loop=False),  # player dash particle
                )
            ),
        )

        self.sfx = {
            # TODO:
        }

        self.clouds = Clouds(self.assets.misc_surfs["clouds"], self._cloud_count)
        self.player = Player(self, pg.Vector2(50, 50), pg.Vector2(player_size))

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        # transition: abs(self.transition) == 30 => opaque screen see nothing | abs(self.transition) == 0 see eeverything; load level when completely black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        self.bg_colors = (pre.hsl_to_rgb(240, 0.3, 0.1), pre.hsl_to_rgb(240, 0.35, 0.1), pre.hsl_to_rgb(240, 0.3, 0.15), self._bg_color)
        self.bg_color_cycle = it.cycle(self.bg_colors)

        # load_level: declares and initializes level specific members
        self.level = 0
        self.load_level(self.level)
        self._level_map_count: Final[int] = len(listdir(pre.MAP_PATH))

        self.screenshake = 0

    def load_level(self, map_id: int) -> None:
        self.tilemap.load(path=path.join(pre.MAP_PATH, f"{map_id}.json"))

        # SPAWNERS
        self.torch_spawners = [
            # fmt: off
            pg.Rect(4 + torch.pos.x, 4 + torch.pos.y, 23, 13)
            for torch in self.tilemap.extract([("large_decor", 2)], keep=True)
            # fmt: on
        ]
        self.enemies: list[Enemy] = []
        self.portal_spawners: list[Portal] = []
        spawner_kinds = (pre.SpawnerKind.PLAYER, pre.SpawnerKind.ENEMY, pre.SpawnerKind.PORTAL)
        self._spawner_id_pairs = list(zip(map(str, [pre.TileKind.SPAWNERS.value] * len(spawner_kinds)), map(int, spawner_kinds)))
        if pre.DEBUG_GAME_ASSERTS:
            seen_player_spawn = False
            seen_player_spawners: list[TileItem] = []
        for spawner in self.tilemap.extract(self._spawner_id_pairs, keep=False):
            match pre.SpawnerKind(spawner.variant):
                case pre.SpawnerKind.PLAYER:
                    if pre.DEBUG_GAME_ASSERTS:
                        seen_player_spawners.append(spawner)
                        assert not seen_player_spawn, f"want only one player spawner. got {len(seen_player_spawners), seen_player_spawners=}"
                        seen_player_spawn = True
                    self.player.pos = spawner.pos.copy()  # note: reset time to avoids multiple spawns during fall
                    self.player.air_time = 0

                case pre.SpawnerKind.ENEMY:
                    self.enemies.append(Enemy(self, spawner.pos, self._enemy_size))

                case pre.SpawnerKind.PORTAL:
                    self.portal_spawners.append(Portal(self, pre.EntityKind.PORTAL, pos=spawner.pos, size=pg.Vector2(pre.TILE_SIZE, pre.TILE_SIZE)))

        if pre.DEBUG_GAME_ASSERTS:
            assert (val := len(self.enemies)) and val > 0, f"want atleast 1 spawned enemy. got {val}"
            assert (val := len(self.portal_spawners)) and val > 0, f"want atleast 1 spawned portal. got {val}"

        self.particles: list[Particle] = []  # particles go on display, but they are added after the displays merge so they don't receive the outline
        # 1/16 on y axis make camera less choppy and also doesn't hide player falling off the screen at free fall. 1/30 for x axis, gives fast
        # horizontal slinky camera motion! Also 16 is a perfect square. note: camera origin is top-left of screen
        self.scroll = pg.Vector2(0.0, 0.0)
        self._scroll_ease = pg.Vector2(1 / 30, 1 / 16)

        # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead = 0
        self.touched_portal = False
        self.transition = self._transition_lo  # -30

    def run(self) -> None:
        bg: pg.Surface = self.assets.misc_surf["background"]
        bg.set_colorkey(pre.BLACK)
        bg.fill(self._bg_color)

        if pre.DEBUG_GAME_HUD:
            render_debug_partialfn = partial(self.render_debug_hud)

        if pre.DEBUG_GAME_STRESSTEST:
            i = 0
            j = 0

        _last_get_tick = pg.time.get_ticks()
        running = True
        while running:
            self.display.fill(pre.TRANSPARENT)
            self.display_2.blit(bg, (0, 0))

            # REGION: start | debug: resizable screen
            if pre.DEBUG_GAME_STRESSTEST:
                i += 1
                i = i % self.display.get_width()
                j += i % 2
                j = j % self.display.get_height()
                # self.display.fill((255, 0, 255))
                pg.draw.circle(self.display, (0, 0, 0), (100, 100), 20)
                pg.draw.circle(self.display, (0, 0, 200), (0, 0), 10)
                pg.draw.circle(self.display, (200, 0, 0), (160, 120), 30)
                pg.draw.line(self.display, (250, 250, 0), (0, 120), (160, 0))
                pg.draw.circle(self.display, (255, 255, 255), (i, j), 5)
                #
                # ^ see github:pygame/examples/resizing_new.py
                # ====
            # ENDREGION

            self.screenshake = max(0, self.screenshake - 1)

            # transitions: game level
            if (_win_condition := (self.touched_portal or not len(self.enemies))) and _win_condition:
                self.transition += 1
                if self.transition > self._transition_hi:
                    self.level = min(self.level + 1, self._level_map_count - 1)
                    bg.fill(next(self.bg_color_cycle))
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
            #     'where we want camera to be' - 'where we are or what we have' / '30', so further player is faster camera moves and vice-versa we
            #     can use round on scroll increment to smooth out jumper scrolling & also multiplying by point zero thirty two instead of dividing
            #     by thirty if camera is off by 1px not an issue, but rendering tiles could be. note: use 0 round off for smooth camera
            self.scroll.x += (self.player.rect().centerx - (self.display.get_width() * 0.5) - self.scroll.x) * self._scroll_ease.x
            self.scroll.y += (self.player.rect().centery - (self.display.get_height() * 0.5) - self.scroll.y) * self._scroll_ease.y
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))

            raw_mouse_pos = pg.Vector2(pg.mouse.get_pos()) / pre.RENDER_SCALE
            mouse_pos = raw_mouse_pos + render_scroll

            # torche flame particle: created each frame randomly
            self.particles.extend(
                Particle(game=self, p_kind=pre.ParticleKind.FLAME, pos=pg.Vector2((t_rect.x + random() * t_rect.w, t_rect.y + random() * t_rect.h)), velocity=pg.Vector2(-0.1, 0.3), frame=randint(0, 20))
                for t_rect in self.torch_spawners.copy()
            )

            # clouds: backdrop update and render
            self.clouds.update()  # clouds drawn behind everything else
            if (_enable_cloud_masks := 0) and _enable_cloud_masks:
                self.clouds.render(self.display, render_scroll)
            else:  # display_2 blitting avoids masks depth
                self.clouds.render(self.display_2, render_scroll)

            # tilemap: render
            self.tilemap.render(self.display, render_scroll)

            # portal: detect and render
            if not self.touched_portal:  # <- note: this disappears very fast
                for i, portal in enumerate(self.portal_spawners):
                    if self.player.rect().colliderect(portal.rect()):
                        self.touched_portal = True
                    self.display.blit(portal.assets[i], portal.pos - render_scroll)

            # enemy: update and render
            for enemy in self.enemies.copy():
                kill_animation = enemy.update(self.tilemap, pg.Vector2(0, 0))
                enemy.render(self.display, render_scroll)
                if kill_animation:
                    self.enemies.remove(enemy)

            # player: halo concept glow spot
            # halo:init
            _cloud_size = tuple(map(lambda x: x**0.328, (69 / 1.618, 69 / 1.618)))  # duplicated from above
            halo_radius = _cloud_size[0] * 0.618 or round((self.player.size.x // 2) * (0.25 or 1))
            # print(f"{halo_radius}")
            halo_size = pg.Vector2(halo_radius, halo_radius)
            halo_center = pg.Vector2(160, 120)
            halo_surf_size = self.display.get_size()
            halo_offset_factor = (0, 0.5)[1]  # if 0 then top-left of player is halop center
            halo_offset_with_player = self.player.size * halo_offset_factor
            halo_dest = self.player.pos - (halo_size / pre.TILE_SIZE + halo_center - halo_offset_with_player) - pg.Vector2(render_scroll)
            halo_color = pre.PINK or self.bg_colors[1]
            halo_glitch_speed_multiplier = (0.5) or (random() * 0.618 * randint(6, 9))  # should sync this to "Bee Gees: staying alive bpm"
            # halo:update
            if 0:
                if (_with_halo_glitch := randint(0, pre.FPS_CAP)) and _with_halo_glitch in {8, 13, 21, 34, 55}:
                    if (_cur_tick := pg.time.get_ticks()) - _last_get_tick >= (pre.FPS_CAP * self.clock.get_time()) * halo_glitch_speed_multiplier:
                        _last_get_tick = _cur_tick  # cycle through color almost every "one second ^^^^^^^^^^^^^^^
                        print(f"ON  {_with_halo_glitch=}")
                        halo_color = pre.PINK
                else:
                    # halo_color = tuple(map(int, tuple(pg.Vector3(next(self.bg_color_cycle)) * 1.618)))  # simulate glitch:
                    # halo_color = self.bg_colors[2]
                    halo_color = pre.PINK
                    # print(f"OFF {_with_halo_glitch=}")
            # halo:render
            halo_surf = pg.Surface(halo_surf_size).convert()
            halo_surf.set_colorkey(pre.BLACK)
            if (_tmp_use_alpha := 0) and _tmp_use_alpha:  # ^ remeber to set this as convert_alpha
                halo_alpha = 255
                halo_surf.set_alpha(halo_alpha)
            pg.draw.circle(halo_surf, halo_color, halo_center, halo_radius)
            _ = self.display.blit(halo_surf, (halo_dest))  # use returned rect in debug HUD

            # player: update and render
            if not self.dead:
                self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
                self.player.render(self.display, render_scroll)

            # mask: before particles
            display_mask: pg.Mask = pg.mask.from_surface(self.display)  # 180 alpha to set color of outline or use 255//2
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_silhouette, offset)

            # particles: todo:
            # ...

            for event in pg.event.get():
                if event.type == pg.KEYDOWN and event.key == pg.K_q:
                    running = False
                if event.type == pg.QUIT:
                    running = False
                if event.type == pg.VIDEORESIZE:
                    self.screen = pg.display.get_surface()
                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_LEFT:
                        self.movement.left = True
                    if event.key == pg.K_RIGHT:
                        self.movement.right = True
                    if event.key == pg.K_UP:
                        if self.player.jump():
                            pass  # todo: play jump sfx
                    if event.key == pg.K_DOWN:
                        if self.player.dash():
                            pass  # todo: dash jump sfx
                if event.type == pg.KEYUP:
                    if event.key == pg.K_LEFT:
                        self.movement.left = False
                    if event.key == pg.K_RIGHT:
                        self.movement.right = False

            # RENDER: DISPLAY

            # blit: display on display_2 and then blit display_2 on screen for depth effect
            self.display_2.blit(self.display, (0, 0))
            # todo: screenshake effect via offset for screen blit
            self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), (0, 0))  # pixel art effect

            if pre.DEBUG_GAME_HUD:
                if abs(self.clock_dt_recent_values[0] - self.clock_dt_recent_values[1]) < 2:
                    render_debug_partialfn(render_scroll, mouse_pos)
            if pre.DEBUG_GAME_CACHEINFO:  # cache
                print(f"{pre.hsl_to_rgb.cache_info() = }")

            # DRAW: FINAL DISPLAY
            # update: whole screen
            pg.display.flip()
            self._clock_dt = self.clock.tick(pre.FPS_CAP)

            if pre.DEBUG_GAME_HUD:
                self.clock_dt_recent_values.appendleft(self._clock_dt)
                if len(self.clock_dt_recent_values) == pre.FPS_CAP:
                    self.clock_dt_recent_values.pop()
        # end `while running:`

        assert running == False
        pg.quit()
        exit()

    def render_debug_hud(self, render_scroll: tuple[int, int], mouse_pos: Optional[tuple[int, int]] = None) -> None:
        t_size = pre.TILE_SIZE
        antialias = True
        key_fillchar = " "
        key_w = 12
        screen_height = pre.SCREEN_HEIGHT
        line_height = min(self.font_size, t_size)
        text_color = pre.CREAM
        val_fillchar = " "  # non monospace fonts look uneven vertically in tables
        val_w = 12

        collisions_bitmap_str = ':'.join(list((k[0] + ('#' if v else ' ')) for k, v in self.player.collisions.__dict__.items())).upper().split(',')[0]
        movement_bitmap_str = ':'.join(list((k[0] + str(int(v))) for k, v in self.movement.__dict__.items())[0:2]).upper().split(',')[0]
        player_action = val.value.upper() if (val := self.player.action) and val else None

        hud_elements = (
            (f"{text.split('.')[0].rjust(key_w,key_fillchar)}{key_fillchar*2}{text.split('.')[1].rjust(val_w,val_fillchar)}" if '.' in text else f"{text.ljust(val_w,val_fillchar)}")
            for text in (
                ##################################
                f"CLOCK_FPS.{self.clock.get_fps():2.0f}",
                f"CLOCK_DT.{self._clock_dt:2.0f}",
                ###################################
                f"CAM_RSCROLL.{render_scroll.__str__()}",
                f"CAM_SCROLL.{self.scroll.__round__(0)}",
                f"MOUSE_POS.{mouse_pos.__str__()}",
                ##################################
                f"INPT_MVMNT.{movement_bitmap_str}",
                f"MAP_LEVEL.{str(self.level)}",
                ##################################
                f"PLYR_ACTION.{player_action }",
                f"PLYR_ALPHA.{self.player.animation_assets[self.player.action.value].img().get_alpha() if self.player.action else None}",
                f"PLYR_COLLIDE.{collisions_bitmap_str}",
                f"PLYR_FLIP.{str(self.player.flip).upper()}",
                f"PLYR_POS.{self.player.pos.__round__(0)}",
                f"PLYR_VEL.{str(self.player.velocity.__round__(0))}",
                f"PLYR_DASH.{str(self.player.dash_time)}",
                ##################################
            )
        )

        # todo: render on a surface then render surface on screen
        blit_text_partialfn = partial(self.screen.blit)
        render_font_partial = partial(self.font.render)

        for index, text in enumerate(hud_elements):
            blit_text_partialfn(
                render_font_partial(text, antialias, text_color, pre.PURPLEMID),
                dest=(t_size, screen_height - (t_size + index * line_height)),
            )


# FIN

####################################################################
####################################################################
####################################################################


class Particle:
    def __init__(self, game: Game, p_kind, pos: pg.Vector2, velocity: pg.Vector2 = pg.Vector2(0, 0), frame: int = 0) -> None:
        self.game = game
        self.pos = pos
        self.velocity = velocity
        # self.particles: deque[pg.Vector2] = deque()
        pass

    def update(self) -> None:
        self.pos.x += self.velocity.x
        self.pos.y += self.velocity.y
        pass

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int] = (0, 0)) -> None:
        pass


# class Torch:
#     def __init__(self, pos: pg.Vector2) -> None:
#         self.pos = pos
#         self.particles: deque[pg.Vector2] = deque()
#         self.particle_radius = 4
#         img = pg.Surface((self.particle_radius, self.particle_radius))
#         pg.draw.circle(surface=img, color=(10, 10, 10), center=(self.particle_radius, self.particle_radius), radius=self.particle_radius)
#         self.img = img  # pg.image.load(filename),
#         for p in it.count():
#             self.particles.append(pg.Vector2(randint(0, pre.TILE_SIZE), randint(0, pre.TILE_SIZE)))
#             if p == 16:
#                 break
#
#         # print(f"{self.particles = }")
#
#     def update(self) -> None:
#         for p in self.particles:
#             p.x += 1
#             p.y += 1
#
#     def render(self, surf: pg.SurfaceType, offset: tuple[int, int]) -> None:
#         # filename: Path = Path(pre.IMGS_PATH) / "torch.png"
#         surf.blit(
#             pg.transform.scale(self.img, (pre.TILE_SIZE, pre.TILE_SIZE)),
#             (self.pos - pg.Vector2(offset) * 0.5) * 0.5,
#         )


####################################################################
####################################################################
####################################################################

if __name__ == "__main__":
    if pre.DEBUG_GAME_PROFILER:
        cProfile.run("Game().load_level(0)", sort="cumulative")
        cProfile.run("Game().run()", sort="cumulative")

    Game().run()

####################################################################
####################################################################
####################################################################
