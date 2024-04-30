# Primer: https://www.pygame.org/docs/tut/newbieguide.html

try:
    import cProfile
    import itertools as it
    import math
    import sys
    import time
    from collections import deque
    from dataclasses import dataclass, field
    from enum import IntEnum, auto
    from functools import partial
    from os import listdir, path
    from pathlib import Path
    from pprint import pprint  # pyright: ignore
    from random import randint, random
    from typing import Final, NoReturn, Optional

    if sys.version_info >= (3, 12):
        from types import GenericAlias  # pyright: ignore

    import pygame as pg

    import internal.prelude as pre
    from internal.assets import Assets
    from internal.entities import Action, Enemy, Player
    from internal.hud import render_debug_hud
    from internal.move_commands import test__internal__move__commands__py
    from internal.particle import Particle
    from internal.spark import Spark
    from internal.spawner import Portal
    from internal.stars import Stars
    from internal.tilemap import Tilemap
except ImportError as e:
    print(f"{e}")
    exit(2)


def quit_exit() -> NoReturn:
    if pre.DEBUG_GAME_CACHEINFO:  # lrucache etc...
        print(f"{pre.hsl_to_rgb.cache_info() = }")
    pg.quit()
    sys.exit()


def get_user_config(filepath: Path) -> pre.UserConfig:
    config: Optional[dict[str, str]] = pre.UserConfig.read_user_config(filepath=filepath)
    if not config:
        print("error while reading configuration file at", repr(filepath))
        return pre.UserConfig.from_dict({})
    return pre.UserConfig.from_dict(config)


class AppState(IntEnum):
    GAMESTATE = auto(0)
    MENUSTATE = auto()


class GameState(IntEnum):
    PLAY = auto(0)
    PAUSE = auto()
    EXIT = auto()


@dataclass
class Button:
    text: str
    pos: pg.Vector2
    size: pg.Vector2
    rect: pg.Rect = field(default_factory=lambda: pg.Rect(0, 0, pre.TILE_SIZE * 4, pre.TILE_SIZE * 3))

    def draw(self, surf: pg.SurfaceType, fill_color: pre.ColorValue) -> None:
        pg.draw.rect(surf, fill_color, self.rect)


@dataclass
class Textz:
    font: pg.font.FontType
    bold: bool = False

    # def __post_init__(self):
    #     self.font = pg.font.SysFont("monospace", self.font_size, bold=self.bold)

    def render(self, surf: pg.SurfaceType, pos: tuple[int, int], text: str, color: pre.ColorValue = pg.Color('white')):
        text_surface = self.font.render(text, True, color)
        text_rect = text_surface.get_rect(center=pos)
        surf.blit(text_surface, text_rect)


@dataclass
class LevelCheckpoints:
    level: int
    checkpoint: int  # 0 is level 1 start
    pos: pg.Vector2
    time: float
    # history: dict[int, int]


