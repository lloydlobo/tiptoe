import cProfile
import itertools as it
import math
from collections import deque
from os import listdir, path
from pathlib import Path
from pprint import pprint
from random import randint, random
from sys import exit
from typing import Final

import pygame as pg

import internal.prelude as pre
from internal.assets import Assets
from internal.entities import Enemy, Player
from internal.hud import render_debug_hud
from internal.particle import Particle
from internal.spawner import Portal
from internal.stars import Stars
from internal.tilemap import Tilemap


class Game:
    def __init__(self) -> None:
        pg.init()

        display_flags = pg.HWSURFACE | pg.DOUBLEBUF | pg.NOFRAME

        self.screen = pg.display.set_mode(pre.DIMENSIONS, pg.RESIZABLE, display_flags)
        pg.display.set_caption(pre.CAPTION)
        pg.display._set_autoresize(False)  # type: ignore |> see github:pygame/examples/resizing_new.py | Diagnostics: "_set_autoresize" is not a known member of module "pygame.display" [reportAttributeAccessIssue]

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.font_size = max(10, 11)
        self.font = pg.font.SysFont(name=("monospace"), size=self.font_size, bold=True)  # or name=pg.font.get_default_font()

        self.clock = pg.time.Clock()
        self.clock_dt = 0
        if pre.DEBUG_GAME_HUD:
            self.clock_dt_recent_values: deque[int] = deque([self.clock_dt, self.clock_dt])

        self.config_handler = pre.ConfigHandler(config_path=pre.SRC_PATH / "config.toml")
        try:
            self.config_handler.load_game_config()
            if 0:
                pprint(self.config_handler.config)
        except Exception as e:
            print(f"Error loading game configuration: {e}")

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)  # perf: figure how to make it optional. have to assign regardless of None

        self._star_count: Final[int] = min(64, max(16, self.config_handler.game_world_stars.get("count", pre.TILE_SIZE * 2)))  # can panic if we get a float or string

        self.assets = Assets.initialize_assets()

        self.sfx = {
            # TODO:
        }

        self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)
        self.player = Player(self, pg.Vector2(50, 50), pg.Vector2(pre.SIZE.PLAYER))

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        # transition: abs(self.transition) == 30 => opaque screen see nothing | abs(self.transition) == 0 see eeverything; load level when completely black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        self.bg_colors = (pre.hsl_to_rgb(240, 0.3, 0.1), pre.hsl_to_rgb(240, 0.35, 0.1), pre.hsl_to_rgb(240, 0.3, 0.15), pre.COLOR.BGCOLOR)
        self.bg_color_cycle = it.cycle(self.bg_colors)

        # load_level: declares and initializes level specific members
        self.level = 0
        self.load_level(self.level)
        self._level_map_count: Final[int] = len(listdir(pre.MAP_PATH))

        self.screenshake = 0
        # if pre.DEBUG_GAME_HUD:
        #     self.render_debug_partialfn = partial()

    def load_level(self, map_id: int) -> None:
        self.tilemap.load(path=path.join(pre.MAP_PATH, f"{map_id}.json"))

        # DECORATIVE SPAWNERS
        self.flametorch_spawners = [pg.Rect(4 + torch.pos.x, 4 + torch.pos.y, 23, 13) for torch in self.tilemap.extract([("decor", 2)], keep=True)]

        spawner_kinds = (pre.SpawnerKind.PLAYER, pre.SpawnerKind.ENEMY, pre.SpawnerKind.PORTAL)
        # TILE SPAWNERS
        self.portal_spawners: list[Portal] = []
        # ENTITY SPAWNERS
        self.enemies: list[Enemy] = []
        for spawner in self.tilemap.extract(
            id_pairs=list(zip(it.repeat(str(pre.TileKind.SPAWNERS.value), len(spawner_kinds)), map(int, spawner_kinds))),
            keep=False,
        ):
            match pre.SpawnerKind(spawner.variant):
                case pre.SpawnerKind.PLAYER:
                    self.player.pos = spawner.pos.copy()  # coerce to a mutable list if pos is a tuple
                    self.player.air_time = 0  # Reset time to avoid multiple spawns during fall
                case pre.SpawnerKind.ENEMY:
                    self.enemies.append(Enemy(self, spawner.pos, pg.Vector2(pre.SIZE.ENEMY)))
                case pre.SpawnerKind.PORTAL:
                    self.portal_spawners.append(Portal(self, pre.EntityKind.PORTAL, spawner.pos, pg.Vector2(pre.TILE_SIZE)))

        if pre.DEBUG_GAME_ASSERTS:
            assert self.player is not None, f"want a spawned player. got {self.player}"
            assert (val := len(self.enemies)) > 0, f"want atleast 1 spawned enemy. got {val}"
            assert (val := len(self.portal_spawners)) > 0, f"want atleast 1 spawned portal. got {val}"

        # Particles go on display, but they are added after the displays merge
        # so they don't receive the outline
        self.particles: list[Particle] = []

        # 1/16 on y axis make camera less choppy and also doesn't hide player falling off the screen at free fall. 1/30 for x axis, gives fast
        # horizontal slinky camera motion! Also 16 is a perfect square. note: camera origin is top-left of screen
        self.scroll = pg.Vector2(0.0, 0.0)
        self._scroll_ease = pg.Vector2(1 / 30, 1 / 16)

        # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead = 0
        self.touched_portal = False
        self.transition = self._transition_lo

    def run(self) -> None:
        bg: pg.Surface = self.assets.misc_surf["background"]
        bg.set_colorkey(pre.BLACK)
        bg.fill(pre.COLOR.BGCOLOR)

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
                i += 1  # type: ignore
                i = i % self.display.get_width()
                j += i % 2  # type: ignore
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
            #   x=torch_rect.x + (random() * torch_rect.w),
            #   y=torch_rect.y + (random() * torch_rect.h),
            #   x=randint(-1, 1),
            #   or torch_rect.y + (-1 * randint(-2, 8)) - torch_rect.h / 2, # shorter flame
            #   x=(torch_rect.x + randint(-1, 1) * pre.SIZE.FLAMETORCH[0] - min(pre.SIZE.FLAMETORCH[1] / 2, torch_rect.w / 2)),
            #   y=torch_rect.y + (-1 * randint(-pre.SIZE.FLAMEPARTICLE[1], pre.SIZE.FLAMEPARTICLE[1])) - torch_rect.h,  # longer flame
            self.particles.extend(
                Particle(
                    game=self,
                    p_kind=pre.ParticleKind.FLAME,
                    pos=pg.Vector2(
                        x=(flametorch_rect.x + randint(-pre.SIZE.FLAMETORCH[0], pre.SIZE.FLAMETORCH[0]) - min(pre.SIZE.FLAMETORCH[1] / 2, flametorch_rect.w / 2)),
                        y=(flametorch_rect.y + randint(-pre.SIZE.FLAMEPARTICLE[1], pre.SIZE.FLAMEPARTICLE[1] // 8) - flametorch_rect.h / 2),
                    ),
                    velocity=pg.Vector2(-0.1, 0.3),
                    frame=pre.COUNTRAND.FLAMEPARTICLE,
                )
                for flametorch_rect in self.flametorch_spawners.copy()
                if random() * (49_999 / 10_000) < (flametorch_rect.w * flametorch_rect.h)  # since torch is slim
            )  # big number is to control spawn rate

            # stars: backdrop update and render
            self.stars.update()  # stars drawn behind everything else
            if (_enable_star_masks := 0) and _enable_star_masks:
                self.stars.render(self.display, render_scroll)
            else:  # display_2 blitting avoids masks depth
                self.stars.render(self.display_2, render_scroll)

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

            if 1:
                # player: halo concept glow spot
                # TODO: init halo sprite in load or init methods.... and choose a smaller surface no whole screen-size to blit circle on
                # halo:init
                halo_radius = pre.SIZE.STAR[0] * 0.64  #  or round((self.player.size.x // 2) * (0.25 or 1))
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
                            halo_color = pre.PINK
                    else:
                        halo_color = pre.PINK
                # halo:render
                halo_surf = pg.Surface(halo_surf_size).convert()
                halo_surf.set_colorkey(pre.BLACK)
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

            # particles:
            #   perf: add a is_used flag to particle, so as to avoid GC allocating memory
            #   perf: if is_used then don't render, until next reset. so we can cycle through limited amount of particles
            for particle in self.particles:
                kill_animation = particle.update()
                particle.render(self.display, render_scroll)
                if kill_animation:
                    self.particles.remove(particle)

                # 0.035 avoids particle to loop from minus one to one
                # 0.3 controls amplitude
                if particle.kind == pre.ParticleKind.FLAME:
                    particle.pos.x += math.sin(particle.animation.frame * 1.035) * 0.3 * randint(-1, 1) // 2
                    pass

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
                if pre.DEBUG_GAME_STRESSTEST and (abs(self.clock_dt_recent_values[0] - self.clock_dt_recent_values[1]) < 2):
                    render_debug_hud(self, render_scroll=render_scroll, mouse_pos=(int(mouse_pos.x), int(mouse_pos.y)))
                else:
                    render_debug_hud(self, render_scroll=render_scroll, mouse_pos=(int(mouse_pos.x), int(mouse_pos.y)))

            # DRAW: FINAL DISPLAY
            pg.display.flip()  # update: whole screen
            self.clock_dt = self.clock.tick(pre.FPS_CAP)

            if pre.DEBUG_GAME_HUD:
                self.clock_dt_recent_values.appendleft(self.clock_dt)
                if len(self.clock_dt_recent_values) == pre.FPS_CAP:
                    self.clock_dt_recent_values.pop()

        # end `while running:`
        assert running == False

        if pre.DEBUG_GAME_CACHEINFO:  # cache
            print(f"{pre.hsl_to_rgb.cache_info() = }")

        pg.quit()
        exit()


if __name__ == "__main__":
    if pre.DEBUG_GAME_PROFILER:
        cProfile.run("Game().load_level(0)", sort="cumulative")
        cProfile.run("Game().run()", sort="cumulative")

    Game().run()
