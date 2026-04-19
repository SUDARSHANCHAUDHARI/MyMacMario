import math
import os
import queue
import random
import sys
import threading
from array import array
from dataclasses import dataclass

import pygame
from pygame._sdl2 import Window

try:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSMenu, NSMenuItem, NSStatusBar, NSVariableStatusItemLength
    from Foundation import NSObject
    HAS_APPKIT = True
except Exception:
    HAS_APPKIT = False

try:
    from pynput import keyboard
    HAS_HOTKEY = True
except Exception:
    HAS_HOTKEY = False

try:
    import simpleaudio as sa
    HAS_AUDIO = True
except Exception:
    HAS_AUDIO = False


WINDOW_W = 1280
WINDOW_H = 420
WORLD_WIDTH = 3400
GROUND_Y = 300
GRAVITY = 0.52
MAX_FALL = 13
PLAYER_W = 34
PLAYER_H = 44
PLAYER_H_POWERED = 58
FPS = 60
OVERLAY_MARGIN = 18
JUMP_HOLD_MAX = 14

SCORE_FILE = os.path.expanduser("~/.desktop_mario_mac_score")

# SMB-style opening riff used as the music loop
_MELODY: list[tuple[float, float]] = [
    (659, 0.15), (659, 0.15), (0, 0.15), (659, 0.15),
    (0, 0.15), (523, 0.15), (659, 0.15), (0, 0.30),
    (784, 0.30), (0, 0.60), (392, 0.30), (0, 0.60),
    (523, 0.45), (0, 0.30), (392, 0.45), (0, 0.30),
    (330, 0.45), (0, 0.75),
]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _build_music_sound(sample_rate: int = 22050) -> "pygame.mixer.Sound | None":
    try:
        buf = array("h")
        for freq, dur in _MELODY:
            n = max(1, int(sample_rate * dur))
            for i in range(n):
                if freq == 0:
                    buf.append(0)
                    buf.append(0)
                else:
                    t = i / sample_rate
                    attack = min(1.0, i / max(1, int(sample_rate * 0.008)))
                    release = min(1.0, (n - i) / max(1, int(sample_rate * 0.015)))
                    env = attack * release
                    v = (math.sin(2 * math.pi * freq * t)
                         + 0.45 * math.sin(2 * math.pi * freq * 2 * t)
                         + 0.18 * math.sin(2 * math.pi * freq * 3 * t))
                    val = int(5000 * v * env)
                    buf.append(val)
                    buf.append(val)
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except Exception:
        return None


@dataclass
class RectEntity:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Coin:
    x: float
    y: float
    collected: bool = False
    phase: float = 0.0


@dataclass
class Enemy:
    x: float
    y: float
    w: float
    h: float
    left_bound: float
    right_bound: float
    vx: float = -1.4
    alive: bool = True
    frame: float = 0.0
    enemy_type: str = "goomba"
    shell_sliding: bool = False


@dataclass
class Pipe:
    x: float
    y: float
    dest_x: float
    w: float = 50
    h: float = 60


@dataclass
class Mushroom:
    x: float
    y: float
    vx: float = 1.5
    collected: bool = False


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    ttl: int
    color: tuple[int, int, int]
    size: int


class AudioEngine:
    def __init__(self) -> None:
        self.enabled = HAS_AUDIO
        self.sample_rate = 22050
        self.sound_map = {
            "jump":   [(620, 0.05), (780, 0.05)],
            "coin":   [(900, 0.04), (1240, 0.06)],
            "stomp":  [(220, 0.06), (180, 0.06)],
            "hit":    [(200, 0.08), (120, 0.12)],
            "win":    [(520, 0.08), (660, 0.08), (780, 0.08), (1040, 0.12)],
            "powerup":[(440, 0.06), (554, 0.06), (659, 0.08), (880, 0.10)],
        }

    def play(self, name: str) -> None:
        if not self.enabled or name not in self.sound_map:
            return
        threading.Thread(target=self._play, args=(self.sound_map[name],), daemon=True).start()

    def _play(self, seq: list[tuple[int, float]]) -> None:
        buf = array("h")
        sr = self.sample_rate
        for freq, dur in seq:
            n = max(1, int(sr * dur))
            for i in range(n):
                t = i / sr
                env = math.exp(-5.5 * i / n)
                v = math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(4 * math.pi * freq * t)
                buf.append(int(16000 * v * env))
        sa.play_buffer(buf.tobytes(), 1, 2, sr)


if HAS_APPKIT:
    class StatusBarDelegate(NSObject):
        def toggleOverlay_(self, _sender) -> None:
            self.command_queue.put("toggle_overlay")

        def cycleOpacity_(self, _sender) -> None:
            self.command_queue.put("cycle_opacity")

        def resetRun_(self, _sender) -> None:
            self.command_queue.put("reset")

        def focusWindow_(self, _sender) -> None:
            self.command_queue.put("focus")

        def quitApp_(self, _sender) -> None:
            self.command_queue.put("quit")


# ---------------------------------------------------------------------------
# Level definitions
# ---------------------------------------------------------------------------

