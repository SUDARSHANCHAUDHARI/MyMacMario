import math
import os
import queue
import random
import threading
import traceback
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
FPS = 60
OVERLAY_MARGIN = 18
DEBUG_LOG_PATH = "/tmp/desktop_mario_mac.log"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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
            "jump": [(620, 0.05), (780, 0.05)],
            "coin": [(900, 0.04), (1240, 0.06)],
            "stomp": [(220, 0.06), (180, 0.06)],
            "hit": [(200, 0.08), (120, 0.12)],
            "win": [(520, 0.08), (660, 0.08), (780, 0.08), (1040, 0.12)],
        }

    def play(self, name: str) -> None:
        if not self.enabled or name not in self.sound_map:
            return
        threading.Thread(target=self._play_sequence, args=(self.sound_map[name],), daemon=True).start()

    def _play_sequence(self, sequence: list[tuple[int, float]]) -> None:
        samples = array("h")
        for freq, duration in sequence:
            length = max(1, int(self.sample_rate * duration))
            for i in range(length):
                t = i / self.sample_rate
                envelope = math.exp(-5.5 * i / length)
                wave = math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * freq * 2 * t)
                samples.append(int(16000 * wave * envelope))
        sa.play_buffer(samples.tobytes(), 1, 2, self.sample_rate)


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


