import cProfile
import itertools as it
import math
import time
from collections import deque
from os import listdir, path
from random import randint, random
from sys import exit
from typing import Final

import pygame as pg

import internal.prelude as pre
from internal.assets import Assets
from internal.entities import Action, Enemy, Player
from internal.hud import render_debug_hud
from internal.particle import Particle
from internal.spawner import Portal
from internal.stars import Stars
from internal.tilemap import Tilemap, pos_to_loc


class Game:
    def __init__(self) -> None:
        pg.init()

        display_flags = pg.HWSURFACE | pg.DOUBLEBUF | pg.NOFRAME

        self.screen = pg.display.set_mode(pre.DIMENSIONS, pg.RESIZABLE, display_flags)
        pg.display._set_autoresize(False)  # type: ignore |> see github:pygame/examples/resizing_new.py | Diagnostics: "_set_autoresize" is not a known member of module "pygame.display" [reportAttributeAccessIssue]
        pg.display.set_caption(pre.CAPTION)
        # pg.display.set_caption(f"{pre.CAPTION} - {pg.time.Clock().get_fps():.0f}fps")
        # pg.display.set_caption(f"{pre.CAPTION} - {self.clock.get_fps():.0f}fps")

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        # self.bgcolor = (pre.COLOR.BGMIRAGE, pre.COLOR.BGCOLORDARK, pre.COLOR.BGCOLORDARKER)[randint(0, 2)]
        self.bgcolor = (pre.COLOR.BGMIRAGE, pre.COLOR.BGCOLORDARK)[randint(0, 1)]

        if pre.DEBUG_GAME_STRESSTEST:
            if (__dreamlike := 0) and __dreamlike:
                self.display_3 = pg.Surface(pre.DIMENSIONS_HALF, pg.BLEND_ALPHA_SDL2).convert_alpha()
                pre.Surfaces.compute_vignette(surf=self.display_3)
                self.display_3.set_alpha(17)
            elif (__noir := 1) and __noir:
                display_3_surf_flag = pg.BLEND_ALPHA_SDL2 if randint(0, 1) else pg.BLEND_RGBA_MULT
                self.display_3 = pg.Surface(pre.DIMENSIONS_HALF, display_3_surf_flag).convert_alpha()
                self.display_3.fill(tuple(map(int, pre.COLOR.BGCOLORDARKGLOW)))
                if self.bgcolor == pre.COLOR.BGCOLORDARK:
                    pre.Surfaces.compute_vignette(self.display_3, randint(22, 28))
                elif self.bgcolor == pre.COLOR.BGCOLORDARKER:
                    pre.Surfaces.compute_vignette(self.display_3, 17)
                else:
                    pre.Surfaces.compute_vignette(self.display_3, 23)
                if (__noir_avoid_muddy_spotlight := 1) and __noir_avoid_muddy_spotlight:
                    self.display_3.set_colorkey(pre.BLACK)
            elif (__moody := 0) and __moody:
                self.display_3 = pg.Surface(pre.DIMENSIONS_HALF, pg.BLEND_ALPHA_SDL2).convert_alpha()
                self.display_3.set_colorkey(pre.BLACK)
                self.display_3.set_alpha(255 // 2)
                pre.Surfaces.compute_vignette(surf=self.display_3)
                self.display_3.set_alpha(14)
            else:
                self.display_3 = pg.Surface(pre.DIMENSIONS_HALF, pg.BLEND_RGBA_MULT).convert_alpha()
                self.display_3.fill(tuple(map(int, (174 * 0.2, 226 * 0.2, 255 * 0.3))))
                pre.Surfaces.compute_vignette(self.display_3, 255)
                self.display_3.fill(pre.COLOR.BGCOLORDARKGLOW)
                pre.Surfaces.compute_vignette(self.display_3, randint(10, 20) or min(8, 255 // 13))

        self.font_size = max(10, 11)
        self.font = pg.font.SysFont(name=("monospace"), size=self.font_size, bold=True)  # or name=pg.font.get_default_font()

        self.clock = pg.time.Clock()
        self.clock_dt = 0
        if pre.DEBUG_GAME_HUD:
            self.clock_dt_recent_values: deque[int] = deque([self.clock_dt, self.clock_dt])

        self.config_handler = pre.ConfigHandler(config_path=pre.SRC_PATH / "config.toml")
        try:
            self.config_handler.load_game_config()
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
        # self.playerstar = PlayerStar(
        #     self,
        # )

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        # transition: abs(self.transition) == 30 => opaque screen see nothing | abs(self.transition) == 0 see eeverything; load level when completely black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        self.bg_colors = (pre.hsl_to_rgb(240, 0.3, 0.1), pre.hsl_to_rgb(240, 0.35, 0.1), pre.hsl_to_rgb(240, 0.3, 0.15), pre.COLOR.BGMIRAGE)
        self.bg_color_cycle = it.cycle(self.bg_colors)

        # load_level: declares and initializes level specific members
        self.level = 0
        self.load_level(self.level)
        self._level_map_count: Final[int] = len(listdir(pre.MAP_PATH))

        self._max_screenshake: Final = pre.TILE_SIZE
        self.screenshake = 0
        # if pre.DEBUG_GAME_HUD:
        #     self.render_debug_partialfn = partial()

    def load_level(self, map_id: int) -> None:
        self.tilemap.load(path=path.join(pre.MAP_PATH, f"{map_id}.json"))

        self.projectiles: list[pre.Projectile] = []

        # SPAWNERS
        self.flametorch_spawners = [pg.Rect(4 + torch.pos.x, 4 + torch.pos.y, 23, 13) for torch in self.tilemap.extract([("decor", 2)], keep=True)]
        spawner_kinds = (pre.SpawnerKind.PLAYER, pre.SpawnerKind.ENEMY, pre.SpawnerKind.PORTAL)
        self.portal_spawners: list[Portal] = []
        self.enemies: list[Enemy] = []
        for spawner in self.tilemap.extract(id_pairs=list(zip(it.repeat(str(pre.TileKind.SPAWNERS.value), len(spawner_kinds)), map(int, spawner_kinds))), keep=False):
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

        # Particles go on display, but they are added after the displays merge so they don't receive the outline
        self.particles: list[Particle] = []

        # 1/16 on y axis make camera less choppy and also doesn't hide player falling off the screen at free fall. 1/30 for x axis, gives fast
        # horizontal slinky camera motion! Also 16 is a perfect square. note: camera origin is top-left of screen
        self.scroll = pg.Vector2(0.0, 0.0)
        self._scroll_ease = pg.Vector2(1 / 25, 1 / 25)

        # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead = 0
        self.dead_hit_skipped_counter = 0  # if player is invincible while idle and hit, count amout of shield that is being hit on...
        self.touched_portal = False
        self.transition = self._transition_lo

    def run(self) -> None:
        bg: pg.Surface = self.assets.misc_surf["background"]
        bg.fill(self.bgcolor)

        self.last_tick_recorded = pg.time.get_ticks()
        # _last_get_tick = pg.time.get_ticks()
        running = True
        while running:
            self.display.fill(pre.TRANSPARENT)
            self.display_2.blit(bg, (0, 0))

            self.screenshake = max(0, self.screenshake - 1)

            # transitions: game level
            if (_win_condition := (self.touched_portal or not len(self.enemies))) and _win_condition:
                self.transition += 1
                if self.transition > self._transition_hi:
                    self.level = min(self.level + 1, self._level_map_count - 1)
                    if (__recycle_background_color := 0) and __recycle_background_color:
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

            # Camera: update and parallax
            #   [where we want camera to be]-[where we are or what we have]/25,
            #   So further player is faster camera moves and vice-versa we can
            #   use round on scroll increment to smooth out jumper
            #   scrolling & also multiplying by point zero thirty two instead
            #   of dividing by thirty if camera is off by 1px not an issue, but
            #   rendering tiles could be. note: use 0 round off for smooth camera.
            self.scroll.x += (self.player.rect().centerx - (self.display.get_width() * 0.5) - self.scroll.x) * self._scroll_ease.x
            self.scroll.y += (self.player.rect().centery - (self.display.get_height() * 0.5) - self.scroll.y) * self._scroll_ease.y
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))

            raw_mouse_pos = pg.Vector2(pg.mouse.get_pos()) / pre.RENDER_SCALE
            mouse_pos = raw_mouse_pos + render_scroll

            # Flametorch: particle animation
            odds_of_flame: float = 0.49999 or 49_999 * 0.00001
            self.particles.extend(
                Particle(
                    game=self,
                    p_kind=pre.ParticleKind.FLAME,  # pj_pos = (rect.x + random() * rect.width, rect.y + random() * rect.height)
                    pos=pg.Vector2(
                        x=(flametorch_rect.x + randint(-pre.SIZE.FLAMETORCH[0] // 2, pre.SIZE.FLAMETORCH[0] // 2) - min(pre.SIZE.FLAMETORCH[0] / 2, flametorch_rect.w / 2)),
                        y=(flametorch_rect.y + randint(-pre.SIZE.FLAMEPARTICLE[1], pre.SIZE.FLAMEPARTICLE[1] // 4) - flametorch_rect.h / 2),
                    ),
                    velocity=pg.Vector2(-0.0001, 0.0003),
                    frame=pre.COUNTRAND.FLAMEPARTICLE,
                )
                for flametorch_rect in self.flametorch_spawners.copy()
                if (random() * odds_of_flame) < (flametorch_rect.w * flametorch_rect.h)  # since torch is slim
            )  # big number is to control spawn rate
            self.particles.extend(
                Particle(
                    game=self,
                    p_kind=pre.ParticleKind.FLAMEGLOW,
                    pos=pg.Vector2(
                        x=(flametorch_rect.x + randint(-pre.SIZE.FLAMETORCH[0] // 2, pre.SIZE.FLAMETORCH[0] // 2) - min(pre.SIZE.FLAMETORCH[0] / 4, flametorch_rect.w / 4)),
                        y=(flametorch_rect.y + randint(-pre.SIZE.FLAMEPARTICLE[1] // 2, pre.SIZE.FLAMEPARTICLE[1] // 2) - flametorch_rect.h / 4),
                    ),
                    velocity=pg.Vector2(-0.0001, 0.0003),
                    frame=pre.COUNTRAND.FLAMEPARTICLE,
                )
                for flametorch_rect in self.flametorch_spawners.copy()
                if (random() * odds_of_flame) < (flametorch_rect.w * flametorch_rect.h)
            )  # big number is to control spawn rate

            # stars: backdrop update and render
            self.stars.update()  # stars drawn behind everything else
            self.stars.render(self.display_2, render_scroll)  # display_2 blitting avoids masks depth

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

            # Player: update and render
            if not self.dead:
                self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
                self.player.render(self.display, render_scroll)
            # if not self.dead:
            #     self.playerstar.update()
            #     self.playerstar.render(self.display,render_scroll)

            # Gun: Projectiles
            #   when adding something new to camera like this to the world
            #   always think about how camera should apply on what one is
            #   working on. e.g. HUD does not need camera scroll, but if
            #   working on something in the world, one needs camera scroll.
            #   also other way around, something in the world. Convert from
            #   screen space to world space backwards. Note that halving
            #   dimensions of image gets its center for the camera
            for projectile in self.projectiles:
                projectile.pos[0] += projectile.velocity
                projectile.timer += 1
                img = self.assets.misc_surf["projectile"]
                dest = pg.Vector2(projectile.pos) - render_scroll
                self.display.blit(img, dest)

                # Post projectile render: update
                prj_x, prj_y = int(projectile.pos[0]), int(projectile.pos[1])
                if self.tilemap.maybe_solid_gridtile_bool(pg.Vector2(prj_x, prj_y)):
                    self.projectiles.remove(projectile)
                    # todo: append sparks
                    # self.sfx["hitwall"].play(0.5)
                elif projectile.timer > 360:
                    self.projectiles.remove(projectile)
                elif abs(self.player.dash_time) < self.player.dash_time_burst_2:  # vulnerable player
                    if self.player.rect().collidepoint(prj_x, prj_y):
                        if self.player.action == Action.IDLE and self.dead_hit_skipped_counter < 2:  # player invincible camouflaged one with the world
                            self.projectiles.remove(projectile)
                            self.dead_hit_skipped_counter += 1  # todo: should reset this if players action state changes from idle to something else
                            # self.sfx["hitwall"].play(0.5)
                            pass
                        else:
                            self.projectiles.remove(projectile)
                            self.dead += 1
                            self.dead_hit_skipped_counter = 0
                            self.screenshake = max(self._max_screenshake, self.screenshake - 1)
                            for i in range(30):
                                # todo: append sparks
                                pass
                            # self.sfx["hit"].play(0.5)

            # particles:
            #   perf: add a is_used flag to particle, so as to avoid GC allocating memory
            #   perf: if is_used then don't render, until next reset. so we can cycle through limited amount of particles
            for particle in self.particles:
                match particle.kind:
                    case pre.ParticleKind.FLAME:
                        particle.pos.x += math.sin(particle.animation.frame * 1.035) * 0.3 * randint(-1, 1)
                        kill_animation = particle.update()
                        particle.render(self.display_2, render_scroll)
                        if kill_animation:
                            self.particles.remove(particle)
                        # 0.035 avoids particle to loop from minus one to one, 0.3 controls amplitude
                    case pre.ParticleKind.FLAMEGLOW:
                        particle.pos.x += math.sin(particle.animation.frame * 1.035) * 0.3 * randint(-1, 1)
                        particle.pos.y += math.sin(particle.animation.frame * 1.035) * 0.3
                        kill_animation = particle.update()
                        img = particle.animation.img().copy()
                        self.display_2.blit(
                            source=img,
                            dest=(particle.pos.x - render_scroll[0] - img.get_width() // 2, particle.pos.y - render_scroll[1] - img.get_height() // 1),
                            special_flags=pg.BLEND_RGB_ADD,
                        )
                        if kill_animation:
                            self.particles.remove(particle)
                    case _:
                        pass
            # mask: before particles
            display_mask: pg.Mask = pg.mask.from_surface(self.display)  # 180 alpha to set color of outline or use 255//2
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_silhouette, offset)

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
            if pre.DEBUG_GAME_STRESSTEST:
                self.display.blit(self.display_3, (0, 0))
            self.display_2.blit(self.display, (0, 0))
            # TODO: screenshake effect via offset for screen blit
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
        assert not running

        if pre.DEBUG_GAME_CACHEINFO:  # cache
            print(f"{pre.hsl_to_rgb.cache_info() = }")

        pg.quit()
        exit()


class PlayerStar:
    def __init__(self, game: Game) -> None:
        """
        player: halo summoning: concept glow spot
        """
        self.game = game
        self.halo_radius = pre.SIZE.STAR[0] * 0.64  #  or round((self.player.size.x // 2) * (0.25 or 1))
        self.halo_size = pg.Vector2(self.halo_radius, self.halo_radius)
        self.halo_center = pg.Vector2(160, 120)
        self.halo_surf_size = pre.SIZE.PLAYER
        self.halo_offset_factor = (0, 0.5)[1]  # if 0 then top-left of player is halop center
        self.halo_offset_with_player = self.game.player.size * self.halo_offset_factor

        self.halo_color = pre.COLOR.PLAYERSTAR or pre.PINK or self.game.bg_colors[1]
        self._last_tick = None
        self.halo_surf = pg.Surface(self.halo_surf_size).convert()
        self.halo_surf.set_colorkey(pre.BLACK)

        # halo:update
        self.halo_glitch_speed_multiplier = (0.5) or (random() * 0.618 * randint(6, 9))  # should sync this to "Bee Gees: staying alive bpm"

    def update(self) -> None:
        if 0:
            if (_with_halo_glitch := randint(0, pre.FPS_CAP)) and _with_halo_glitch in {8, 13, 21, 34, 55}:
                if (_cur_tick := pg.time.get_ticks()) - self.game.last_tick_recorded >= (pre.FPS_CAP * self.game.clock.get_time()) * self.halo_glitch_speed_multiplier:
                    self._last_tick = _cur_tick  # cycle through color almost every "one second ^^^^^^^^^^^^^^^
                    self.halo_color = pre.PINK
            else:
                self.halo_color = pre.PINK
        self.halo_dest = self.game.player.pos - (self.halo_size / pre.TILE_SIZE + self.halo_center - self.halo_offset_with_player)
        # self.halo_dest = self.player.pos - (halo_size / 2) - render_scroll

    def render(self, surf: pg.SurfaceType, offset: tuple[int, int]) -> None:
        pg.draw.circle(surface=surf, color=self.halo_color, center=self.halo_center, radius=self.halo_radius)
        self.game.display.blit(source=surf, dest=(self.halo_dest))  # use returned rect in debug HUD
        surf.blit(source=self.halo_surf, dest=(self.halo_dest - offset), special_flags=pg.BLEND_RGB_ADD)  # use returned rect in debug HUD
        pass


if __name__ == "__main__":
    if pre.DEBUG_GAME_PROFILER:
        cProfile.run("Game().load_level(0)", sort="cumulative")
        cProfile.run("Game().run()", sort="cumulative")

    Game().run()