def _level_1() -> dict:
    return dict(
        platforms=[
            RectEntity(0,    GROUND_Y, 820, 120),
            RectEntity(920,  GROUND_Y, 430, 120),
            RectEntity(1450, GROUND_Y, 260, 120),
            RectEntity(1780, GROUND_Y, 540, 120),
            RectEntity(2370, GROUND_Y, 320, 120),
            RectEntity(2760, GROUND_Y, 380, 120),
            RectEntity(460,  230, 70, 24),
            RectEntity(530,  230, 70, 24),
            RectEntity(1040, 206, 70, 24),
            RectEntity(1110, 206, 70, 24),
            RectEntity(1180, 206, 70, 24),
            RectEntity(1930, 214, 70, 24),
            RectEntity(2000, 214, 70, 24),
            RectEntity(2070, 214, 70, 24),
            RectEntity(2590, 182, 70, 24),
            RectEntity(2660, 182, 70, 24),
        ],
        question_blocks={(530, 230), (1110, 206), (2000, 214), (2590, 182)},
        coin_positions=[
            (480, 185), (550, 185), (1060, 162), (1130, 162), (1200, 162),
            (1950, 168), (2020, 168), (2090, 168), (1490, 258), (1560, 258),
            (1840, 258), (2610, 138), (2680, 138),
        ],
        enemies=[
            Enemy(690,  GROUND_Y - 26, 30, 26, 620,  790),
            Enemy(1510, GROUND_Y - 26, 30, 26, 1470, 1660),
            Enemy(1860, GROUND_Y - 26, 30, 26, 1810, 2270),
            Enemy(2790, GROUND_Y - 26, 30, 26, 2770, 3070),
            Enemy(1100, GROUND_Y - 32, 28, 32, 950,  1340, enemy_type="koopa"),
            Enemy(2420, GROUND_Y - 32, 28, 32, 2380, 2670, enemy_type="koopa"),
        ],
        pipes=[
            Pipe(x=350,  y=GROUND_Y - 60, dest_x=2900),
            Pipe(x=2850, y=GROUND_Y - 60, dest_x=360),
        ],
    )


def _level_2() -> dict:
    """Harder layout: wider gaps, more enemies, higher jumps required."""
    return dict(
        platforms=[
            RectEntity(0,    GROUND_Y, 600, 120),
            RectEntity(700,  GROUND_Y, 280, 120),
            RectEntity(1080, GROUND_Y, 200, 120),
            RectEntity(1380, GROUND_Y, 150, 120),
            RectEntity(1630, GROUND_Y, 400, 120),
            RectEntity(2130, GROUND_Y, 260, 120),
            RectEntity(2490, GROUND_Y, 200, 120),
            RectEntity(2790, GROUND_Y, 480, 120),
            RectEntity(300,  220, 70, 24),
            RectEntity(500,  195, 70, 24),
            RectEntity(700,  170, 70, 24),
            RectEntity(900,  195, 70, 24),
            RectEntity(1160, 210, 70, 24),
            RectEntity(1440, 185, 70, 24),
            RectEntity(1700, 210, 70, 24),
            RectEntity(1840, 185, 70, 24),
            RectEntity(2200, 195, 70, 24),
            RectEntity(2340, 170, 70, 24),
            RectEntity(2560, 195, 70, 24),
            RectEntity(2700, 170, 70, 24),
        ],
        question_blocks={(500, 195), (900, 195), (1440, 185), (2340, 170)},
        coin_positions=[
            (320, 175), (520, 150), (720, 125), (920, 150),
            (1180, 165), (1460, 140), (1720, 165), (1860, 140),
            (2220, 150), (2360, 125), (2580, 150), (2720, 125),
        ],
        enemies=[
            Enemy(650,  GROUND_Y - 26, 30, 26, 610,  960,  vx=-1.6),
            Enemy(1150, GROUND_Y - 26, 30, 26, 1090, 1360, vx=-1.6),
            Enemy(1700, GROUND_Y - 26, 30, 26, 1640, 2110, vx=-1.6),
            Enemy(2550, GROUND_Y - 26, 30, 26, 2500, 2770, vx=-1.6),
            Enemy(750,  GROUND_Y - 32, 28, 32, 710,  950,  enemy_type="koopa", vx=-1.6),
            Enemy(1480, GROUND_Y - 32, 28, 32, 1390, 1610, enemy_type="koopa", vx=-1.6),
            Enemy(2180, GROUND_Y - 32, 28, 32, 2140, 2470, enemy_type="koopa", vx=-1.6),
            Enemy(2840, GROUND_Y - 26, 30, 26, 2800, 3240, vx=-1.8),
        ],
        pipes=[
            Pipe(x=260,  y=GROUND_Y - 60, dest_x=3050),
            Pipe(x=3000, y=GROUND_Y - 60, dest_x=270),
        ],
    )


_LEVELS = [_level_1, _level_2]


# ---------------------------------------------------------------------------
# Main game class
# ---------------------------------------------------------------------------