class DesktopMarioMac:
    def __init__(self) -> None:
        os.environ.setdefault("SDL_VIDEO_ALLOW_SCREENSAVER", "1")
        self._debug("app boot")
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
        self.audio = AudioEngine()
        self.best_score = 0
        self.command_queue: queue.Queue[str] = queue.Queue()
        self.status_item = None
        self.status_delegate = None
        self.integration_status = "menu pending"
        self.integration_detail = "starting integration checks"
        self.reset_level()
        self._apply_window_mode()
        self._start_hotkey_listener()
        self._start_tray()

    def reset_level(self) -> None:
        self.platforms = [
            RectEntity(0, GROUND_Y, 820, 120),
            RectEntity(920, GROUND_Y, 430, 120),
            RectEntity(1450, GROUND_Y, 260, 120),
            RectEntity(1780, GROUND_Y, 540, 120),
            RectEntity(2370, GROUND_Y, 320, 120),
            RectEntity(2760, GROUND_Y, 380, 120),
            RectEntity(460, 230, 70, 24),
            RectEntity(530, 230, 70, 24),
            RectEntity(1040, 206, 70, 24),
            RectEntity(1110, 206, 70, 24),
            RectEntity(1180, 206, 70, 24),
            RectEntity(1930, 214, 70, 24),
            RectEntity(2000, 214, 70, 24),
            RectEntity(2070, 214, 70, 24),
            RectEntity(2590, 182, 70, 24),
            RectEntity(2660, 182, 70, 24),
        ]
        self.question_blocks = {(530, 230), (1110, 206), (2000, 214), (2590, 182)}
        self.coins = [
            Coin(x, y, phase=random.random() * math.tau)
            for x, y in [
                (480, 185), (550, 185), (1060, 162), (1130, 162), (1200, 162),
                (1950, 168), (2020, 168), (2090, 168), (1490, 258), (1560, 258),
                (1840, 258), (2610, 138), (2680, 138),
            ]
        ]
        self.enemies = [
            Enemy(690, GROUND_Y - 26, 30, 26, 620, 790),
            Enemy(1510, GROUND_Y - 26, 30, 26, 1470, 1660),
            Enemy(1860, GROUND_Y - 26, 30, 26, 1810, 2270),
            Enemy(2790, GROUND_Y - 26, 30, 26, 2770, 3070),
        ]
        self.player = RectEntity(96, GROUND_Y - PLAYER_H, PLAYER_W, PLAYER_H)
        self.player_vx = 0.0
        self.player_vy = 0.0
        self.on_ground = True
        self.facing = 1
        self.coyote_frames = 0
        self.jump_buffer = 0
        self.invuln_ticks = 0
        self.player_anim = 0.0
        self.camera_x = 0.0
        self.score = 0
        self.message = "Desktop Mario Mac"
        self.message_ticks = 180
        self.level_complete = False
        self.particles: list[Particle] = []

    def run(self) -> None:
        while self.running:
            self.clock.tick(FPS)
            self._drain_external_commands()
            self._handle_events()
            self._update()
            self._draw()
        if self.status_item is not None:
            try:
                NSStatusBar.systemStatusBar().removeStatusItem_(self.status_item)
            except Exception:
                pass
        pygame.quit()

    def _debug(self, message: str) -> None:
        try:
            with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as log_file:
                log_file.write(message + "\n")
        except Exception:
            pass

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.overlay_mode:
                        self.toggle_overlay_mode()
                    else:
                        self.running = False
                elif event.key == pygame.K_r:
                    self.reset_level()
                elif event.key in (pygame.K_SPACE, pygame.K_UP):
                    self.jump_buffer = 8
                elif event.key == pygame.K_F10:
                    self.toggle_overlay_mode()
                elif event.key == pygame.K_F11:
                    self.cycle_overlay_opacity()
                elif event.key == pygame.K_o:
                    self.toggle_overlay_mode()
                elif event.key == pygame.K_p:
                    self.cycle_overlay_opacity()
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_SPACE, pygame.K_UP) and self.player_vy < -4.5:
                    self.player_vy *= 0.58

    def _drain_external_commands(self) -> None:
        while not self.command_queue.empty():
            command = self.command_queue.get_nowait()
            if command == "toggle_overlay":
                self.toggle_overlay_mode()
            elif command == "cycle_opacity":
                self.cycle_overlay_opacity()
            elif command == "reset":
                self.reset_level()
            elif command == "quit":
                self.running = False
            elif command == "focus":
                try:
                    self.window.focus(input_only=False)
                except Exception:
                    pass

    def _start_hotkey_listener(self) -> None:
        if not HAS_HOTKEY:
            self._debug("hotkey unavailable")
            return

        def run_listener() -> None:
            listener = keyboard.GlobalHotKeys(
                {
                    "<ctrl>+<alt>+o": lambda: self.command_queue.put("toggle_overlay"),
                    "<ctrl>+<alt>+p": lambda: self.command_queue.put("cycle_opacity"),
                }
            )
            listener.run()

        threading.Thread(target=run_listener, daemon=True).start()
        self._debug("hotkey listener started")

    def _start_tray(self) -> None:
        if HAS_APPKIT and self._start_native_status_item():
            self.integration_status = "native menu bar active"
            self.integration_detail = "look for M in top-right menu bar"
            return
        if not HAS_APPKIT:
            self.integration_status = "menu bar unavailable"
            self.integration_detail = "AppKit unavailable"
            self._debug("native menu unavailable")

    def _start_native_status_item(self) -> bool:
        try:
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
            self.status_delegate = StatusBarDelegate.alloc().init()
            self.status_delegate.command_queue = self.command_queue
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
            button = self.status_item.button()
            button.setTitle_("M")
            button.setToolTip_("Desktop Mario Mac")

            menu = NSMenu.alloc().init()
            items = [
                ("Toggle Overlay", "toggleOverlay:"),
                ("Cycle Opacity", "cycleOpacity:"),
                ("Reset Run", "resetRun:"),
                ("Focus Window", "focusWindow:"),
                ("Quit", "quitApp:"),
            ]
            for title, action in items:
                item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
                item.setTarget_(self.status_delegate)
                menu.addItem_(item)
            self.status_item.setMenu_(menu)
            self._debug("native status item created")
            return True
        except Exception as exc:
            self.status_item = None
            self.status_delegate = None
            self.integration_status = "native menu failed"
            self.integration_detail = str(exc)[:90]
            self._debug("native status item failed")
            self._debug(traceback.format_exc())
            return False

    def toggle_overlay_mode(self) -> None:
        self.overlay_mode = not self.overlay_mode
        self._apply_window_mode()
        if self.overlay_mode:
            self.message = "Overlay mode on"
        else:
            self.message = "Window mode on"
        self.message_ticks = 120

    def cycle_overlay_opacity(self) -> None:
        if not self.overlay_mode:
            self.message = "Enable overlay mode first"
            self.message_ticks = 90
            return
        values = [0.82, 0.9, 0.96]
        current_index = min(range(len(values)), key=lambda idx: abs(values[idx] - self.overlay_opacity))
        self.overlay_opacity = values[(current_index + 1) % len(values)]
        self._apply_window_mode()
        self.message = f"Overlay opacity {int(self.overlay_opacity * 100)}%"
        self.message_ticks = 90

    def _apply_window_mode(self) -> None:
        window_w = WINDOW_W
        window_h = WINDOW_H
        x = (self.screen_w - window_w) // 2
        y = (self.screen_h - window_h) // 2
        self.window.resizable = False
        self.window.size = (window_w, window_h)
        if self.overlay_mode:
            y = self.screen_h - window_h - OVERLAY_MARGIN
            self.window.borderless = True
            self.window.always_on_top = True
            self.window.opacity = self.overlay_opacity
        else:
            self.window.borderless = False
            self.window.always_on_top = False
            self.window.opacity = 1.0
        self.window.position = (x, max(40, y))

    def _update(self) -> None:
        self.player_anim += 0.22
        if self.message_ticks > 0:
            self.message_ticks -= 1
        if self.invuln_ticks > 0:
            self.invuln_ticks -= 1
        if self.jump_buffer > 0:
            self.jump_buffer -= 1

        keys = pygame.key.get_pressed()
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        run = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        if self.level_complete:
            self.camera_x += (max(0, WORLD_WIDTH - WINDOW_W) - self.camera_x) * 0.08
            return

        accel = 0.85 if self.on_ground else 0.45
        max_speed = 7.4 if run else 4.8
        target_vx = 0.0
        if left:
            target_vx -= max_speed
        if right:
            target_vx += max_speed
        self.player_vx += (target_vx - self.player_vx) * accel * 0.18
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
            self.audio.play("jump")
            self._burst(self.player.x + self.player.w / 2, self.player.y + self.player.h, (255, 242, 191), 6)

        self.player.x += self.player_vx
        self._resolve_horizontal()

        was_grounded = self.on_ground
        self.player_vy = clamp(self.player_vy + GRAVITY, -20, MAX_FALL)
        self.player.y += self.player_vy
        self.on_ground = False
        self._resolve_vertical()
        self.coyote_frames = 6 if self.on_ground else max(0, self.coyote_frames - 1)
        if self.on_ground and not was_grounded:
            self._burst(self.player.x + self.player.w / 2, self.player.y + self.player.h, (247, 223, 156), 4)

        if self.player.y > WINDOW_H + 80:
            self.player.x = 96
            self.player.y = GROUND_Y - PLAYER_H
            self.player_vx = 0
            self.player_vy = 0
            self.message = "Watch the gaps."
            self.message_ticks = 100
            self.audio.play("hit")

        target_camera = clamp(self.player.x - WINDOW_W * 0.35, 0, max(0, WORLD_WIDTH - WINDOW_W))
        self.camera_x += (target_camera - self.camera_x) * 0.12

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

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            enemy.frame += 0.18
            enemy.x += enemy.vx
            if enemy.x <= enemy.left_bound or enemy.x + enemy.w >= enemy.right_bound:
                enemy.vx *= -1
            if self._rects_overlap(self.player, enemy):
                stomp = self.player_vy > 1.5 and self.player.y + self.player.h - 6 <= enemy.y + 10
                if stomp:
                    enemy.alive = False
                    self.player_vy = -7.8
                    self.score += 250
                    self.best_score = max(self.best_score, self.score)
                    self.message = "stomp +250"
                    self.message_ticks = 40
                    self.audio.play("stomp")
                    self._burst(enemy.x + enemy.w / 2, enemy.y + enemy.h / 2, (142, 90, 47), 10)
                elif self.invuln_ticks == 0:
                    self.invuln_ticks = 90
                    self.player.x = max(40, self.player.x - 70)
                    self.player_vx = -4 * self.facing
                    self.message = "Ouch."
                    self.message_ticks = 50
                    self.audio.play("hit")

        for particle in list(self.particles):
            particle.x += particle.vx
            particle.y += particle.vy
            particle.vy += 0.24
            particle.ttl -= 1
            if particle.ttl <= 0:
                self.particles.remove(particle)

        if self.player.x > WORLD_WIDTH - 150:
            self.level_complete = True
            self.message = "Desktop saved. Nice run."
            self.message_ticks = 180
            self.audio.play("win")
            self.best_score = max(self.best_score, self.score)

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

    def _circle_hits_player(self, x: float, y: float, radius: float) -> bool:
        nearest_x = max(self.player.x, min(x, self.player.x + self.player.w))
        nearest_y = max(self.player.y, min(y, self.player.y + self.player.h))
        dx = x - nearest_x
        dy = y - nearest_y
        return dx * dx + dy * dy <= radius * radius

    def _rects_overlap(self, a: RectEntity, b: RectEntity) -> bool:
        return a.x < b.x + b.w and a.x + a.w > b.x and a.y < b.y + b.h and a.y + a.h > b.y

    def _burst(self, x: float, y: float, color: tuple[int, int, int], count: int) -> None:
        for _ in range(count):
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=random.uniform(-2.8, 2.8),
                    vy=random.uniform(-4.6, -1.4),
                    ttl=random.randint(18, 32),
                    color=color,
                    size=random.randint(3, 6),
                )
            )

    def _draw(self) -> None:
        self.screen.fill((120, 201, 255))
        self._draw_background()
        self._draw_world()
        self._draw_particles()
        self._draw_ui()
        pygame.display.flip()

    def _draw_background(self) -> None:
        pygame.draw.rect(self.screen, (188, 230, 255), (0, 0, WINDOW_W, 44))
        for idx in range(5):
            cloud_x = ((idx * 320) - (self.camera_x * (0.12 + idx * 0.01))) % (WINDOW_W + 180) - 90
            cloud_y = 46 + (idx % 2) * 24
            self._draw_cloud(cloud_x, cloud_y)
        for idx, color in enumerate(((184, 216, 162), (146, 191, 116), (110, 162, 84))):
            parallax = 0.18 + idx * 0.07
            base_y = 224 + idx * 28
            points = [(0, WINDOW_H)]
            for x in range(-120, WINDOW_W + 121, 120):
                world_x = x + self.camera_x * parallax
                height = 28 + (math.sin(world_x / 130) + 1) * 24 + idx * 8
                points.append((x, base_y - height))
            points.append((WINDOW_W, WINDOW_H))
            pygame.draw.polygon(self.screen, color, points)

    def _draw_cloud(self, x: float, y: float) -> None:
        for dx, dy, r in [(0, 8, 22), (24, 0, 24), (52, 10, 18), (78, 8, 14)]:
            pygame.draw.circle(self.screen, (255, 255, 255), (int(x + dx + r), int(y + dy + r)), r)

    def _draw_world(self) -> None:
        for plat in self.platforms:
            if plat.y >= GROUND_Y:
                self._draw_ground(plat)
            else:
                self._draw_block(plat)

        for coin in self.coins:
            if coin.collected:
                continue
            wobble = math.sin(coin.phase) * 2
            x = int(coin.x - self.camera_x)
            y = int(coin.y + wobble)
            pygame.draw.circle(self.screen, (242, 194, 48), (x, y), 12)
            pygame.draw.circle(self.screen, (156, 112, 0), (x, y), 12, 3)

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            x = int(enemy.x - self.camera_x)
            y = int(enemy.y)
            pygame.draw.ellipse(self.screen, (139, 76, 32), (x, y + 8, enemy.w, enemy.h - 8))
            pygame.draw.rect(self.screen, (90, 44, 15), (x + 4, y + 2, enemy.w - 8, 12))
            eye_offset = 6 if enemy.vx > 0 else 1
            pygame.draw.circle(self.screen, (255, 255, 255), (x + eye_offset + 8, y + 15), 2)
            pygame.draw.circle(self.screen, (255, 255, 255), (x + eye_offset + 16, y + 15), 2)

        if not (self.invuln_ticks > 0 and self.invuln_ticks % 8 < 4):
            self._draw_player()

        flag_x = int(WORLD_WIDTH - self.camera_x - 90)
        pygame.draw.rect(self.screen, (236, 236, 236), (flag_x, 70, 6, GROUND_Y - 70))
        pygame.draw.polygon(self.screen, (241, 74, 55), [(flag_x + 6, 84), (flag_x + 52, 96), (flag_x + 6, 110)])

    def _draw_ground(self, plat: RectEntity) -> None:
        x = int(plat.x - self.camera_x)
        pygame.draw.rect(self.screen, (156, 107, 48), (x, int(plat.y), int(plat.w), int(plat.h)))
        pygame.draw.rect(self.screen, (101, 181, 75), (x, int(plat.y), int(plat.w), 18))
        for line_x in range(x, x + int(plat.w), 26):
            pygame.draw.line(self.screen, (122, 75, 30), (line_x, int(plat.y) + 18), (line_x + 10, int(plat.y + plat.h)), 2)

    def _draw_block(self, plat: RectEntity) -> None:
        x = int(plat.x - self.camera_x)
        color = (194, 120, 28) if (plat.x, plat.y) in self.question_blocks else (123, 84, 37)
        border = (249, 199, 54) if (plat.x, plat.y) in self.question_blocks else (214, 176, 111)
        pygame.draw.rect(self.screen, color, (x, int(plat.y), int(plat.w), int(plat.h)))
        pygame.draw.rect(self.screen, border, (x, int(plat.y), int(plat.w), int(plat.h)), 3)

    def _draw_player(self) -> None:
        x = int(self.player.x - self.camera_x)
        y = int(self.player.y)
        pygame.draw.rect(self.screen, (37, 84, 199), (x + 6, y + 16, self.player.w - 12, self.player.h - 16))
        pygame.draw.rect(self.screen, (215, 75, 57), (x + 4, y + 8, self.player.w - 8, 12))
        pygame.draw.rect(self.screen, (241, 200, 155), (x + 7, y + 18, self.player.w - 14, 12))
        pygame.draw.rect(self.screen, (140, 43, 24), (x + 3, y + 2, self.player.w - 6, 8))
        pygame.draw.rect(self.screen, (215, 75, 57), (x + 1, y + 10, self.player.w - 2, 4))
        pygame.draw.circle(self.screen, (0, 0, 0), (x + 12, y + 23), 2)
        pygame.draw.circle(self.screen, (0, 0, 0), (x + self.player.w - 12, y + 23), 2)

    def _draw_particles(self) -> None:
        for particle in self.particles:
            pygame.draw.rect(
                self.screen,
                particle.color,
                (int(particle.x - self.camera_x), int(particle.y), particle.size, particle.size),
            )

    def _draw_ui(self) -> None:
        pygame.draw.rect(self.screen, (14, 20, 32), (24, 20, 360, 100), border_radius=14)
        score_label = self.font.render(f"Score {self.score}", True, (255, 255, 255))
        best_label = self.small_font.render(f"Best {self.best_score}    Esc quit    R reset", True, (247, 213, 109))
        controls = self.small_font.render("Arrows move, Space jumps, Shift runs, F10/O overlay", True, (201, 231, 255))
        self.screen.blit(score_label, (42, 34))
        self.screen.blit(best_label, (42, 68))
        self.screen.blit(controls, (42, 88))

        mode_label = "overlay mode" if self.overlay_mode else "window mode"
        badge = self.small_font.render(
            f"pygame {mode_label}  |  Ctrl+Alt+O  |  {'audio on' if HAS_AUDIO else 'audio off'}",
            True,
            (216, 239, 255),
        )
        pygame.draw.rect(self.screen, (22, 35, 53), (WINDOW_W - 294, 24, 270, 40), border_radius=10)
        self.screen.blit(badge, (WINDOW_W - 278, 36))
        integration = self.small_font.render(self.integration_status, True, (255, 241, 171))
        detail = self.small_font.render(self.integration_detail[:44], True, (201, 231, 255))
        self.screen.blit(integration, (WINDOW_W - 278, 78))
        self.screen.blit(detail, (WINDOW_W - 278, 96))

        if self.message_ticks > 0:
            text = self.big_font.render(self.message, True, (255, 255, 255))
            self.screen.blit(text, (WINDOW_W // 2 - text.get_width() // 2, 28))


if __name__ == "__main__":
    DesktopMarioMac().run()
