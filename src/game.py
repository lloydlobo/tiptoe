# Primer: https://www.pygame.org/docs/tut/newbieguide.html

import itertools as it
import math
import queue
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from os import listdir, path
from pathlib import Path
from pprint import pprint  # pyright: ignore
from random import randint, random, uniform
from typing import Final, NoReturn, Optional

import pygame as pg

import internal.prelude as pre
from internal.assets import Assets
from internal.camera import SimpleCamera
from internal.entities import Action, Enemy, Player
from internal.hud import render_debug_hud
from internal.particle import Particle
from internal.spark import Spark
from internal.spawner import Portal
from internal.stars import Stars
from internal.tilemap import Tilemap


def quit_exit(context: str = "") -> NoReturn:
    if pre.DEBUG_GAME_CACHEINFO:  # lrucache etc...
        print(f"{pre.hsl_to_rgb.cache_info() = }")
    if context:
        print(f"{context}")
    pg.quit()
    sys.exit()


def get_user_config(filepath: Path) -> pre.UserConfig:
    config: Optional[dict[str, str]] = pre.UserConfig.read_user_config(filepath=filepath)
    if not config:
        print("error while reading configuration file at", repr(filepath))
        return pre.UserConfig.from_dict({})
    return pre.UserConfig.from_dict(config)


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


class AppState(Enum):
    GAMESTATE = auto()
    MENUSTATE = auto()


class GameState(Enum):
    PLAY = auto()
    PAUSE = auto()
    EXIT = auto()
    NEXTLEVEL = auto()


@dataclass
class GameCheckpointState:
    player_pos: tuple[float, float]
    enemy_positions: list[tuple[float, float]]