class DesktopMarioMac:
    def __init__(self) -> None:
        self.screensaver_mode = "--screensaver" in sys.argv
        os.environ.setdefault("SDL_VIDEO_ALLOW_SCREENSAVER", "1")
        pygame.mixer.pre_init(22050, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption("Desktop Mario Mac")
        self.display_flags = pygame.SCALED
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H), self.display_flags)
        self.window = Window.from_display_module()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Menlo", 18, bold=True)
        self.small_font = pygame.font.SysFont("Menlo", 12)
        self.big_font = pygame.font.SysFont("Menlo", 22, bold=True)
        desktop_sizes = pygame.display.get_desktop_sizes()
        self.screen_w, self.screen_h = desktop_sizes[0] if desktop_sizes else self.window.size
        self.overlay_mode = False
        self.overlay_opacity = 0.92

        self.running = True
        self.paused = False
        self.audio = AudioEngine()
        self.best_score = self._load_best_score()
        self.current_level = 0
        self.music_on = True
        self.music_sound: "pygame.mixer.Sound | None" = _build_music_sound()
        self.music_channel: "pygame.mixer.Channel | None" = None
        self.command_queue: queue.Queue[str] = queue.Queue()
        self.status_item = None
        self.status_delegate = None
        self.reset_level()
        self._apply_window_mode()
        self._start_hotkey_listener()
        self._start_tray()
        self._start_music()

    # ------------------------------------------------------------------
    # Score persistence
    # ------------------------------------------------------------------

    def _load_best_score(self) -> int:
        try:
            with open(SCORE_FILE) as f:
                return int(f.read().strip())
        except Exception:
            return 0

    def _save_best_score(self) -> None:
        try:
            with open(SCORE_FILE, "w") as f:
                f.write(str(self.best_score))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    def _start_music(self) -> None:
        if self.music_sound is None or not self.music_on:
            return
        try:
            self.music_channel = self.music_sound.play(loops=-1)
            if self.music_channel:
                self.music_channel.set_volume(0.28)
        except Exception:
            pass

    def _toggle_music(self) -> None:
        self.music_on = not self.music_on
        if self.music_on:
            self._start_music()
            self.message = "Music on"
        else:
            if self.music_channel:
                self.music_channel.stop()
            self.message = "Music off"
        self.message_ticks = 80

    # ------------------------------------------------------------------
    # Level setup
    # ------------------------------------------------------------------

    def reset_level(self) -> None:
        layout = _LEVELS[self.current_level % len(_LEVELS)]()
        self.platforms: list[RectEntity] = layout["platforms"]
        self.question_blocks: set[tuple[float, float]] = layout["question_blocks"]
        self.question_blocks_hit: set[tuple[float, float]] = set()
        self.coins = [
            Coin(x, y, phase=random.random() * math.tau)
            for x, y in layout["coin_positions"]
        ]
        self.enemies: list[Enemy] = layout["enemies"]
        self.pipes: list[Pipe] = layout["pipes"]
        self.mushrooms: list[Mushroom] = []
        self.player = RectEntity(96, GROUND_Y - PLAYER_H, PLAYER_W, PLAYER_H)
        self.player_vx = 0.0
        self.player_vy = 0.0
        self.on_ground = True
        self.facing = 1
        self.coyote_frames = 0
        self.jump_buffer = 0
        self.jump_hold_frames = 0
        self.invuln_ticks = 0
        self.player_anim = 0.0
        self.powered = False
        self.pipe_warp_ticks = 0
        self.pipe_dest_x = 0.0
        self.camera_x = 0.0
        self.score = 0
        self.message = f"Level {self.current_level + 1}"
        self.message_ticks = 180
        self.level_complete = False
        self.particles: list[Particle] = []
        self.paused = False

    def _player_h(self) -> float:
        return PLAYER_H_POWERED if self.powered else PLAYER_H

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while self.running:
            self.clock.tick(FPS)
            self._drain_external_commands()
            self._handle_events()
            self._update()
            self._draw()
        self._save_best_score()
        if self.music_channel:
            self.music_channel.stop()
        if self.status_item is not None:
            try:
                NSStatusBar.systemStatusBar().removeStatusItem_(self.status_item)
            except Exception:
                pass
        pygame.quit()

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if self.screensaver_mode:
                    self.running = False
                    return
                if event.key == pygame.K_ESCAPE:
                    if self.overlay_mode:
                        self.toggle_overlay_mode()
                    else:
                        self.running = False
                elif event.key == pygame.K_TAB:
                    self._toggle_pause()
                elif event.key == pygame.K_r:
                    self.reset_level()
                elif event.key in (pygame.K_SPACE, pygame.K_UP):
                    if not self.paused:
                        self.jump_buffer = 8
                elif event.key == pygame.K_F10:
                    self.toggle_overlay_mode()
                elif event.key == pygame.K_F11:
                    self.cycle_overlay_opacity()
                elif event.key == pygame.K_o:
                    self.toggle_overlay_mode()
                elif event.key == pygame.K_p:
                    self.cycle_overlay_opacity()
                elif event.key == pygame.K_m:
                    self._toggle_music()
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_SPACE, pygame.K_UP):
                    self.jump_hold_frames = 0
                    if self.player_vy < -4.5:
                        self.player_vy *= 0.58

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            if self.music_channel:
                pygame.mixer.pause()
        else:
            if self.music_on and self.music_channel:
                pygame.mixer.unpause()

    def _drain_external_commands(self) -> None:
        while not self.command_queue.empty():
            cmd = self.command_queue.get_nowait()
            if cmd == "toggle_overlay":
                self.toggle_overlay_mode()
            elif cmd == "cycle_opacity":
                self.cycle_overlay_opacity()
            elif cmd == "reset":
                self.reset_level()
            elif cmd == "quit":
                self.running = False
            elif cmd == "focus":
                try:
                    self.window.focus(input_only=False)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Hotkey / tray / window
    # ------------------------------------------------------------------

    def _start_hotkey_listener(self) -> None:
        if not HAS_HOTKEY:
            return

        def run() -> None:
            keyboard.GlobalHotKeys({
                "<ctrl>+<alt>+o": lambda: self.command_queue.put("toggle_overlay"),
                "<ctrl>+<alt>+p": lambda: self.command_queue.put("cycle_opacity"),
            }).run()

        threading.Thread(target=run, daemon=True).start()

    def _start_tray(self) -> None:
        if HAS_APPKIT:
            self._start_native_status_item()

    def _start_native_status_item(self) -> bool:
        try:
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            self.status_delegate = StatusBarDelegate.alloc().init()
            self.status_delegate.command_queue = self.command_queue
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
            self.status_item.button().setTitle_("M")
            self.status_item.button().setToolTip_("Desktop Mario Mac")
            menu = NSMenu.alloc().init()
            for title, action in [
                ("Toggle Overlay", "toggleOverlay:"),
                ("Cycle Opacity",  "cycleOpacity:"),
                ("Reset Run",      "resetRun:"),
                ("Focus Window",   "focusWindow:"),
                ("Quit",           "quitApp:"),
            ]:
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
                item.setTarget_(self.status_delegate)
                menu.addItem_(item)
            self.status_item.setMenu_(menu)
            return True
        except Exception:
            self.status_item = None
            self.status_delegate = None
            return False

    def toggle_overlay_mode(self) -> None:
        self.overlay_mode = not self.overlay_mode
        self._apply_window_mode()
        self.message = "Overlay mode on" if self.overlay_mode else "Window mode on"
        self.message_ticks = 120

    def cycle_overlay_opacity(self) -> None:
        if not self.overlay_mode:
            self.message = "Enable overlay mode first"
            self.message_ticks = 90
            return
        values = [0.82, 0.9, 0.96]
        idx = min(range(len(values)), key=lambda i: abs(values[i] - self.overlay_opacity))
        self.overlay_opacity = values[(idx + 1) % len(values)]
        self._apply_window_mode()
        self.message = f"Opacity {int(self.overlay_opacity * 100)}%"
        self.message_ticks = 90

    def _apply_window_mode(self) -> None:
        ww, wh = WINDOW_W, WINDOW_H
        x = (self.screen_w - ww) // 2
        y = (self.screen_h - wh) // 2
        self.window.resizable = False
        self.window.size = (ww, wh)
        if self.screensaver_mode:
            self.window.borderless = True
            self.window.always_on_top = True
            self.window.opacity = 0.88
            self.window.position = (x, y)
        elif self.overlay_mode:
            y = self.screen_h - wh - OVERLAY_MARGIN
            self.window.borderless = True
            self.window.always_on_top = True
            self.window.opacity = self.overlay_opacity
            self.window.position = (x, max(40, y))
        else:
            self.window.borderless = False
            self.window.always_on_top = False
            self.window.opacity = 1.0
            self.window.position = (x, max(40, y))

    # ------------------------------------------------------------------
    # Dock badge
    # ------------------------------------------------------------------

    def _update_dock_badge(self) -> None:
        if not HAS_APPKIT:
            return
        try:
            label = str(self.score) if self.score > 0 else ""
            NSApplication.sharedApplication().dockTile().setBadgeLabel_(label)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Game update
    # ------------------------------------------------------------------

    def _update(self) -> None:
        if self.paused:
            return

        self.player_anim += 0.22
        if self.message_ticks > 0:
            self.message_ticks -= 1
        if self.invuln_ticks > 0:
            self.invuln_ticks -= 1
        if self.jump_buffer > 0:
            self.jump_buffer -= 1

        if self.pipe_warp_ticks > 0:
            self.pipe_warp_ticks -= 1
            if self.pipe_warp_ticks == 0:
                ph = self._player_h()
                self.player.x = self.pipe_dest_x
                self.player.y = GROUND_Y - ph
                self.player.h = ph
                self.player_vx = 0.0
                self.player_vy = 0.0
                self.camera_x = clamp(self.player.x - WINDOW_W * 0.35, 0, max(0, WORLD_WIDTH - WINDOW_W))
            return

        keys = pygame.key.get_pressed()
        left  = keys[pygame.K_LEFT]  or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        run   = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        jump_held = keys[pygame.K_SPACE] or keys[pygame.K_UP]
        down  = keys[pygame.K_DOWN]  or keys[pygame.K_s]

        if self.level_complete:
            self.camera_x += (max(0, WORLD_WIDTH - WINDOW_W) - self.camera_x) * 0.08
            if self.message_ticks == 0:
                self.current_level = (self.current_level + 1) % len(_LEVELS)
                self.reset_level()
            return

        max_speed = 7.4 if run else 4.8
        accel = 0.85 if self.on_ground else 0.45
        target_vx = (-max_speed if left else 0.0) + (max_speed if right else 0.0)
        ratio = abs(self.player_vx) / max_speed if max_speed > 0 else 0.0
        quad = 0.12 + 0.10 * ratio * ratio
        self.player_vx += (target_vx - self.player_vx) * accel * quad
        if abs(target_vx) < 0.1:
            self.player_vx *= 0.78 if self.on_ground else 0.96
        if abs(self.player_vx) < 0.05:
            self.player_vx = 0.0
        if self.player_vx != 0:
            self.facing = 1 if self.player_vx > 0 else -1

        if (self.on_ground or self.coyote_frames > 0) and self.jump_buffer > 0:
            self.player_vy = -11.8 if run else -11.0
            self.on_ground = False
            self.coyote_frames = 0
            self.jump_buffer = 0
            self.jump_hold_frames = 1
            self.audio.play("jump")
            self._burst(self.player.x + self.player.w / 2, self.player.y + self.player.h, (255, 242, 191), 6)

        if jump_held and self.player_vy < 0 and self.jump_hold_frames > 0:
            self.jump_hold_frames += 1
            grav = GRAVITY * (0.35 if self.jump_hold_frames <= JUMP_HOLD_MAX else 1.0)
        else:
            if not jump_held:
                self.jump_hold_frames = 0
            grav = GRAVITY

        self.player.x += self.player_vx
        self._resolve_horizontal()
        was_grounded = self.on_ground
        self.player_vy = clamp(self.player_vy + grav, -20, MAX_FALL)
        self.player.y += self.player_vy
        self.on_ground = False
        self._resolve_vertical()
        self.coyote_frames = 6 if self.on_ground else max(0, self.coyote_frames - 1)
        if self.on_ground and not was_grounded:
            self._burst(self.player.x + self.player.w / 2, self.player.y + self.player.h, (247, 223, 156), 4)

        if self.player.y > WINDOW_H + 80:
            ph = self._player_h()
            self.player.x = 96
            self.player.y = GROUND_Y - ph
            self.player.h = ph
            self.player_vx = 0
            self.player_vy = 0
            if self.powered:
                self.powered = False
            self.message = "Watch the gaps."
            self.message_ticks = 100
            self.audio.play("hit")

        target_cam = clamp(self.player.x - WINDOW_W * 0.35, 0, max(0, WORLD_WIDTH - WINDOW_W))
        self.camera_x += (target_cam - self.camera_x) * 0.12

        for coin in self.coins:
            coin.phase += 0.2
            if not coin.collected and self._circle_hits_player(coin.x, coin.y, 12):
                coin.collected = True
                self.score += 100
                self.best_score = max(self.best_score, self.score)
                self.message = "+100"
                self.message_ticks = 25
                self.audio.play("coin")
                self._burst(coin.x, coin.y, (247, 199, 58), 8)
                self._update_dock_badge()

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            enemy.frame += 0.18
            speed = enemy.vx * 4.5 if (enemy.shell_sliding and enemy.vx != 0) else enemy.vx
            enemy.x += speed
            if enemy.x <= enemy.left_bound or enemy.x + enemy.w >= enemy.right_bound:
                enemy.vx *= -1
            if not self._rects_overlap(self.player, enemy):
                continue
            stomp = self.player_vy > 1.5 and self.player.y + self.player.h - 6 <= enemy.y + 10
            if stomp:
                if enemy.enemy_type == "koopa" and not enemy.shell_sliding:
                    enemy.shell_sliding = True
                    enemy.vx = 0.0
                    self.player_vy = -7.8
                    self.score += 100
                    self.best_score = max(self.best_score, self.score)
                    self.message = "shell! +100"
                    self.message_ticks = 40
                    self.audio.play("stomp")
                    self._burst(enemy.x + enemy.w / 2, enemy.y + enemy.h / 2, (74, 140, 58), 8)
                else:
                    enemy.alive = False
                    self.player_vy = -7.8
                    self.score += 250
                    self.best_score = max(self.best_score, self.score)
                    self.message = "stomp +250"
                    self.message_ticks = 40
                    self.audio.play("stomp")
                    self._burst(enemy.x + enemy.w / 2, enemy.y + enemy.h / 2, (142, 90, 47), 10)
                self._update_dock_badge()
            elif enemy.enemy_type == "koopa" and enemy.shell_sliding and enemy.vx == 0:
                enemy.vx = 1.4 if self.player.x < enemy.x else -1.4
            elif self.invuln_ticks == 0:
                self.invuln_ticks = 90
                if self.powered:
                    self.powered = False
                    self.player.h = PLAYER_H
                    self.message = "Power down!"
                else:
                    self.player.x = max(40, self.player.x - 70)
                    self.player_vx = -4 * self.facing
                    self.message = "Ouch."
                self.message_ticks = 50
                self.audio.play("hit")

        for mush in self.mushrooms:
            if mush.collected:
                continue
            mush.x += mush.vx
            mr = RectEntity(mush.x, mush.y, 22, 22)
            for plat in self.platforms:
                if self._rects_overlap(mr, plat):
                    mush.vx *= -1
                    break
            if self._circle_hits_player(mush.x + 11, mush.y + 11, 13):
                mush.collected = True
                self.powered = True
                self.player.h = PLAYER_H_POWERED
                self.score += 500
                self.best_score = max(self.best_score, self.score)
                self.message = "Power up! +500"
                self.message_ticks = 60
                self.audio.play("powerup")
                self._update_dock_badge()

        if self.player_vy < -3 and not self.on_ground:
            head = RectEntity(self.player.x + 4, self.player.y - 4, self.player.w - 8, 6)
            for plat in self.platforms:
                qk = (plat.x, plat.y)
                if qk in self.question_blocks and qk not in self.question_blocks_hit:
                    if self._rects_overlap(head, plat):
                        self.question_blocks_hit.add(qk)
                        self.mushrooms.append(Mushroom(x=plat.x + plat.w / 2 - 11, y=plat.y - 28))
                        self.audio.play("powerup")
                        self._burst(plat.x + plat.w / 2, plat.y, (249, 199, 54), 10)

        if down and self.on_ground and self.pipe_warp_ticks == 0 and self.invuln_ticks == 0:
            for pipe in self.pipes:
                if self._rects_overlap(self.player, RectEntity(pipe.x, pipe.y, pipe.w, pipe.h)):
                    self.pipe_warp_ticks = 45
                    self.pipe_dest_x = pipe.dest_x
                    self.message = "Warp!"
                    self.message_ticks = 60
                    break

        for p in list(self.particles):
            p.x += p.vx
            p.y += p.vy
            p.vy += 0.24
            p.ttl -= 1
            if p.ttl <= 0:
                self.particles.remove(p)

        if self.player.x > WORLD_WIDTH - 150:
            self.level_complete = True
            self.message = f"Level {self.current_level + 1} clear!"
            self.message_ticks = 200
            self.audio.play("win")
            self.best_score = max(self.best_score, self.score)
            self._save_best_score()
            self._update_dock_badge()

    # ------------------------------------------------------------------
    # Collision helpers
    # ------------------------------------------------------------------

    def _resolve_horizontal(self) -> None:
        for plat in self.platforms:
            if self._rects_overlap(self.player, plat):
                if self.player_vx > 0:
                    self.player.x = plat.x - self.player.w
                elif self.player_vx < 0:
                    self.player.x = plat.x + plat.w

    def _resolve_vertical(self) -> None:
        for plat in self.platforms:
            if self._rects_overlap(self.player, plat):
                if self.player_vy >= 0 and self.player.y + self.player.h - self.player_vy <= plat.y + 5:
                    self.player.y = plat.y - self.player.h
                    self.player_vy = 0
                    self.on_ground = True
                elif self.player_vy < 0 and self.player.y - self.player_vy >= plat.y + plat.h - 5:
                    self.player.y = plat.y + plat.h
                    self.player_vy = 0

    def _circle_hits_player(self, x: float, y: float, r: float) -> bool:
        nx = max(self.player.x, min(x, self.player.x + self.player.w))
        ny = max(self.player.y, min(y, self.player.y + self.player.h))
        return (x - nx) ** 2 + (y - ny) ** 2 <= r * r

    def _rects_overlap(self, a: RectEntity, b: RectEntity) -> bool:
        return a.x < b.x + b.w and a.x + a.w > b.x and a.y < b.y + b.h and a.y + a.h > b.y

    def _burst(self, x: float, y: float, color: tuple[int, int, int], count: int) -> None:
        for _ in range(count):
            self.particles.append(Particle(
                x=x, y=y,
                vx=random.uniform(-2.8, 2.8),
                vy=random.uniform(-4.6, -1.4),
                ttl=random.randint(18, 32),
                color=color,
                size=random.randint(3, 6),
            ))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        self.screen.fill((120, 201, 255))
        self._draw_background()
        self._draw_world()
        self._draw_particles()
        if not self.screensaver_mode:
            self._draw_ui()
        if self.paused:
            self._draw_pause_overlay()
        pygame.display.flip()

    def _draw_background(self) -> None:
        pygame.draw.rect(self.screen, (188, 230, 255), (0, 0, WINDOW_W, 44))
        for idx in range(5):
            cx = ((idx * 320) - (self.camera_x * (0.12 + idx * 0.01))) % (WINDOW_W + 180) - 90
            cy = 46 + (idx % 2) * 24
            self._draw_cloud(cx, cy)
        for idx, col in enumerate(((184, 216, 162), (146, 191, 116), (110, 162, 84))):
            par = 0.18 + idx * 0.07
            base_y = 224 + idx * 28
            pts = [(0, WINDOW_H)]
            for x in range(-120, WINDOW_W + 121, 120):
                h = 28 + (math.sin((x + self.camera_x * par) / 130) + 1) * 24 + idx * 8
                pts.append((x, base_y - h))
            pts.append((WINDOW_W, WINDOW_H))
            pygame.draw.polygon(self.screen, col, pts)

    def _draw_cloud(self, x: float, y: float) -> None:
        for dx, dy, r in [(0, 8, 22), (24, 0, 24), (52, 10, 18), (78, 8, 14)]:
            pygame.draw.circle(self.screen, (255, 255, 255), (int(x + dx + r), int(y + dy + r)), r)

    def _draw_world(self) -> None:
        for pipe in self.pipes:
            px, py, pw, ph = int(pipe.x - self.camera_x), int(pipe.y), int(pipe.w), int(pipe.h)
            pygame.draw.rect(self.screen, (58, 158, 58),  (px + 4, py + 14, pw - 8, ph - 14))
            pygame.draw.rect(self.screen, (34, 110, 34),  (px + 4, py + 14, pw - 8, ph - 14), 2)
            pygame.draw.rect(self.screen, (58, 158, 58),  (px, py, pw, 14))
            pygame.draw.rect(self.screen, (34, 110, 34),  (px, py, pw, 14), 2)

        for plat in self.platforms:
            if plat.y >= GROUND_Y:
                self._draw_ground(plat)
            else:
                self._draw_block(plat)

        for coin in self.coins:
            if coin.collected:
                continue
            cx = int(coin.x - self.camera_x)
            cy = int(coin.y + math.sin(coin.phase) * 2)
            pygame.draw.circle(self.screen, (242, 194, 48), (cx, cy), 12)
            pygame.draw.circle(self.screen, (156, 112, 0),  (cx, cy), 12, 3)

        for mush in self.mushrooms:
            if mush.collected:
                continue
            mx, my = int(mush.x - self.camera_x), int(mush.y)
            pygame.draw.circle(self.screen, (215, 50, 50),  (mx + 11, my + 8), 13)
            pygame.draw.rect(self.screen,   (241, 200, 155), (mx + 3, my + 10, 18, 12))
            pygame.draw.circle(self.screen, (255, 255, 255), (mx + 7,  my + 5),  3)
            pygame.draw.circle(self.screen, (255, 255, 255), (mx + 15, my + 4),  3)

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            ex, ey = int(enemy.x - self.camera_x), int(enemy.y)
            if enemy.enemy_type == "koopa":
                if enemy.shell_sliding:
                    pygame.draw.ellipse(self.screen, (74, 140, 58), (ex, ey + 6, enemy.w, enemy.h - 6))
                    pygame.draw.ellipse(self.screen, (48, 100, 38), (ex, ey + 6, enemy.w, enemy.h - 6), 2)
                    pygame.draw.line(self.screen, (48, 100, 38), (ex + enemy.w // 2, ey + 8), (ex + enemy.w // 2, ey + enemy.h), 2)
                    pygame.draw.line(self.screen, (48, 100, 38), (ex, ey + enemy.h // 2 + 4), (ex + enemy.w, ey + enemy.h // 2 + 4), 2)
                else:
                    pygame.draw.ellipse(self.screen, (74, 140, 58),  (ex + 2, ey + 8, enemy.w - 4, enemy.h - 8))
                    pygame.draw.rect(self.screen,   (241, 200, 155), (ex + 6, ey, enemy.w - 12, 10))
                    eo = 5 if enemy.vx > 0 else 2
                    pygame.draw.circle(self.screen, (0, 0, 0), (ex + eo + 6, ey + 5), 2)
            else:
                pygame.draw.ellipse(self.screen, (139, 76, 32), (ex, ey + 8, enemy.w, enemy.h - 8))
                pygame.draw.rect(self.screen,   (90, 44, 15),  (ex + 4, ey + 2, enemy.w - 8, 12))
                eo = 6 if enemy.vx > 0 else 1
                pygame.draw.circle(self.screen, (255, 255, 255), (ex + eo + 8,  ey + 15), 2)
                pygame.draw.circle(self.screen, (255, 255, 255), (ex + eo + 16, ey + 15), 2)

        if not (self.invuln_ticks > 0 and self.invuln_ticks % 8 < 4):
            self._draw_player()

        fx = int(WORLD_WIDTH - self.camera_x - 90)
        pygame.draw.rect(self.screen,     (236, 236, 236), (fx, 70, 6, GROUND_Y - 70))
        pygame.draw.polygon(self.screen,  (241, 74, 55),   [(fx + 6, 84), (fx + 52, 96), (fx + 6, 110)])

    def _draw_ground(self, plat: RectEntity) -> None:
        x = int(plat.x - self.camera_x)
        pygame.draw.rect(self.screen, (156, 107, 48), (x, int(plat.y), int(plat.w), int(plat.h)))
        pygame.draw.rect(self.screen, (101, 181, 75), (x, int(plat.y), int(plat.w), 18))
        for lx in range(x, x + int(plat.w), 26):
            pygame.draw.line(self.screen, (122, 75, 30), (lx, int(plat.y) + 18), (lx + 10, int(plat.y + plat.h)), 2)

    def _draw_block(self, plat: RectEntity) -> None:
        x = int(plat.x - self.camera_x)
        qk = (plat.x, plat.y)
        is_q = qk in self.question_blocks and qk not in self.question_blocks_hit
        color  = (194, 120, 28) if is_q else (123, 84, 37)
        border = (249, 199, 54) if is_q else (214, 176, 111)
        pygame.draw.rect(self.screen, color,  (x, int(plat.y), int(plat.w), int(plat.h)))
        pygame.draw.rect(self.screen, border, (x, int(plat.y), int(plat.w), int(plat.h)), 3)
        if is_q:
            q = self.small_font.render("?", True, (255, 255, 255))
            self.screen.blit(q, (x + int(plat.w) // 2 - q.get_width() // 2, int(plat.y) + 4))

    def _draw_player(self) -> None:
        x  = int(self.player.x - self.camera_x)
        y  = int(self.player.y)
        ph = int(self._player_h())
        pygame.draw.rect(self.screen, (37, 84, 199), (x + 6, y + ph - 28, self.player.w - 12, 28))
        if self.powered:
            pygame.draw.rect(self.screen, (215, 75, 57),  (x + 4, y + ph - 44, self.player.w - 8, 18))
            pygame.draw.rect(self.screen, (241, 200, 155), (x + 7, y + ph - 30, self.player.w - 14, 14))
            pygame.draw.rect(self.screen, (140, 43, 24),  (x + 3, y + ph - 52, self.player.w - 6, 10))
            pygame.draw.rect(self.screen, (215, 75, 57),  (x + 1, y + ph - 44, self.player.w - 2, 4))
            pygame.draw.circle(self.screen, (255, 220, 50), (x + self.player.w // 2, y + ph - 36), 4)
        else:
            pygame.draw.rect(self.screen, (215, 75, 57),   (x + 4, y + 8,  self.player.w - 8,  12))
            pygame.draw.rect(self.screen, (241, 200, 155), (x + 7, y + 18, self.player.w - 14, 12))
            pygame.draw.rect(self.screen, (140, 43, 24),  (x + 3, y + 2,  self.player.w - 6,   8))
            pygame.draw.rect(self.screen, (215, 75, 57),  (x + 1, y + 10, self.player.w - 2,   4))
        pygame.draw.circle(self.screen, (0, 0, 0), (x + 12,                y + ph - 16), 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (x + self.player.w - 12, y + ph - 16), 2)

    def _draw_particles(self) -> None:
        for p in self.particles:
            pygame.draw.rect(self.screen, p.color,
                             (int(p.x - self.camera_x), int(p.y), p.size, p.size))

    def _draw_ui(self) -> None:
        pygame.draw.rect(self.screen, (14, 20, 32), (24, 20, 440, 100), border_radius=14)
        self.screen.blit(self.font.render(f"Score {self.score}  Lv{self.current_level + 1}", True, (255, 255, 255)), (42, 34))
        self.screen.blit(self.small_font.render(f"Best {self.best_score}    Esc quit    R reset    Tab pause", True, (247, 213, 109)), (42, 68))
        self.screen.blit(self.small_font.render("Arrows/WASD move · Space jump · Shift run · Down pipe · M music", True, (201, 231, 255)), (42, 88))

        ml = "overlay" if self.overlay_mode else "window"
        badge = self.small_font.render(
            f"pygame {ml}  |  Ctrl+Alt+O  |  M menu  |  {'♪ on' if self.music_on else '♪ off'}",
            True, (216, 239, 255),
        )
        pygame.draw.rect(self.screen, (22, 35, 53), (WINDOW_W - 372, 24, 348, 40), border_radius=10)
        self.screen.blit(badge, (WINDOW_W - 278, 36))

        if self.message_ticks > 0:
            t = self.big_font.render(self.message, True, (255, 255, 255))
            self.screen.blit(t, (WINDOW_W // 2 - t.get_width() // 2, 28))

    def _draw_pause_overlay(self) -> None:
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        lines = [
            (self.big_font, "PAUSED",       (255, 255, 255)),
            (self.font,     "Tab to resume", (201, 231, 255)),
            (self.font,     "R to restart",  (201, 231, 255)),
        ]
        total_h = sum(self.big_font.get_height() if i == 0 else self.font.get_height() for i, _ in enumerate(lines)) + 12
        y = (WINDOW_H - total_h) // 2
        for fnt, text, color in lines:
            surf = fnt.render(text, True, color)
            self.screen.blit(surf, (WINDOW_W // 2 - surf.get_width() // 2, y))
            y += surf.get_height() + 6


if __name__ == "__main__":
    DesktopMarioMac().run()