class Game:
    def __init__(self) -> None:
        pg.init()
        display_flags = pg.DOUBLEBUF | pg.NOFRAME | pg.HWSURFACE  # hwsurface flag does nothing in pygameg ver2.0+, doublebuf has someuse, but not a magic speed up flag. see https://www.pygame.org/docs/tut/newbieguide.html

        self.screen = pg.display.set_mode(pre.DIMENSIONS, pg.RESIZABLE, display_flags)
        pg.display._set_autoresize(False)  # type: ignore ^ |> see github:pygame/examples/resizing_new.py | Diagnostics: "_set_autoresize" is not a known member of module "pygame.display" [reportAttributeAccessIssue]
        pg.display.set_caption(pre.CAPTION)

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.bgcolor = pre.COLOR.BGMIRAGE or (pre.COLOR.BGMIRAGE, pre.COLOR.BGCOLORDARK)[randint(0, 1)]

        self.fontface_path = pre.FONT_PATH / "8bit_wonder" / "8-BIT WONDER.TTF"  # note: font author suggest using font size in multiples of 9.
        self.font = pg.font.Font(self.fontface_path, 18)  # alias for self.font_base -> [ xxs xs sm base md lg ]
        self.font_sm = pg.font.Font(self.fontface_path, 12)  # author suggest using font size in multiples of 9.
        self.font_xs = pg.font.Font(self.fontface_path, 9)  # author suggest using font size in multiples of 9.

        if pre.DEBUG_GAME_HUD:
            try:
                self.font_hud = pg.font.SysFont(name=("Julia Mono"), size=12, bold=True)
            except:
                self.font_hud = pg.font.SysFont(name=("monospace"), size=11, bold=True)

        self.clock = pg.time.Clock()
        self.dt: float = 0.0  # delta time == 1 / framerate(fps) or pygame.clock.tick() / 1000
        if pre.DEBUG_GAME_HUD:
            self.clock_dt_recent_values: deque[pre.Number] = deque([self.dt, self.dt])

        self.config_handler = get_user_config(pre.CONFIG_PATH)

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)
        self._star_count: Final[int] = min(64, max(16, self.config_handler.star_count or pre.TILE_SIZE * 2))  # can panic if we get a float or string

        self.assets = Assets.initialize_assets()

        @dataclass
        class SFX:
            """Sound Effects"""

            ambienceheartbeatloop: pg.mixer.Sound
            ambienceportalnear: pg.mixer.Sound
            dash: pg.mixer.Sound
            dashbassy: pg.mixer.Sound
            hit: pg.mixer.Sound
            hitmisc: pg.mixer.Sound
            hitwall: pg.mixer.Sound
            jump: pg.mixer.Sound
            jumplanding: pg.mixer.Sound
            playerspawn: pg.mixer.Sound
            portaltouch: pg.mixer.Sound
            shoot: pg.mixer.Sound
            shootmiss: pg.mixer.Sound

        self.sfx = SFX(
            ambienceheartbeatloop=pg.mixer.Sound((pre.SFX_PATH / "ambienceheartbeatloop.wav").__str__()),
            ambienceportalnear=pg.mixer.Sound((pre.SFX_PATH / "ambienceportalnear.wav").__str__()),
            dash=pg.mixer.Sound((pre.SFX_PATH / "dash.wav").__str__()),
            dashbassy=pg.mixer.Sound((pre.SFX_PATH / "dashbassy.wav").__str__()),
            hit=pg.mixer.Sound((pre.SFX_PATH / "hit.wav").__str__()),
            hitmisc=pg.mixer.Sound((pre.SFX_PATH / "hitmisc.wav").__str__()),
            hitwall=pg.mixer.Sound((pre.SFX_PATH / "hitwall.wav").__str__()),
            jump=pg.mixer.Sound((pre.SFX_PATH / "jump.wav").__str__()),
            jumplanding=pg.mixer.Sound((pre.SFX_PATH / "jumplanding.wav").__str__()),
            playerspawn=pg.mixer.Sound((pre.SFX_PATH / "playerspawn.wav").__str__()),
            portaltouch=pg.mixer.Sound((pre.SFX_PATH / "portaltouch.wav").__str__()),
            shoot=pg.mixer.Sound((pre.SFX_PATH / "shoot.wav").__str__()),
            shootmiss=pg.mixer.Sound((pre.SFX_PATH / "shootmiss.wav").__str__()),
        )

        self.sfx.ambienceheartbeatloop.set_volume(0.5)  # note: loop it
        self.sfx.ambienceportalnear.set_volume(0.5)
        self.sfx.dash.set_volume(0.2)
        self.sfx.dashbassy.set_volume(0.2)
        self.sfx.hit.set_volume(0.2)
        self.sfx.hitmisc.set_volume(0.2)
        self.sfx.hitwall.set_volume(0.2)
        self.sfx.jump.set_volume(0.15)
        self.sfx.jumplanding.set_volume(0.02)
        self.sfx.playerspawn.set_volume(0.2)
        self.sfx.portaltouch.set_volume(0.2)
        self.sfx.shoot.set_volume(0.1)
        self.sfx.shootmiss.set_volume(0.2)

        self._player_starting_pos: Final = pg.Vector2(104, 145) or pg.Vector2(50, 50)
        # self.mut_player_last_pos = self._player_starting_pos.copy()

        self.player = Player(self, self._player_starting_pos.copy(), pg.Vector2(pre.SIZE.PLAYER))

        self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)
        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.screenshake = 0
        self.gameover = False

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        # Transition: abs(self.transition) == 30 => opaque screen see nothing |
        #   abs(self.transition) == 0 see eeverything; load level when completely black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        self.bg_colors = (pre.hsl_to_rgb(240, 0.3, 0.1), pre.hsl_to_rgb(240, 0.35, 0.1), pre.hsl_to_rgb(240, 0.3, 0.15), pre.COLOR.BGMIRAGE)
        self.bg_color_cycle = it.cycle(self.bg_colors)  # this returns copies with next fn call

        # load_level: declares and initializes level specific members
        self.level = 0
        self.checkpoints: deque[LevelCheckpoints] = deque()
        self._level_map_count: Final[int] = len(listdir(pre.MAP_PATH))
        self._max_screenshake: Final = pre.TILE_SIZE

        self.load_level(self.level)

    def reset_game(self) -> None:
        self.clock = pg.time.Clock()
        self.dt = 0

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)
        self.player = Player(self, self._player_starting_pos.copy(), pg.Vector2(pre.SIZE.PLAYER))

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.screenshake = 0
        self.gameover = False

        self.level = 0

        if len(self.checkpoints):
            self.checkpoints.clear()

        self.load_level(self.level)

    def load_level(self, map_id: int) -> None:
        self.tilemap.load(path=path.join(pre.MAP_PATH, f"{map_id}.json"))

        self.projectiles: list[pre.Projectile] = []
        self.sparks: list[Spark] = []

        # SPAWNERS
        self.flametorch_spawners: list[pg.Rect] = [pg.Rect(4 + torch.pos.x, 4 + torch.pos.y, pre.SIZE.FLAMETORCH[0], pre.SIZE.FLAMETORCH[1]) for torch in self.tilemap.extract([("decor", 2)], keep=True)]
        self.portal_spawners: list[Portal] = []
        self.enemies: list[Enemy] = []
        val_spawner_kinds = (pre.SpawnerKind.PLAYER.value, pre.SpawnerKind.ENEMY.value, pre.SpawnerKind.PORTAL.value)

        for spawner in self.tilemap.extract(id_pairs=list(zip(it.repeat(str(pre.TileKind.SPAWNERS.value), len(val_spawner_kinds)), val_spawner_kinds)), keep=False):
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
        #   horizontal slinky camera motion! Also 16 is a perfect square. note: camera origin is top-left of screen
        self.scroll = pg.Vector2(0.0, 0.0)
        self._scroll_ease = pg.Vector2(1 / 25, 1 / 25)

        # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead = 0
        self.dead_hit_skipped_counter = 0  # if player is invincible while idle and hit, count amout of shield that is being hit on...
        self.touched_portal = False
        if self.level != 0:
            self.sfx.playerspawn.play()

        self.transition = self._transition_lo

        try:
            if len(self.checkpoints):  # note: at reset we are clearing the deque
                recent_checkpoint = self.checkpoints[0]
                if recent_checkpoint.level == self.level and recent_checkpoint.checkpoint != 0 and self.level != 0:
                    self.player.pos = recent_checkpoint.pos
                    print(f"{time.time()} Reloading last checkpoint {recent_checkpoint}")
            else:
                self.checkpoints.appendleft(LevelCheckpoints(self.level, 0, self.player.pos, time.time()))
        except Exception as e:  # deque index out of range
            print(e)  # note: at init we populate deque with first checkpoint. should do this here, to avoid indexing
            quit_exit()

    def run(self) -> None:
        # if (_tmp_with_music := 0) and _tmp_with_music:
        pg.mixer.music.load((pre.SRC_DATA_PATH / "music.wav").__str__())
        pg.mixer.music.set_volume(0.2)
        pg.mixer.music.play(-1)  # -1 => play infinitely

        chan_sfx_ambienceheartbeatloop: pg.mixer.ChannelType = self.sfx.ambienceheartbeatloop.play(-1)
        if self.level == 0:
            self.sfx.playerspawn.play()

        bg: pg.Surface = self.assets.misc_surf["background"]
        bg.fill(self.bgcolor)

        self.last_tick_recorded = pg.time.get_ticks()

        running = True

        while running:
            self.display.fill(pre.TRANSPARENT)
            self.display_2.blit(bg, (0, 0))

            self.screenshake = max(0, self.screenshake - 1)

            # Transitions: game level
            if self.touched_portal or not len(self.enemies):  # win_condition:
                self.transition += 1
                if self.transition > self._transition_hi:
                    try:
                        if self.level + 1 >= self._level_map_count:
                            self.reset_game()
                            self.gameover = True  # since this func is called by mainmenu_screen, it
                            running = False  #      ,will continue on from the loop inside game menu
                        else:
                            # todo: checkpoint logic
                            self.level = min(self.level + 1, self._level_map_count - 1)
                            self.load_level(self.level)
                    except Exception as e:
                        # fixme: antipattern to use Exception?
                        print(e)
                        quit_exit()

            if self.transition < self._transition_mid:
                self.transition += 1

            if self.dead:
                self.dead += 1
                if self.dead >= self._dead_mid:  # ease into incrementing for level change till _hi
                    self.transition = min(self._transition_hi, self.transition + 1)
                if self.dead >= self._dead_hi:
                    if (recent_checkpoint := self.checkpoints[0]) and recent_checkpoint.level == self.level and recent_checkpoint.checkpoint != 0:
                        self.checkpoints.appendleft(LevelCheckpoints(self.level, (recent_checkpoint.checkpoint + 1), self.player.pos, time.time()))
                    self.load_level(self.level)

            # Camera: update and parallax [where we want camera to be]-[where we are or what we have]/25, So further player is faster camera moves and vice-versa we can
            #   use round on scroll increment to smooth out jumper scrolling & also multiplying by point zero thirty two instead of dividing
            #   by thirty if camera is off by 1px not an issue, but rendering tiles could be. note: use 0 round off for smooth camera.
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
                    p_kind=pre.ParticleKind.FLAME,
                    pos=pg.Vector2(
                        x=(rect.x + randint(-pre.SIZE.FLAMETORCH[0] // 2, pre.SIZE.FLAMETORCH[0] // 2) - min(pre.SIZE.FLAMETORCH[0] / 2, rect.w / 2)),
                        y=(rect.y + randint(-pre.SIZE.FLAMEPARTICLE[1], pre.SIZE.FLAMEPARTICLE[1] // 4) - rect.h / 2),
                    ),
                    velocity=pg.Vector2(-0.1, -0.3),
                    frame=randint(0, 20) or pre.COUNTRANDOMFRAMES.FLAMEPARTICLE,
                )  # velocity slightly to left and down, frame these need to be lambdas
                for rect in self.flametorch_spawners.copy()
                if (random() * odds_of_flame) < (rect.w * rect.h)  # since torch is slim
            )  # big number is to control spawn rate
            self.particles.extend(
                Particle(
                    game=self,
                    p_kind=pre.ParticleKind.FLAMEGLOW,
                    pos=pg.Vector2(
                        x=(rect.x + 0.01 * randint(-pre.SIZE.FLAMETORCH[0] // 2, pre.SIZE.FLAMETORCH[0] // 2) - min(pre.SIZE.FLAMETORCH[0] / 4, rect.w / 4)),
                        y=(rect.y + 0.03 * randint(-pre.SIZE.FLAMEPARTICLE[1] // 2, pre.SIZE.FLAMEPARTICLE[1] // 2) - rect.h / 2),
                    ),
                    velocity=pg.Vector2(0.2 * randint(-1, 1), -0.3),
                    frame=randint(0, 20) or pre.COUNTRANDOMFRAMES.FLAMEGLOW,  # these need to be lambdas
                )
                for rect in self.flametorch_spawners.copy()
                if (random() * odds_of_flame * 60) < (rect.w * rect.h)  # random * bignum pixel area (to avoid spawning particles at each frame)
            )  # big number is to control spawn rate

            # Stars: backdrop update and render
            self.stars.update()  # stars drawn behind everything else
            self.stars.render(self.display_2, render_scroll)  # display_2 blitting avoids masks depth

            # Tilemap: render
            self.tilemap.render(self.display, render_scroll)

            # Portal: detect and render
            if not self.touched_portal:  # <- note: this disappears very fast
                for i, portal in enumerate(self.portal_spawners):
                    if self.player.rect().colliderect(portal.rect()):
                        self.touched_portal = True
                        if self.level != self._level_map_count:
                            self.sfx.portaltouch.play()
                    self.display.blit(portal.assets[i], portal.pos - render_scroll)

            # Checkpoints via flametorchs
            if 0:  # FUTURE:
                if len(self.flametorch_spawners):
                    for torch in self.flametorch_spawners:
                        if self.player.rect().colliderect(torch):
                            if self.checkpoints:
                                recent_checkpoint = self.checkpoints[0]
                                if recent_checkpoint.level != self.level:
                                    raise ValueError("impossible condition or logic error in storing checkpoints")
                                # torch_pos = torch.x, torch.y
                                # if recent_checkpoint.checkpoint_pos == torch_pos:
                                #     self.checkpoints[0].time = time.time()
                                self.checkpoints.appendleft(
                                    LevelCheckpoints(
                                        level=self.level,
                                        checkpoint=recent_checkpoint.checkpoint + 1,  # should use key value pair {level: checkpoint}
                                        pos=self.player.pos,
                                        # checkpoint_pos=torch_pos,
                                        time=time.time(),
                                    )
                                )
                                print(f"{self.checkpoints, torch}")
                        pass

            # Enemy: update and render
            for enemy in self.enemies.copy():
                kill_animation = enemy.update(self.tilemap, pg.Vector2(0, 0))
                enemy.render(self.display, render_scroll)
                if kill_animation:
                    self.enemies.remove(enemy)

            # Player: update and render
            if not self.dead:
                self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
                self.player.render(self.display, render_scroll)

            # Gun: Projectiles when adding something new to camera like this to the world always think about how camera should apply on what one is
            #   working on. e.g. HUD does not need camera scroll, but if working on something in the world, one needs camera scroll.
            #   also other way around, something in the world. Convert from screen space to world space backwards. Note that halving dimensions of image gets its center for the camera
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
                    spark_speed, direction = 0.5, math.pi if projectile.velocity > 0 else 0  # unit circle direction (0 left, right math.pi)
                    self.sparks.extend([Spark(projectile.pos, angle=(random() - spark_speed + direction), speed=(random() + 2)) for _ in range(4)])  # projectile hit solid object -> sparks bounce opposite to that direction
                    self.sfx.hitwall.play()
                elif projectile.timer > 360:
                    self.projectiles.remove(projectile)
                elif abs(self.player.dash_time) < self.player.dash_time_burst_2:  # vulnerable player
                    if self.player.rect().collidepoint(prj_x, prj_y):
                        if self.player.action is Action.IDLE and self.dead_hit_skipped_counter < self.player.max_dead_hit_skipped_counter:  # player invincible camouflaged one with the world
                            self.projectiles.remove(projectile)
                            self.dead_hit_skipped_counter += 1  # todo: should reset this if players action state changes from idle to something else
                            self.sparks.extend((Spark(pos=pg.Vector2(self.player.rect().center), angle=random() * math.pi * 2, speed=random() + 2)) for _ in range(30))
                            self.sfx.hitmisc.play()  # invincible player when idle for 3 lifes
                            pass
                        else:  # player leaves world
                            self.projectiles.remove(projectile)
                            self.dead += 1
                            self.dead_hit_skipped_counter = 0
                            self.screenshake = max(self._max_screenshake, self.screenshake - 1)
                            self.sparks.extend((Spark(pos=pg.Vector2(self.player.rect().center), angle=random() * math.pi * 2, speed=random() + 2, color=pre.PINKLIGHT)) for _ in range(30))
                            self.particles.extend(
                                (
                                    Particle(
                                        self,
                                        p_kind=pre.ParticleKind.FLAME,
                                        pos=pg.Vector2(self.player.rect().center),
                                        velocity=(pg.Vector2((math.cos(random() * math.pi * 2 + math.pi) * random() * 5 * 0.5, math.cos(random() * math.pi + math.pi) * random() * math.pi * 0.5))),
                                        frame=randint(0, 7),
                                    )
                                    for _ in range(30)
                                )
                            )
                            self.sfx.hit.play()

            for spark in self.sparks.copy():
                kill_animation = spark.update()
                spark.render(self.display, offset=render_scroll)
                if kill_animation:
                    self.sparks.remove(spark)

            # Display Mask: before particles
            display_mask: pg.Mask = pg.mask.from_surface(self.display)  # 180 alpha to set color of outline or use 255//2
            display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.display_2.blit(display_silhouette, offset)

            # Particles:
            for particle in self.particles.copy():
                match particle.kind:
                    case pre.ParticleKind.FLAME:
                        kill_animation = particle.update()
                        particle.render(self.display, render_scroll)
                        particle.pos.x += math.sin(particle.animation.frame * 0.035) * 0.3  # * randint(-1, 1)
                        if kill_animation:
                            self.particles.remove(particle)
                    case pre.ParticleKind.FLAMEGLOW:  # 0.035 avoids particle to loop from minus one to one of sine function, 0.3 controls amplitude
                        kill_animation = particle.update()
                        img = particle.animation.img().copy()
                        # ideal is display, but display_2 looks cool for flameglow
                        self.display_2.blit(
                            source=img, dest=(particle.pos.x - render_scroll[0] - img.get_width() // 2, particle.pos.y - render_scroll[1] - img.get_height() // 2), special_flags=pg.BLEND_RGB_ADD
                        )  # ^ use center of the image as origin
                        particle.pos.x += math.sin(particle.animation.frame * 0.035) * 0.3
                        if kill_animation:
                            self.particles.remove(particle)
                    case _:
                        pass

            for event in pg.event.get():
                if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                    running = False  # since this func is called by mainmenu_screen, it will continue on from the loop inside game menu
                if event.type == pg.KEYDOWN and event.key == pg.K_q:
                    quit_exit()
                if event.type == pg.QUIT:
                    quit_exit()
                if event.type == pg.VIDEORESIZE:
                    self.screen = pg.display.get_surface()

                if event.type == pg.KEYDOWN:
                    if event.key == pg.K_LEFT:
                        self.movement.left = True
                    if event.key == pg.K_RIGHT:
                        self.movement.right = True
                    if event.key == pg.K_UP:
                        if self.player.jump():
                            self.sfx.jump.play()
                    if event.key == pg.K_DOWN:
                        self.player.dash()
                if event.type == pg.KEYUP:
                    if event.key == pg.K_LEFT:
                        self.movement.left = False
                    if event.key == pg.K_RIGHT:
                        self.movement.right = False

            if random() < 0.0001:  # for application not responding messages(rare)
                pg.event.clear()

            # Render: display
            self.display_2.blit(self.display, (0, 0))  # blit: display on display_2 and then blit display_2 on screen for depth effect
            # TODO: screenshake effect via offset for screen blit
            self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), (0, 0))  # pixel art effect

            if pre.DEBUG_GAME_HUD:
                if pre.DEBUG_GAME_STRESSTEST and (abs(self.clock_dt_recent_values[0] - self.clock_dt_recent_values[1]) < 2):
                    render_debug_hud(self, render_scroll=render_scroll, mouse_pos=(int(mouse_pos.x), int(mouse_pos.y)))
                else:
                    render_debug_hud(self, render_scroll=render_scroll, mouse_pos=(int(mouse_pos.x), int(mouse_pos.y)))

            # Draw: final display
            pg.display.flip()  # update: whole screen
            self.dt = self.clock.tick(pre.FPS_CAP) * 0.001

            if pre.DEBUG_GAME_HUD:
                self.clock_dt_recent_values.appendleft(self.dt)
                if len(self.clock_dt_recent_values) is pre.FPS_CAP:
                    self.clock_dt_recent_values.pop()

        if not running:
            chan_sfx_ambienceheartbeatloop.fadeout(3000)


def loading_screen(game: Game):
    clock = pg.time.Clock()

    loading_screen_duration_sec: Final[float] = 3.0
    fade_in_frame_count: Final = 7  # same as for bullet projectiles
    max_count: Final[int] = math.floor(pre.FPS_CAP * loading_screen_duration_sec)

    bgcolor = pre.CHARCOAL
    w, h = pre.DIMENSIONS_HALF
    base_font_size = 16
    base_font_size *= 3

    cycle_loading_indicator_dots: it.cycle[str] = it.cycle(["   ", "*  ", "** ", "***"])
    title_textz = Textz(game.font, bold=True)
    loading_indicator_textz = Textz(game.font_sm)

    title_textz_offy = 4 * pre.TILE_SIZE

    loading_indicator_textz_offy = math.floor(min(0.618 * (pre.SCREEN_HEIGHT // 2 - title_textz_offy), 8 * pre.TILE_SIZE)) - math.floor(pre.TILE_SIZE * 1.618)

    title_str = pre.CAPTION
    title_textz_drawfn = partial(title_textz.render, pos=(w // 2, h // 2 - title_textz_offy), text=title_str, color=pre.WHITE)

    loading_indicator_textz_drawfn = partial(loading_indicator_textz.render, pos=(w // 2, h - loading_indicator_textz_offy), color=pre.WHITE)
    loading_indicator_text_str = next(cycle_loading_indicator_dots)

    loading_timer = 0
    count = 0

    if pre.DEBUG_GAME_ASSERTS:
        t_start = time.perf_counter()

    while count < max_count:
        game.display.fill(bgcolor)

        if count >= fade_in_frame_count:  # fade in
            if loading_timer >= math.floor(60 * 0.7):
                loading_indicator_text_str = next(cycle_loading_indicator_dots)
                loading_timer = 0
            if count + 75 > max_count:
                loading_indicator_text_str = "  oadingl  "
            if count + 70 > max_count:
                loading_indicator_text_str = " adinglo  "
            if count + 65 > max_count:
                loading_indicator_text_str = " dingloa  "
            if count + 54 > max_count:
                loading_indicator_text_str = " ingload  "
            if count + 44 > max_count:
                loading_indicator_text_str = " ngloadi  "
            if count + 40 > max_count:
                loading_indicator_text_str = " gloadin  "
            if count + 34 > max_count:
                loading_indicator_text_str = " loading  "
            if count + 27 >= max_count:
                loading_indicator_text_str = "  summons  "

            title_textz_drawfn(game.display)
            loading_indicator_textz_drawfn(game.display, text=loading_indicator_text_str)

        # pixel art effect for drop-shadow depth
        display_mask: pg.Mask = pg.mask.from_surface(game.display)
        display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            game.display_2.blit(display_silhouette, offset)

        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                pg.quit()
                sys.exit()
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()

        game.display_2.blit(game.display, (0, 0))
        game.screen.blit(pg.transform.scale(game.display_2, game.screen.get_size()), (0, 0))  # pixel art effect

        pg.display.flip()
        clock.tick(pre.FPS_CAP)

        loading_timer += 1
        count += 1

    if pre.DEBUG_GAME_ASSERTS:
        t_end = time.perf_counter()
        t_elapsed = t_end - t_start  # type: ignore
        ok = count is max_count
        did_not_drop_frames = t_elapsed <= loading_screen_duration_sec
        try:
            assert ok, f"loading_screen: error in {repr('while')} loop execution logic. want {max_count}. got {count}"
            assert did_not_drop_frames, f"error: {t_elapsed=} should be less than {loading_screen_duration_sec=} (unless game dropped frames)"
        except AssertionError as e:
            print(f"loading_screen: AssertionError while loading screen:\n\t{e}", file=sys.stderr)
            pass


def gameover_screen(game: Game):
    clock = pg.time.Clock()

    loading_screen_duration_sec: Final[float] = 2.0
    fade_in_frame_count: Final = 7  # same as for bullet projectiles
    max_count: Final[int] = math.floor(pre.FPS_CAP * loading_screen_duration_sec)

    w, h = pre.DIMENSIONS_HALF
    bgcolor = pre.CHARCOAL
    base_font_size = 16
    base_font_size *= 3

    title_textz = Textz(game.font, bold=True)
    instruction_textz = Textz(game.font_sm, bold=False)

    title_textz_offy = 4 * pre.TILE_SIZE
    loading_indicator_textz_offy = math.floor(min(0.618 * (pre.SCREEN_HEIGHT // 2 - title_textz_offy), 8 * pre.TILE_SIZE)) - math.floor(pre.TILE_SIZE * 1.618)

    title_str = "Game Over"
    instruction_str = f"esc*ape to main menu or q*uit to exit"

    title_textz_drawfn = partial(title_textz.render, pos=(w // 2, h // 2 - title_textz_offy), text=title_str, color=pre.WHITE)
    instruction_textz_drawfn = partial(instruction_textz.render, pos=(w // 2, h - loading_indicator_textz_offy), text=instruction_str, color=pre.WHITE)

    loading_timer = 0
    count = 0

    if pre.DEBUG_GAME_STRESSTEST:
        t_start = time.perf_counter()

    chan_sfx: pg.mixer.ChannelType = game.sfx.ambienceportalnear.play(-1)

    running = True
    while running:  # while count < max_count:
        game.display.fill(bgcolor)

        if count >= fade_in_frame_count:  # fade in
            title_textz_drawfn(game.display)
            instruction_textz_drawfn(game.display)

        # pixel art effect for drop-shadow depth
        display_mask: pg.Mask = pg.mask.from_surface(game.display)
        display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            game.display_2.blit(display_silhouette, offset)

        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                pg.quit()
                sys.exit()
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    chan_sfx.fadeout(2000)
                    try:
                        running = False  # since this func is called by mainmenu_screen, it will continue on from the loop inside game menu
                    except:
                        print(f"something went wrong while running mainmenu_screen from gameover_screen()")
                        quit_exit()

        game.display_2.blit(game.display, (0, 0))
        game.screen.blit(pg.transform.scale(game.display_2, game.screen.get_size()), (0, 0))  # pixel art effect

        pg.display.flip()
        clock.tick(pre.FPS_CAP)

        loading_timer += 1
        count += 1

    if pre.DEBUG_GAME_STRESSTEST:
        t_end = time.perf_counter()
        t_elapsed = t_end - t_start  # type: ignore
        ok = count is max_count
        did_not_drop_frames = t_elapsed <= loading_screen_duration_sec
        try:
            assert ok, f"error in {repr('while')} loop execution logic. want {max_count}. got {count}"
            assert did_not_drop_frames, f"error: {t_elapsed=} should be less than {loading_screen_duration_sec=} (unless game dropped frames)"
        except AssertionError as e:
            print(f"AssertionError while loading screen:\n\t{e}", file=sys.stderr)
            pass
    pass


def options_menu():
    # TODO:
    pass


def mainmenu_screen(game: Game):
    title_textz = Textz(game.font, bold=True)
    instruction_textz = Textz(game.font_sm, bold=False)
    title_textz_offy = 4 * pre.TILE_SIZE
    loading_indicator_textz_offy = math.floor(min(0.618 * (pre.SCREEN_HEIGHT // 2 - title_textz_offy), 8 * pre.TILE_SIZE)) - math.floor(pre.TILE_SIZE * 1.618)
    title_str = "Menu"
    instruction_str = f"return* to enter game or q*uit to exit"
    bgcolor = pre.CHARCOAL
    w, h = pre.DIMENSIONS_HALF
    title_textz_drawfn = partial(title_textz.render, pos=(w // 2, h // 2 - title_textz_offy), text=title_str, color=pre.WHITE)
    instruction_textz_drawfn = partial(instruction_textz.render, pos=(w // 2, h - loading_indicator_textz_offy), text=instruction_str, color=pre.WHITE)

    clock = pg.time.Clock()

    # def play_menu_theme():
    #     game.sfx.ambienceportalnear.play()

    chan_menu_sfx_theme: pg.mixer.ChannelType = game.sfx.ambienceportalnear.play(-1)

    running = True

    while running:  # while count < max_count:
        game.display.fill(bgcolor)

        title_textz_drawfn(game.display)
        instruction_textz_drawfn(game.display)

        # pixel art effect for drop-shadow depth
        display_mask: pg.Mask = pg.mask.from_surface(game.display)
        display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))

        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            game.display_2.blit(display_silhouette, offset)

        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                pg.quit()
                sys.exit()
            if event.type == pg.QUIT:
                pg.quit()
                sys.exit()
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_RETURN:
                    chan_menu_sfx_theme.fadeout(2000)
                    # chan_menu_sfx_theme.stop() # necessary to stop if fading out? or pause?
                    try:
                        game.run()
                        if game.gameover:
                            gameover_screen(game)
                            # TODO: how to resume ambience sfx channel for main menu?
                            #     chan_menu_sfx_theme.play()
                    except RuntimeError as e:
                        print(e)
                        print(f"error while running game from mainmenu_screen()", file=sys.stderr)
                        quit_exit()

        game.display_2.blit(game.display, (0, 0))
        game.screen.blit(pg.transform.scale(game.display_2, game.screen.get_size()), (0, 0))  # pixel art effect

        pg.display.flip()
        clock.tick(pre.FPS_CAP)

    assert not running
    if not running:
        chan_menu_sfx_theme.fadeout(1000)


if __name__ == "__main__":
    test__internal__move__commands__py()
    if pre.DEBUG_GAME_PROFILER:
        cProfile.run("Game().load_level(0)", sort="cumulative")
        cProfile.run("Game().run()", sort="cumulative")

    game = Game()
    loading_screen(game=game)
    mainmenu_screen(game=game)

# """
# NOTE: After fixing torch size problem. this is to be used vvvvvvv
#
# self.particles.extend(
#     Particle(
#         game=self,
#         p_kind=pre.ParticleKind.FLAME,  # pj_pos = (rect.x + random() * rect.width, rect.y + random() * rect.height)
#         pos=pg.Vector2(
#             x=(flametorch_rect.x + randint(-pre.SIZE.FLAMETORCH[0] // 1, pre.SIZE.FLAMETORCH[0] // 1) - min(pre.SIZE.FLAMETORCH[0] / 1, flametorch_rect.w / 1)),
#             y=(flametorch_rect.y + randint(-pre.SIZE.FLAMEPARTICLE[1], pre.SIZE.FLAMEPARTICLE[1] // 2) - flametorch_rect.h / 2),
#         ),
#         velocity=pg.Vector2(-0.1, 0.3),
#         frame=pre.COUNTRAND.FLAMEPARTICLE,
#     )
#     for flametorch_rect in self.flametorch_spawners.copy()
#     if (random() * odds_of_flame) < (flametorch_rect.w * flametorch_rect.h)  # since torch is slim
# )  # big number is to control spawn rate
# self.particles.extend(
#     Particle(
#         game=self,
#         p_kind=pre.ParticleKind.FLAMEGLOW,
#         pos=pg.Vector2(
#             x=(flametorch_rect.x + 0.01 * randint(-pre.SIZE.FLAMETORCH[0] // 1, pre.SIZE.FLAMETORCH[0] // 1) - min(pre.SIZE.FLAMETORCH[0] / 2, flametorch_rect.w / 2)),
#             y=(flametorch_rect.y + 0.03 * randint(-pre.SIZE.FLAMEPARTICLE[1] // 1, pre.SIZE.FLAMEPARTICLE[1] // 1) - flametorch_rect.h / 2),
#         ),
#         velocity=pg.Vector2(-0.1, 0.1),
#         frame=pre.COUNT.FLAMEGLOW,
#     )
#     for flametorch_rect in self.flametorch_spawners.copy()
#     if (random() * odds_of_flame * 60) < (flametorch_rect.w * flametorch_rect.h)
# )  # big number is to control spawn rate
#
# """