class Game:
    def __init__(self) -> None:
        pg.init()

        # note: hwsurface flag does nothing in pygameg ver2.0+, doublebuf has someuse, but not a magic speed up flag.
        # see https://www.pygame.org/docs/tut/newbieguide.html
        display_flags = pg.DOUBLEBUF | pg.NOFRAME | pg.HWSURFACE  # SCLAED | FULLSCREEN

        # self.dimensions = pg.display.Info().current_w, pg.display.Info().current_h
        self.mainscreen = None  # @property ??
        self.screen = pg.display.set_mode(pre.DIMENSIONS, pg.RESIZABLE, display_flags)
        self.dimensions = pg.Vector2(pre.DIMENSIONS)

        pg.display._set_autoresize(False)  # pyright: ignore |> see github:pygame/examples/resizing_new.py
        pg.display.set_caption(pre.CAPTION)

        self.display = pg.Surface(pre.DIMENSIONS_HALF, pg.SRCALPHA)
        self.display_2 = pg.Surface(pre.DIMENSIONS_HALF)

        self.bgcolor = pre.COLOR.BACKGROUND

        # note: font author suggest using font size in multiples of 9.
        self.fontface_path = pre.FONT_PATH / "8bit_wonder" / "8-BIT WONDER.TTF"
        self.font = pg.font.Font(self.fontface_path, 18)
        self.font_sm = pg.font.Font(self.fontface_path, 12)
        self.font_xs = pg.font.Font(self.fontface_path, 9)

        if pre.DEBUG_GAME_HUD:
            self.font_hud = pg.font.SysFont(name=("monospace"), size=7, bold=True)

        self.clock = pg.time.Clock()
        self.dt: float = 0.0  # delta time == 1 / framerate(fps) or pygame.clock.tick() / 1000
        if pre.DEBUG_GAME_HUD:
            self.clock_dt_recent_values: deque[pre.Number] = deque([self.dt, self.dt])

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        self.config_handler: pre.UserConfig = get_user_config(pre.CONFIG_PATH)
        _star_count = self.config_handler.star_count  # can panic if we get a float or string
        self._star_count: Final[int] = min(64, max(16, _star_count or pre.TILE_SIZE * 2))

        self.assets = Assets.initialize_assets()

        self.sfx = SFX(
            # fmt: off
            ambienceheartbeatloop=pg.mixer.Sound((pre.SFX_PATH / "ambienceheartbeatloop.wav").__str__()),
            # fmt: on
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

        self.sfx.ambienceheartbeatloop.set_volume(0.1)
        self.sfx.ambienceportalnear.set_volume(0.1)
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
        self.player = Player(self, self._player_starting_pos.copy(), pg.Vector2(pre.SIZE.PLAYER))

        self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.screenshake = 0
        self.gameover = False

        self._dead_lo: Final = 0
        self._dead_mid: Final = 10
        self._dead_hi: Final = 40

        self.scroll_ease: Final = pg.Vector2(1 / 30, 1 / 30)
        self.camerasize = self.display.get_size()
        self.camera = SimpleCamera(size=self.camerasize)

        # Transition:
        #   abs(self.transition) == 30 => opaque screen see nothing
        #   self.transition is 0 see eeverything; load level when completely black
        self._transition_lo: Final = -30
        self._transition_mid: Final = 0
        self._transition_hi: Final = 30

        self._max_screenshake: Final = pre.TILE_SIZE
        # load_level: declares and initializes level specific members
        self.level = 0
        self._level_map_count: Final[int] = len(listdir(pre.MAP_PATH))

        # TODO: offload it to loading screen as it is going to call it?
        # self.load_level(self.level)

        self.running = True

    def gts_record_checkpoint(self):
        player_position = (self.player.pos.x, self.player.pos.y)
        enemy_positions = [(e.pos.x, e.pos.y) for e in self.enemies]

        self.gcs_states.appendleft(GameCheckpointState(player_position, enemy_positions))
        if self.gcs_states.__len__() > 3:
            self.gcs_states.pop()

    def gts_rewind_checkpoint(self):
        if self.gcs_states:
            prev_gts = self.gcs_states.pop()
            self.player.pos = pg.Vector2(prev_gts.player_pos)

    def gts_rewind_recent_checkpoint(self):
        if self.gcs_states:
            prev_gts = self.gcs_states.popleft()
            self.player.pos = pg.Vector2(prev_gts.player_pos)

    def run(self) -> None:
        """This game loop runs continuously until the player opts out via inputs.

        Each iteration, computes user input non-blocking events, updates state
        of the game, and renders the game.
        future: Track delta time between each loop to control rate of gameplay.
        """
        level_music_filename = "intro_loop.wav"
        match self.level:
            case 0:
                level_music_filename = "theme_1.wav"
            case 1:
                level_music_filename = "theme_2.wav"
            case _:
                pass

        pg.mixer.music.load((pre.SRC_DATA_PATH / "music" / level_music_filename).__str__())
        pg.mixer.music.set_volume(0.2)
        pg.mixer.music.play(-1)

        if self.level == 0:
            self.sfx.playerspawn.play()

        surfw = pre.DIMENSIONS_HALF[0]
        bg2_speed, bg3_speed = 0.1, 0.4
        bg2_depth, bg3_depth = 0.1, 0.8
        bg2_x = bg3_x = 0
        bg2_y = bg3_y = 0

        gcs_timer = 0

        # NOTE: Access unlimited checkpoint rewinds if you initialize this in
        # Game.run(), else default to initializing this to Game.lvl_load_level(...)
        self.gcs_states: deque[GameCheckpointState] = deque([])

        while self.running:
            self.dt = self.clock.tick(pre.FPS_CAP) * 0.001
            self.display.fill((0, 0, 0, 0))
            self.display_2.blit(self.bg1, (0, 0))
            if (_tmpflag_parallax_enableed := 1) and _tmpflag_parallax_enableed:
                bg2_x -= bg2_speed
                if bg2_x < -surfw:
                    bg2_x = 0
                # bg3_x -= bg3_speed
                # if bg3_x < -surfw: bg3_x = 0
                # moveby_x = pre.Motion.lerp(24, 8, abs(1 - ((0.1328, 0.09)[randint(0, 1)] * 0.35 * math.sin((self.player.dash_time)))))  # always 0. use dash
                # moveby_x = 0  # always 0. use dash
                # moveafter_x = self.dimensions.x / 2  # or use 4
                moveafter_x = self.level_map_size[0]  # this fixes, full range movement of bg3 mountains from start to end
                moveafter_y = pre.Motion.lerp(32, 16, abs(self.player.pos.y - self.dimensions.y))
                bg2_y = max(0, (moveafter_y - self.camera.render_scroll[1]) * bg2_depth)
                bg3_x = max(0, (moveafter_x - self.camera.render_scroll[0]) * bg3_speed * bg3_depth)
                bg3_y = max(0, moveafter_y - self.camera.render_scroll[1] // 2 * bg3_depth)
            if 0:  # easy on performance
                self.display_2.blit(self.bg2, (bg2_x, 0))
                self.display_2.blit(self.bg2, ((bg2_x + surfw), 0))  # wrap around
            else:
                self.display_2.blit(self.bg2, (bg2_x, bg2_y))
                self.display_2.blit(self.bg2, ((bg2_x + surfw), bg2_y))  # wrap around
            if 0:  # easy on performance
                self.display_2.blit(self.bg3, (0, bg3_y))
                self.display_2.blit(self.bg3, (0 + surfw, bg3_y))  # wrap around
            else:
                self.display_2.blit(self.bg3, (bg3_x, bg3_y))
                self.display_2.blit(self.bg3, ((bg3_x - surfw), bg3_y))  # wrap around
            if (_tmpflag_rewind_glitch_enabled := 0) and _tmpflag_rewind_glitch_enabled:
                # QUEST: introduce absurd rewinding checkpoints when in 'Delirium' in later levels ???
                if gcs_timer > 0 and (2 * (gcs_timer + 1)) % pre.FPS_CAP == 0:
                    self.gts_rewind_checkpoint()
                    self.gts_record_checkpoint()
                    gcs_timer = -10 * pre.FPS_CAP  # rewind timer for 10 secs 'wait-time'
                gcs_timer += 1

            self.events()
            self.update()
            self.render()

    def events(self) -> None:
        for event in pg.event.get():
            # note: exit game loop while self.running and continue on from the caller
            if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.running = False
                try:
                    assert not self.gameover, "failed to overide gameover flag after reset"
                except AssertionError as e:
                    self.gameover = False
                    print(f"ignoring AssertionError: {e}\ncontext: TEMPFIX: overiding gameover to False")
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
                if event.key in (pg.K_SPACE, pg.K_c):
                    if self.player.jump():
                        self.sfx.jump.play()
                if event.key in (pg.K_x, pg.K_v):
                    self.player.dash()
                if event.key == pg.K_s:  # set checkpoint
                    self.gts_record_checkpoint()
                if event.key == pg.K_z:
                    self.gts_rewind_recent_checkpoint()
                if event.key == pg.K_d:
                    self.gts_rewind_checkpoint()
            if event.type == pg.KEYUP:
                if event.key == pg.K_LEFT:
                    self.movement.left = False
                if event.key == pg.K_RIGHT:
                    self.movement.right = False

    def render(self) -> None:
        """Render display."""
        self.display_2.blit(self.display, (0, 0))
        _offset = (
            (0, 0)
            if not self.config_handler.screenshake
            else (
                (self.screenshake * random()) - (self.screenshake * 0.5),
                (self.screenshake * random()) - (self.screenshake * 0.5),
            )
        )
        self.screen.blit(pg.transform.scale(self.display_2, self.screen.get_size()), _offset)
        pg.display.flip()

    def draw_text(self, x: int, y: int, font: pg.font.Font, color: pg.Color | pre.ColorValue | pre.ColorKind, text: str):
        surf = font.render(text, True, color)
        rect = surf.get_rect()
        rect.midtop = (x, y)
        self.display.blit(surf, rect)

    def set_mainscreen(self, scr: Optional["StartScreen | LoadingScreen | Game"]):
        if self.mainscreen != None:
            # delete existing screen (QUEST?: are we deleting game copy?)
            del self.mainscreen
            self.mainscreen = None

        self.mainscreen = scr

        # show new screen
        if self.mainscreen != None:
            self.mainscreen.run()

        if self.gameover:
            return AppState.MENUSTATE, GameState.EXIT
        elif not self.running:
            # note: we could just set gamestate form keyevent or update loop
            return AppState.GAMESTATE, GameState.NEXTLEVEL

    def reset_game(self) -> None:
        self.clock = pg.time.Clock()
        self.dt = 0

        self.movement = pre.Movement(left=False, right=False, top=False, bottom=False)

        self.stars = Stars(self.assets.misc_surfs["stars"], self._star_count)
        self.player = Player(self, self._player_starting_pos.copy(), pg.Vector2(pre.SIZE.PLAYER))

        self.tilemap = Tilemap(self, pre.TILE_SIZE)

        self.screenshake = 0
        self.camera.reset()
        try:
            assert not self.gameover, "failed to overide gameover flag while gameover_screen() loop exits. context: gameover->mainmenu->playing->pressed Escape(leads to gameover but want mainmenu[pause like])"
        except AssertionError as e:
            self.gameover = False  # -> this fixes: in Game.run() we reset_game() and then set self.gameover = True and then while running's running = False... so this is pointless. either do it here or there
            print(f"error while running game from reset_game():\n\t{e}", file=sys.stderr)

        self.level = 0
        self.lvl_load_level(self.level)

    def _lvl_load_level_map(self, map_id: int):
        self.tilemap.load(path=path.join(pre.MAP_PATH, f"{map_id}.json"))

    def lvl_have_more_levels(self) -> bool:
        return self.level + 1 >= self._level_map_count

    def lvl_increment_level(self):
        prev = self.level
        self.level = min(self.level + 1, self._level_map_count - 1)
        return dict(prev=prev, next=self.level)

    def lvl_load_level(self, map_id: int, progressbar: Optional[queue.Queue[int]] = None) -> None:
        progress = 0
        if progressbar is not None:
            progressbar.put(progress)
        self.level_map_size = (pre.DIMENSIONS_HALF[0] * 3, pre.DIMENSIONS_HALF[1])
        """self.level_map_size::

        This is used to update camera based on each level's tilemap's dimension limit... hardcoded for now"""

        self._lvl_load_level_map(map_id)

        if 0:
            try:
                assert not self.gameover, f"want gameover flag to be false. got {self.gameover=}"
            except AssertionError as e:
                print(f"error while running game from load_level():\n\t{e}", file=sys.stderr)
                quit_exit()
            self.gameover = False

        progress += 5
        if progressbar is not None:
            progressbar.put(progress)

        self.projectiles: list[pre.Projectile] = []
        self.sparks: list[Spark] = []

        self.bg1 = self.assets.misc_surf["bg1"]
        self.bg2 = self.assets.misc_surf["bg2"]
        self.bg3 = self.assets.misc_surf["bg3"]

        # SPAWNERS
        self.ftorch_spawners = [
            pg.Rect(
                max(4, pre.SIZE.FLAMETORCH[0] // 2) + torch.pos.x,
                max(4, pre.SIZE.FLAMETORCH[1] // 2) + torch.pos.y,
                pre.SIZE.FLAMETORCH[0],
                pre.SIZE.FLAMETORCH[1],
            )
            for torch in self.tilemap.extract([("decor", 2)], keep=True)
        ]
        self.spike_spawners = list(self.tilemap.spawn_spikes(self.tilemap.extract([("spike", 0), ("spike", 1), ("spike", 2), ("spike", 3)], keep=True)))

        progress += 10
        if progressbar is not None:
            progressbar.put(progress)

        self.portal_spawners: list[Portal] = []
        self.enemies: list[Enemy] = []

        _spwn_kinds: Final = (pre.SpawnerKind.PLAYER.value, pre.SpawnerKind.ENEMY.value, pre.SpawnerKind.PORTAL.value)

        increment = math.floor((80 - progress) / len(_spwn_kinds))  # FIXME: can be wrong
        for spawner in self.tilemap.extract(list(zip(it.repeat(str(pre.TileKind.SPAWNERS.value), len(_spwn_kinds)), _spwn_kinds)), False):
            match pre.SpawnerKind(spawner.variant):
                case pre.SpawnerKind.PLAYER:  # coerce to a mutable list if pos is a tuple
                    self.player.pos = spawner.pos.copy()
                    self.player.air_time = 0  # Reset time to avoid multiple spawns during fall
                case pre.SpawnerKind.ENEMY:
                    self.enemies.append(Enemy(self, spawner.pos, pg.Vector2(pre.SIZE.ENEMY)))
                case pre.SpawnerKind.PORTAL:
                    self.portal_spawners.append(Portal(self, pre.EntityKind.PORTAL, spawner.pos, pg.Vector2(pre.TILE_SIZE)))
            progress += increment
            if progressbar is not None:
                progressbar.put(progress)
        # progress 78% for lvl1 on Fri May  3 10:57:31 AM IST 2024

        if pre.DEBUG_GAME_ASSERTS:
            assert self.player is not None, f"want a spawned player. got {self.player}"
            assert (val := len(self.enemies)) > 0, f"want atleast 1 spawned enemy. got {val}"
            assert (val := len(self.portal_spawners)) > 0, f"want atleast 1 spawned portal. got {val}"

        self.particles: list[Particle] = []

        self.scroll = pg.Vector2(0.0, 0.0)

        self.dead = 0  # tracks if the player died -> 'reloads level' - which than resets this counter to zero
        self.dead_hit_skipped_counter = 0  # if player is invincible while idle and hit, count amout of shield that is being hit on...
        self.touched_portal = False
        self.transition = self._transition_lo
        if self.level != 0:
            self.sfx.playerspawn.play()

        progress = 100
        if progressbar is not None:
            progressbar.put(progress)

        if 1:  # HACK: emulate loading heavy resources
            time.sleep(0.150)

    def update(self) -> None:

        # Camera: update and parallax
        if 0:
            self.scroll.x += (self.player.rect.centerx - (self.display.get_width() * 0.5) - self.scroll.x) * self.scroll_ease.x
            self.scroll.y += (self.player.rect.centery - (self.display.get_height() * 0.5) - self.scroll.y) * self.scroll_ease.y
            render_scroll: tuple[int, int] = (int(self.scroll.x), int(self.scroll.y))
        else:
            _target = self.player.rect
            # print(_target.bottom, _target.bottom // 2)
            self.camera.update((_target.centerx, _target.bottom // 2), map_size=self.level_map_size, dt=self.dt)
            render_scroll = self.camera.render_scroll

            if pre.DEBUG_GAME_HUD:
                self.camera.debug(self.display_2, (int(_target.x), int(_target.y)))

        # Mouse: cursor position with offset
        raw_mouse_pos = pg.Vector2(pg.mouse.get_pos()) / pre.RENDER_SCALE
        mouse_pos: pg.Vector2 = raw_mouse_pos + render_scroll

        if 0:
            # Render mouse blog
            mouse_surf = self.assets.misc_surf.get("mouse")
            if mouse_surf:
                dest = raw_mouse_pos - pg.Vector2(mouse_surf.get_size()) // 2
                mask: pg.Mask = pg.mask.from_surface(mouse_surf)
                silhouette = mask.to_surface(setcolor=(20, 20, 21, math.floor(255 / 2)), unsetcolor=(0, 0, 0, 0))
                for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    self.display.blit(silhouette, (dest - (pg.Vector2(offset) * pre.TILE_SIZE)))

        self.screenshake = max(0, self.screenshake - 1)

        # Check for game level transitions
        if self.touched_portal or not self.enemies:  # win_condition:
            self.transition += 1

            # Check if transition to the next level is required
            if self.transition > self._transition_hi:
                try:
                    if self.lvl_have_more_levels():  # self.level + 1 >= self._level_map_count:
                        self.reset_game()
                        if pre.DEBUG_GAME_ASSERTS:
                            try:
                                assert not self.gameover, "expected gameover to be false after resetting game."
                            except AssertionError as e:
                                err_msg = f"error while running game from Game.run():\n\t{e}"
                                print(f"allowing AssertionError instead of quit_exit():\n\t{err_msg}", file=sys.stderr)
                        self.gameover = True  # note: run() is called by mainmenu_screen,
                        self.running = False  # the process will continue on from the loop inside game menu.
                    else:
                        curlvl = self.level
                        result = self.lvl_increment_level()
                        prevlvl = result.get("prev")
                        nextlvl = result.get("next")
                        if pre.DEBUG_GAME_ASSERTS:
                            # Validate the next and previous levels
                            try:
                                assert isinstance(prevlvl, int) and prevlvl >= 0, f"Invalid previous level: {prevlvl}"
                                assert isinstance(nextlvl, int) and nextlvl >= 0, f"Invalid next level: {nextlvl}"
                                assert prevlvl != curlvl, f"Previous level should not be the current level"
                                assert nextlvl != curlvl, f"Next level should not be the current level"
                            except AssertionError as e:
                                print(f"error during game loop level assertions in Game.run(): {e}", file=sys.stderr)
                        if (_tmpflag_mainscreen_strategy_disabled := 0) and _tmpflag_mainscreen_strategy_disabled:  # NOTE: debugging StartScreen and LoadingScreen
                            self.lvl_load_level(self.level)
                        else:
                            # Exit loop back to the caller loadingscreen propably
                            self.running = False
                except Exception as e:
                    print(f"error during game loop transitions level assertions in Game.run(): {e}", file=sys.stderr)
                    quit_exit()

        if self.transition < self._transition_mid:
            self.transition += 1

        if self.dead:
            self.dead += 1
            if self.dead >= self._dead_mid:  # ease into incrementing for level change till _hi
                self.transition = min(self._transition_hi, self.transition + 1)
            if self.dead >= self._dead_hi:
                self.lvl_load_level(self.level)

        # Flametorch: particle animation
        odds_of_flame: float = (6 * 0.001) * 49_999  # note: big number 49_999 controls spawn rate
        # fmt: off
        self.particles.extend(
            Particle( game=self, p_kind=pre.ParticleKind.FLAME, pos=pg.Vector2((rect.x - random() * rect.w), (rect.y - random() * rect.h - 4)), velocity=pg.Vector2(uniform(-0.03, 0.03), uniform(0.0, -0.03)), frame=randint(0, 20),)
            for rect in self.ftorch_spawners.copy() if (random() * odds_of_flame) < (rect.w * rect.h)
        )
        self.particles.extend(
            Particle( game=self, p_kind=pre.ParticleKind.FLAMEGLOW, pos=pg.Vector2((rect.x - random() * rect.w), (rect.y - random() * rect.h - 4)), velocity=pg.Vector2(uniform(-0.2, 0.2), uniform(0.1, 0.3)), frame=randint(0, 20),)
            for rect in self.ftorch_spawners.copy() if (random() * odds_of_flame * 8) < (rect.w * rect.h)
        )
        # fmt: on

        # Stars: backdrop update and render
        self.stars.update()  # stars drawn behind everything else
        self.stars.render(self.display_2, render_scroll)  # display_2 blitting avoids masks depth

        # Tilemap: render
        self.tilemap.render(self.display, render_scroll)

        # Portal: detect and render
        if not self.touched_portal:  # <- note: this disappears very fast
            for i, portal in enumerate(self.portal_spawners):
                if self.player.rect.colliderect(portal.rect()):
                    self.touched_portal = True

                    if self.level != self._level_map_count:
                        self.sfx.portaltouch.play()

                self.display.blit(portal.assets[i], portal.pos - render_scroll)

        # Enemy: update and render
        for enemy in self.enemies.copy():
            kill_animation = enemy.update(self.tilemap, pg.Vector2(0, 0))
            enemy.render(self.display, render_scroll)
            if 0:  # no border for sleeping invisibility
                match enemy.action:
                    case Action.SLEEPING:  # avoid border shadow
                        enemy.render(self.display_2, render_scroll)
                    case _:
                        enemy.render(self.display, render_scroll)
                        pass
            if kill_animation:
                self.enemies.remove(enemy)

        for spike_rect in self.spike_spawners:
            if self.player.rect.colliderect(spike_rect):
                self.dead += 1

        _radius_ = 2
        for i, state in enumerate(self.gcs_states):
            _r = _radius_ * (1 + 1 / (1 + i))
            # _r *=  _radius_ * abs(math.sin(1.618 / (i + 1))) * 0.328
            # _r *= _radius_ * 0.1618

            pg.draw.circle(
                self.display,
                pre.GREENGLOW,
                # pre.BLUEGLOW,
                center=(int(state.player_pos[0] - render_scroll[0]), int(state.player_pos[1] - render_scroll[1])),
                radius=(_r + 1),
            )
            pg.draw.circle(
                self.display,
                pre.GREENBLURB,
                center=(int(state.player_pos[0] - render_scroll[0]), int(state.player_pos[1] - render_scroll[1])),
                radius=_r,
            )

            if pre.DEBUG_GAME_STRESSTEST:
                self.draw_text(int(state.player_pos[0] - render_scroll[0]), int(state.player_pos[1] - render_scroll[1]), self.font_xs, pre.COLOR.FLAMEGLOW, f"{i+1}")

        # Player: update and render
        if not self.dead:
            self.player.update(self.tilemap, pg.Vector2(self.movement.right - self.movement.left, 0))
            self.player.render(self.display, render_scroll)

        # Gun: projectiles and sparks
        for projectile in self.projectiles:
            projectile.pos[0] += projectile.velocity
            projectile.timer += 1

            img = self.assets.misc_surf["projectile"]
            dest = (projectile.pos[0] - (img.get_width() * 0.5) - render_scroll[0], projectile.pos[1] - (img.get_height() * 0.5) - render_scroll[1])
            self.display.blit(img, dest)

            # Projectile post render: update
            projectile_x, projectile_y = int(projectile.pos[0]), int(projectile.pos[1])  # int -> precision for grid system

            if self.tilemap.maybe_solid_gridtile_bool(pg.Vector2(projectile_x, projectile_y)):
                self.projectiles.remove(projectile)
                # Wall sparks bounce opposite to projectile's direction
                spark_speed, spark_direction = 0.5, math.pi if (projectile.velocity > 0) else 0  # note: unit circle direction (0 left, right math.pi)
                self.sparks.extend(Spark(projectile.pos, angle=(random() - spark_speed + spark_direction), speed=(2 + random())) for _ in range(4))
                self.sfx.hitwall.play()
            elif projectile.timer > 360:
                self.projectiles.remove(projectile)
            elif abs(self.player.dash_timer) < self.player.dash_time_burst_2:  # vulnerable player
                if self.player.rect.collidepoint(projectile_x, projectile_y):
                    # Player looses health but still alive
                    if (self.player.action == Action.IDLE) and (self.dead_hit_skipped_counter < self.player.max_dead_hit_skipped_counter):
                        self.projectiles.remove(projectile)
                        self.dead_hit_skipped_counter += 1  # Todo: should reset this if players action state changes from idle to something else
                        self.screenshake = max(self._max_screenshake, self.screenshake - 0.5)
                        self.sparks.extend(Spark(pos=pg.Vector2(self.player.rect.center), angle=(random() * math.pi * 2), speed=(2 + random()), color=pre.COLOR.PLAYER) for _ in range(30))
                        self.sfx.hitmisc.play()  # invincible player when idle for 3 lifes
                    else:  # Player dies
                        self.projectiles.remove(projectile)
                        self.dead += 1
                        self.dead_hit_skipped_counter = 0  # Todo: should reset this if players action state changes from idle to something else
                        self.screenshake = max(self._max_screenshake, self.screenshake - 1)
                        # fmt: off
                        self.sparks.extend(Spark(pos=pg.Vector2(self.player.rect.center), angle=random() * math.pi * 2, speed=((2 * uniform(0.618, 1.618)) + random())) for _ in range(30))
                        self.particles.extend(Particle(self, pre.ParticleKind.PARTICLE, pg.Vector2(self.player.rect.center), (pg.Vector2((math.cos((random() * math.pi * 2) + math.pi) * (random() * 5) * 0.5, math.cos((random() * math.pi * 2) + math.pi) * (random() * 5) * 0.5))), frame=randint(0, 7)) for _ in range(30))
                        self.sfx.hit.play()
                        # fmt: on

        for spark in self.sparks.copy():
            kill_animation = spark.update()
            spark.render(self.display, offset=render_scroll)
            if kill_animation:
                self.sparks.remove(spark)

        # Display Mask: before particles
        display_mask: pg.Mask = pg.mask.from_surface(self.display)
        display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.display_2.blit(display_silhouette, offset)

        # Particles
        for particle in self.particles.copy():
            match particle.kind:
                case pre.ParticleKind.FLAME:
                    kill_animation = particle.update()
                    particle.render(self.display, render_scroll)
                    amplitude = uniform(-1.0, 1.0) * 0.3 * 0.5
                    if amplitude == 0:
                        amplitude = 1
                    size = pre.SIZE.FLAMEPARTICLE  # JUICE: if player gets near, let the flames change!!!!
                    particle_rect = pg.Rect(particle.pos.x, particle.pos.y, size[0], size[1])
                    if self.player.rect.colliderect(particle_rect):
                        if self.player.pos.x < particle.pos.x and not self.player.flip:
                            particle.velocity.x += -abs(amplitude) * 0.2
                        if self.player.pos.x > particle.pos.x and self.player.flip:
                            particle.velocity.x += abs(amplitude) * 0.2
                    particle.pos.x += math.sin(particle.animation.frame * 0.035) * amplitude
                    if kill_animation:
                        self.particles.remove(particle)
                case pre.ParticleKind.FLAMEGLOW:
                    kill_animation = particle.update()
                    img = particle.animation.img().copy()
                    amplitude = uniform(-1.0, 1.0) * 0.3 * 0.5
                    if amplitude == 0:
                        amplitude = 1
                    dest = (particle.pos.x - render_scroll[0] - img.get_width() // 2, particle.pos.y - render_scroll[1] - img.get_height() // 2)  # ideal is display, but display_2 looks cool for flameglow
                    self.display_2.blit(img, dest, special_flags=pg.BLEND_RGB_ADD)  # ^ use center of the image as origin
                    particle.pos.x += math.sin(particle.animation.frame * 0.035) * (amplitude, 0.3)[randint(0, 1)]
                    if kill_animation:
                        self.particles.remove(particle)
                case _:
                    pass

        if pre.DEBUG_GAME_HUD:
            try:
                mousepos = [math.floor(mouse_pos.x), math.floor(mouse_pos.y)]
                render_debug_hud(self, self.display_2, render_scroll, (mousepos[0], mousepos[1]))
                self.clock_dt_recent_values.appendleft(self.dt)
                if len(self.clock_dt_recent_values) is pre.FPS_CAP:
                    self.clock_dt_recent_values.pop()
            except Exception as e:
                print(f"exception during rendering debugging HUD: {e}")


# def loading_screen(game: Game):
#     clock = pg.time.Clock()
#
#     loading_screen_duration_sec: Final[float] = 1.0
#
#     fade_in_frame_count: Final = 7  # same as for bullet projectiles
#     max_count: Final[int] = math.floor(pre.FPS_CAP * loading_screen_duration_sec)
#
#     bgcolor = pre.CHARCOAL
#     w, h = pre.DIMENSIONS_HALF
#     base_font_size = 16
#     base_font_size *= 3
#
#     cycle_loading_indicator_dots: it.cycle[str] = it.cycle(["   ", "*  ", "** ", "***"])
#     title_textz = Textz(game.font, bold=True)
#     loading_indicator_textz = Textz(game.font_sm)
#
#     title_textz_offy = 4 * pre.TILE_SIZE
#
#     loading_indicator_textz_offy = math.floor(min(0.618 * (pre.SCREEN_HEIGHT // 2 - title_textz_offy), 8 * pre.TILE_SIZE)) - math.floor(pre.TILE_SIZE * 1.618)
#
#     title_str = pre.CAPTION
#     title_textz_drawfn = partial(
#         title_textz.render,
#         pos=(w // 2, h // 2 - title_textz_offy),
#         text=title_str,
#         color=pre.WHITE,
#     )
#
#     loading_indicator_textz_drawfn = partial(
#         loading_indicator_textz.render,
#         pos=(w // 2, h - loading_indicator_textz_offy),
#         color=pre.WHITE,
#     )
#     loading_indicator_text_str = next(cycle_loading_indicator_dots)
#
#     loading_timer = 0
#     count = 0
#
#     if pre.DEBUG_GAME_ASSERTS:
#         t_start = time.perf_counter()
#
#     while count < max_count:
#         game.display.fill(bgcolor)
#
#         if count >= fade_in_frame_count:  # fade in
#             if loading_timer >= math.floor(60 * 0.7):
#                 loading_indicator_text_str = next(cycle_loading_indicator_dots)
#                 loading_timer = 0
#             if count + 75 > max_count:
#                 loading_indicator_text_str = "  oadingl  "
#             if count + 70 > max_count:
#                 loading_indicator_text_str = " adinglo  "
#             if count + 65 > max_count:
#                 loading_indicator_text_str = " dingloa  "
#             if count + 54 > max_count:
#                 loading_indicator_text_str = " ingload  "
#             if count + 44 > max_count:
#                 loading_indicator_text_str = " ngloadi  "
#             if count + 40 > max_count:
#                 loading_indicator_text_str = " gloadin  "
#             if count + 34 > max_count:
#                 loading_indicator_text_str = " loading  "
#             if count + 27 >= max_count:
#                 loading_indicator_text_str = "  summons  "
#
#             title_textz_drawfn(game.display)
#             loading_indicator_textz_drawfn(game.display, text=loading_indicator_text_str)
#
#         # pixel art effect for drop-shadow depth
#         display_mask: pg.Mask = pg.mask.from_surface(game.display)
#         display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
#         for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
#             game.display_2.blit(display_silhouette, offset)
#
#         for event in pg.event.get():
#             if event.type == pg.KEYDOWN and event.key == pg.K_q:
#                 quit_exit()
#             if event.type == pg.QUIT:
#                 quit_exit()
#
#         game.display_2.blit(game.display, (0, 0))
#         game.screen.blit(pg.transform.scale(game.display_2, game.screen.get_size()), (0, 0))  # pixel art effect
#
#         pg.display.flip()
#         clock.tick(pre.FPS_CAP)
#
#         loading_timer += 1
#         count += 1
#
#     if pre.DEBUG_GAME_ASSERTS:
#         t_end = time.perf_counter()
#         t_elapsed = t_end - t_start  # pyright: ignore
#         ok = count is max_count
#         did_not_drop_frames = t_elapsed <= loading_screen_duration_sec
#         try:
#             assert ok, f"loading_screen: error in {repr('while')} loop execution logic. want {max_count}. got {count}"
#             assert did_not_drop_frames, f"error: {t_elapsed=} should be less than {loading_screen_duration_sec=} (unless game dropped frames)"
#         except AssertionError as e:
#             print(f"loading_screen: AssertionError while loading screen:\n\t{e}", file=sys.stderr)
#             quit_exit()
#
#
# def gameover_screen(game: Game):
#     try:
#         assert game.gameover, f"want gameover flag to be true. got {game.gameover=}"
#     except AssertionError as e:
#         print(f"error while running game from gameover_screen():\n\t{e}", file=sys.stderr)
#         quit_exit()
#
#     loading_screen_duration_sec: Final[float] = 2.0
#     fade_in_frame_count: Final = 7  # same as for bullet projectiles
#     max_count: Final[int] = math.floor(pre.FPS_CAP * loading_screen_duration_sec)
#
#     w, h = pre.DIMENSIONS_HALF
#     bgcolor = pre.CHARCOAL
#     base_font_size = 16
#     base_font_size *= 3
#
#     title_textz = Textz(game.font, bold=True)
#     instruction_textz = Textz(game.font_sm, bold=False)
#
#     title_textz_offy = 4 * pre.TILE_SIZE
#     loading_indicator_textz_offy = math.floor(min(0.618 * (pre.SCREEN_HEIGHT // 2 - title_textz_offy), 8 * pre.TILE_SIZE)) - math.floor(pre.TILE_SIZE * 1.618)
#
#     title_str = "Game Over"
#     instruction_str = f"esc*ape to main menu or q*uit to exit"
#
#     title_textz_drawfn = partial(
#         title_textz.render,
#         pos=(w // 2, h // 2 - title_textz_offy),
#         text=title_str,
#         color=pre.WHITE,
#     )
#     instruction_textz_drawfn = partial(
#         instruction_textz.render,
#         pos=(w // 2, h - loading_indicator_textz_offy),
#         text=instruction_str,
#         color=pre.WHITE,
#     )
#
#     loading_timer = 0
#     count = 0
#
#     if pre.DEBUG_GAME_STRESSTEST:
#         t_start = time.perf_counter()
#
#     clock = pg.time.Clock()
#     running = True
#
#     while running:  # while count < max_count:
#         game.display.fill(bgcolor)
#
#         if count >= fade_in_frame_count:  # fade in
#             title_textz_drawfn(game.display)
#             instruction_textz_drawfn(game.display)
#
#         display_mask: pg.Mask = pg.mask.from_surface(game.display)  # pixel art effect for drop-shadow depth
#         display_silhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
#         for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
#             game.display_2.blit(display_silhouette, offset)
#
#         for event in pg.event.get():
#             if event.type == pg.KEYDOWN and event.key == pg.K_q:
#                 quit_exit()
#             if event.type == pg.QUIT:
#                 quit_exit()
#             if event.type == pg.KEYDOWN:
#                 if event.key == pg.K_ESCAPE:
#                     try:
#                         # fixes: this is now setting ganeover state to false as
#                         # we exit gameover menu.
#                         # solves assertion error in Game.run() loop on Esc event
#                         game.gameover = False
#                         # since this func is called by mainmenu_screen, it will
#                         # continue on from the loop inside game menu
#                         running = False
#                     except Exception as e:  # fixme: using exception (anti-pattern)
#                         print(f"something went wrong while running mainmenu_screen from gameover_screen():\n\t{e}")
#                         quit_exit()
#
#         game.display_2.blit(game.display, (0, 0))
#         game.screen.blit(pg.transform.scale(game.display_2, game.screen.get_size()), (0, 0))  # pixel art effect
#
#         pg.display.flip()
#         clock.tick(pre.FPS_CAP)
#
#         loading_timer += 1
#         count += 1
#
#     if pre.DEBUG_GAME_STRESSTEST:
#         t_end = time.perf_counter()
#         t_elapsed = t_end - t_start  # type: ignore
#         ok = count is max_count
#         did_not_drop_frames = t_elapsed <= loading_screen_duration_sec
#         try:
#             # fmt: off
#             assert (ok), f"error in {repr('while')} loop execution logic. want {max_count}. got {count}"
#             assert (did_not_drop_frames), f"error: {t_elapsed=} should be less than {loading_screen_duration_sec=} (unless game dropped frames)"
#         except AssertionError as e:
#             print(f"error while running game from gameover_screen():\n\t{e}", file=sys.stderr)
#             quit_exit()
#         # fmt: on
#
#     try:
#         assert not running, "gameover loop not running"
#     except AssertionError as e:
#         print(f"error while running game from gameover_screen():\n\t{e}", file=sys.stderr)
#         quit_exit()


class LoadingScreen:
    def __init__(self, game: Game, level: int) -> None:
        self.game = game
        # self.clock = pg.time.Clock()  # or use game's clock?

        self.level = level

        self.queue: queue.Queue[int] = queue.Queue()
        self.w, self.h = pre.DIMENSIONS_HALF

        self.queue.put(0)
        self.progress: int = self.queue.get()  # 0% initially
        if pre.DEBUG_GAME_ASSERTS:  # self.queue.join()
            assert self.queue.qsize() == 0 or self.queue.empty()

        # fonts
        self.fontsize = 18  # 9*2
        self.font = pg.font.Font(pg.font.match_font("monospace"), self.fontsize)

    def run(self) -> None:
        running = True
        while running:
            loaderthread: Optional[threading.Thread] = None

            match self.level:  # self.level.level
                case 0 | 1 | 2:
                    loaderthread = threading.Thread(target=self.game.lvl_load_level, args=(self.level, self.queue))
                    loaderthread.start()
                case _:
                    # todo: load the next level/levels
                    pass

            while True:
                self.events()
                self.update()
                self.render()
                if loaderthread is not None and not loaderthread.is_alive():
                    result = self.game.set_mainscreen(self.game)
                    if not self.game.running:
                        break

            if not self.game.running:
                self.game.running = True
                self.level = self.game.level
                if self.game.gameover:
                    running = False
                    if 1:  # NOTE: placeholdere to impl a GameoverScreen
                        self.game.gameover = False
                    # self.game.running = True # HACK: to reset game state. NOTE: probably don't use a cls.running styled state variable. and just check for level changes and/or gameover

    def events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()
            if event.type == pg.QUIT:
                self.running = False
                quit_exit()

    def update(self):
        if not self.queue.empty() or not self.queue.qsize() == 0:
            self.progress = self.queue.get()

    def render(self):
        # clear screen and render background
        self.game.display.fill(self.game.bgcolor)

        pbar_h = 30 // 2
        pbar_w = (self.w - self.w / 4) // 2

        x = self.w / 2 - pbar_w / 2
        y = self.h / 2

        pcounter = self.progress / 100
        if pcounter >= 1:
            pcounter = 1

        pbar_fill = pcounter * pbar_w
        pbar_outline_rect = pg.Rect(x - 10, y - 10, pbar_w + 20, pbar_h + 20)
        pbar_fill_rect = pg.Rect(x, y, pbar_fill, pbar_h)

        # draw bar
        pg.draw.rect(self.game.display, pre.WHITE, pbar_fill_rect)
        pg.draw.rect(self.game.display, pre.WHITE, pbar_outline_rect, 2)

        # draw text
        self.game.draw_text(self.w // 2 - self.fontsize // 2, self.h // 2 - self.fontsize // 2 - pbar_h - 50, self.font, pre.WHITE, "Loading...")

        dispmask: pg.Mask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)

        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))

        # *flip* the display
        pg.display.flip()


class StartScreen:
    """Main Menu Screen."""

    def __init__(self, game: Game) -> None:
        self.game = game

        # self.clock = pg.time.Clock()  # or use game's clock?

        self.w, self.h = pre.DIMENSIONS_HALF
        self.bgcolor = pre.CHARCOAL

        self.title_font = self.game.font
        self.start_font = self.game.font_sm

        # fonts
        # self.title_textz = Textz(self.game.font, bold=True)
        # self.instruction_textz = Textz(self.game.font_sm, bold=False)

        # fmt: off
        self.title_str = "Menu"
        self.instruction_str = f"return* to enter game or q*uit to exit"

        self._title_textz_offy = 4 * pre.TILE_SIZE
        # self.title_textz_drawfn = partial( self.title_textz.render, pos=(self.w // 2, self.h // 2 - self._title_textz_offy), text=self.title_str, color=pre.WHITE,)

        # self._loading_indicator_textz_offy = math.floor( min(0.618 * (pre.SCREEN_HEIGHT // 2 - self._title_textz_offy), 8 * pre.TILE_SIZE)) - math.floor(pre.TILE_SIZE * 1.618)
        # self.instruction_textz_drawfn = partial( self.instruction_textz.render, pos=(self.w // 2, self.h - self._loading_indicator_textz_offy), text=self.instruction_str, color=pre.WHITE,)
        # fmt: on

        self.running = True

    def run(self) -> None:
        # play background music
        pg.mixer.music.load(pre.SRC_DATA_PATH / "music" / "intro_loop.wav")
        pg.mixer.music.set_volume(0.3)
        pg.mixer.music.play(loops=-1)

        while self.running:
            # self.clock.tick(pre.FPS_CAP)
            self.events()
            self.update()
            self.render()

        # try:
        #     assert not self.running, "main menu not running"
        # except AssertionError as e:
        #     print(f"error while running game from mainmenu_screen():\n\t{e}", file=sys.stderr)
        #     quit_exit()

    def events(self):
        for event in pg.event.get():
            if event.type == pg.KEYDOWN and event.key == pg.K_q:
                self.running = False
                quit_exit()
            if event.type == pg.QUIT:
                self.running = False
                quit_exit()
            if event.type == pg.KEYDOWN and event.key == pg.K_RETURN:
                pg.mixer.music.fadeout(1000)
                self.game.set_mainscreen(LoadingScreen(game=self.game, level=self.game.level))

                if 0:  # TODO: debugging
                    self.game.run()
                    if self.game.gameover:
                        # try:
                        #     gameover_screen(self.game)
                        # except RuntimeError as e:
                        #     errmsg = f"error while running game from mainmenu_screen(), {e}"
                        #     print(errmsg, file=sys.stderr)
                        #     quit_exit()
                        pass

    def update(self):
        # clear screen and render background
        self.game.display.fill(self.bgcolor)

        # update text to display
        self.game.draw_text(self.w // 2, 50, self.title_font, pre.WHITE, "TIP")
        self.game.draw_text(self.w // 2, 69, self.title_font, pre.WHITE, "TOE")
        self.game.draw_text(self.w // 2, self.h - 100, self.start_font, pre.WHITE, "Press enter to start")

    def render(self):
        dispmask: pg.Mask = pg.mask.from_surface(self.game.display)
        dispsilhouette = dispmask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
        for offset in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            self.game.display_2.blit(dispsilhouette, offset)

        self.game.display_2.blit(self.game.display, (0, 0))
        self.game.screen.blit(pg.transform.scale(self.game.display_2, self.game.screen.get_size()), (0, 0))

        pg.display.flip()


#
# @dataclass
# class Button:
#     text: str
#     pos: pg.Vector2
#     size: pg.Vector2
#     rect: pg.Rect = field(default_factory=lambda: pg.Rect(0, 0, pre.TILE_SIZE * 4, pre.TILE_SIZE * 3))
#
#     def draw(self, surf: pg.SurfaceType, fill_color: pre.ColorValue) -> None:
#         pg.draw.rect(surf, fill_color, self.rect)
#
#
# @dataclass
# class Textz:
#     font: pg.font.FontType
#     bold: bool = False
#
#     # def __post_init__(self):
#     #     self.font = pg.font.SysFont("monospace", self.font_size, bold=self.bold)
#
#     def render(self, surf: pg.SurfaceType, pos: tuple[int, int], text: str, color: pre.ColorValue = pg.Color('white')):
#         text_surface = self.font.render(text, True, color)
#         text_rect = text_surface.get_rect(center=pos)
#         surf.blit(text_surface, text_rect)
#
