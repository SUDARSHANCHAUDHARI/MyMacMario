import math
import queue
import random
import threading
import tkinter as tk
from array import array
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageOps, ImageTk
from pynput import keyboard
import pystray

try:
    import simpleaudio as sa

    HAS_AUDIO = True
except Exception:
    HAS_AUDIO = False

try:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

    HAS_APPKIT = True
except Exception:
    HAS_APPKIT = False


WORLD_WIDTH = 3300
PLAYFIELD_HEIGHT = 360
GROUND_Y = 260
GRAVITY = 0.5
MAX_FALL = 13.5
PLAYER_W = 32
PLAYER_H = 42


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
    vx: float = -1.1
    alive: bool = True
    frame: float = 0.0


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    ttl: int
    color: str
    size: int


class AudioEngine:
    def __init__(self) -> None:
        self.enabled = HAS_AUDIO
        self.sample_rate = 22050
        self.sound_map = {
            "jump": [(600, 0.05), (760, 0.05)],
            "coin": [(900, 0.04), (1200, 0.06)],
            "stomp": [(210, 0.06), (180, 0.06)],
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
                wobble = math.sin(2 * math.pi * freq * t) + 0.35 * math.sin(2 * math.pi * (freq * 2) * t)
                samples.append(int(16000 * wobble * envelope))
        sa.play_buffer(samples.tobytes(), 1, 2, self.sample_rate)


class SpriteBank:
    COLORS = {
        ".": (0, 0, 0, 0),
        "R": (214, 69, 44, 255),
        "B": (45, 91, 214, 255),
        "S": (245, 201, 163, 255),
        "H": (115, 43, 24, 255),
        "Y": (249, 199, 54, 255),
        "O": (194, 120, 28, 255),
        "K": (34, 25, 25, 255),
        "W": (255, 255, 255, 255),
        "G": (88, 174, 82, 255),
        "D": (61, 119, 36, 255),
        "L": (255, 234, 142, 255),
        "N": (123, 84, 37, 255),
    }

    def __init__(self) -> None:
        self.scale = 4
        self.player_right = {
            "idle": self._make_image(
                [
                    "..HHHH..",
                    ".HRRRRH.",
                    ".HRRRRRH",
                    "..SSSS..",
                    ".SSSSSR.",
                    "..BBBB..",
                    ".BBBBBB.",
                    ".BB..BB.",
                    "SS....SS",
                    "S......S",
                ]
            ),
            "run1": self._make_image(
                [
                    "..HHHH..",
                    ".HRRRRH.",
                    ".HRRRRRH",
                    "..SSSS..",
                    ".SSSSSR.",
                    "..BBBB..",
                    ".BBBBBB.",
                    "BB...BB.",
                    "S....SS.",
                    ".....S..",
                ]
            ),
            "run2": self._make_image(
                [
                    "..HHHH..",
                    ".HRRRRH.",
                    ".HRRRRRH",
                    "..SSSS..",
                    ".SSSSSR.",
                    "..BBBB..",
                    ".BBBBBB.",
                    ".BB...BB",
                    ".SS....S",
                    "..S.....",
                ]
            ),
            "jump": self._make_image(
                [
                    "..HHHH..",
                    ".HRRRRH.",
                    ".HRRRRRH",
                    "..SSSS..",
                    ".SSSSSR.",
                    "..BBBB..",
                    ".BBBBBB.",
                    "..BB.B..",
                    ".SS..SS.",
                    "S......S",
                ]
            ),
        }
        self.enemy = [
            self._make_image(
                [
                    "..NNNN..",
                    ".NNNNNN.",
                    "NNWWWWNN",
                    "NNNNNNNN",
                    ".NN..NN.",
                    "N......N",
                ]
            ),
            self._make_image(
                [
                    "..NNNN..",
                    ".NNNNNN.",
                    "NNWWWWNN",
                    "NNNNNNNN",
                    "N.N..N.N",
                    ".N....N.",
                ]
            ),
        ]
        self.coin = [
            self._make_image(
                [
                    "...YY...",
                    "..YLLY..",
                    ".YLLLLY.",
                    ".YLYLLY.",
                    ".YLLLLY.",
                    "..YLLY..",
                    "...YY...",
                ]
            ),
            self._make_image(
                [
                    "...YY...",
                    "...LL...",
                    "..YLLY..",
                    "..YLLY..",
                    "..YLLY..",
                    "...LL...",
                    "...YY...",
                ]
            ),
        ]
        self.block = self._make_image(
            [
                "OOOOOOOO",
                "OYYYYYYO",
                "OYOOOOYO",
                "OYOYYOYO",
                "OYOOOOYO",
                "OYYYYYYO",
                "OOOOOOOO",
                "OO....OO",
            ]
        )
        self.brick = self._make_image(
            [
                "NNNNNNNN",
                "NLLLLLLN",
                "NNNNNNNN",
                "NLLLLLLN",
                "NNNNNNNN",
                "NLLLLLLN",
                "NNNNNNNN",
                "NLLLLLLN",
            ]
        )

    def _make_image(self, rows: list[str]) -> Image.Image:
        width = len(rows[0])
        height = len(rows)
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                img.putpixel((x, y), self.COLORS[cell])
        return img.resize((width * self.scale, height * self.scale), Image.Resampling.NEAREST)

    def frame(self, image: Image.Image) -> ImageTk.PhotoImage:
        return ImageTk.PhotoImage(image)

    def player(self, pose: str, facing: int) -> ImageTk.PhotoImage:
        img = self.player_right[pose]
        if facing < 0:
            img = ImageOps.mirror(img)
        return self.frame(img)

    def enemy_frame(self, index: int, facing: int) -> ImageTk.PhotoImage:
        img = self.enemy[index % len(self.enemy)]
        if facing > 0:
            img = ImageOps.mirror(img)
        return self.frame(img)

    def coin_frame(self, index: int) -> ImageTk.PhotoImage:
        return self.frame(self.coin[index % len(self.coin)])

    def block_frame(self) -> ImageTk.PhotoImage:
        return self.frame(self.block)

    def brick_frame(self) -> ImageTk.PhotoImage:
        return self.frame(self.brick)


class DesktopMarioMac:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Desktop Mario Mac")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="systemTransparent")
        self.root.wm_attributes("-transparent", True)

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.playfield_top = self.screen_h - PLAYFIELD_HEIGHT
        self.root.geometry(f"{self.screen_w}x{self.screen_h}+0+0")

        self.canvas = tk.Canvas(
            self.root,
            width=self.screen_w,
            height=self.screen_h,
            bg="systemTransparent",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.command_queue: queue.Queue[str] = queue.Queue()
        self.running = True
        self.visible = False
        self.camera_x = 0.0
        self.camera_target_x = 0.0
        self.score = 0
        self.best_score = 0
        self.message = "Press Ctrl+Alt+M to play on your desktop"
        self.message_ticks = 240
        self.level_complete = False

        self.left_pressed = False
        self.right_pressed = False
        self.run_pressed = False
        self.jump_pressed = False
        self.jump_buffer = 0
        self.coyote_frames = 0
        self.invuln_ticks = 0

        self.audio = AudioEngine()
        self.sprites = SpriteBank()
        self._setup_native_mac()
        self._load_world()

        self._bind_keys()
        self._start_hotkey_listener()
        self._start_tray()

        self.hide()
        self.root.after(16, self._tick)
        self.root.after(50, self._drain_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _setup_native_mac(self) -> None:
        if not HAS_APPKIT:
            return
        try:
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception:
            pass
        try:
            self.root.createcommand("tk::mac::Quit", self.quit)
        except Exception:
            pass

    def _load_world(self) -> None:
        self.platforms = [
            RectEntity(0, GROUND_Y, 820, 100),
            RectEntity(920, GROUND_Y, 420, 100),
            RectEntity(1430, GROUND_Y, 260, 100),
            RectEntity(1760, GROUND_Y, 520, 100),
            RectEntity(2340, GROUND_Y, 300, 100),
            RectEntity(2720, GROUND_Y, 360, 100),
            RectEntity(450, 198, 70, 26),
            RectEntity(520, 198, 70, 26),
            RectEntity(1050, 172, 70, 26),
            RectEntity(1120, 172, 70, 26),
            RectEntity(1190, 172, 70, 26),
            RectEntity(1890, 180, 70, 26),
            RectEntity(1960, 180, 70, 26),
            RectEntity(2030, 180, 70, 26),
            RectEntity(2550, 150, 70, 26),
            RectEntity(2620, 150, 70, 26),
        ]
        self.question_blocks = {(520, 198), (1120, 172), (1960, 180), (2550, 150)}
        self.coins = [
            Coin(x, y, phase=random.random() * math.tau)
            for x, y in [
                (470, 150),
                (540, 150),
                (1070, 126),
                (1140, 126),
                (1210, 126),
                (1910, 134),
                (1980, 134),
                (2050, 134),
                (1480, 218),
                (1540, 218),
                (1820, 218),
                (2570, 106),
                (2640, 106),
            ]
        ]
        self.enemies = [
            Enemy(680, GROUND_Y - 26, 28, 26, 620, 790),
            Enemy(1490, GROUND_Y - 26, 28, 26, 1450, 1650),
            Enemy(1840, GROUND_Y - 26, 28, 26, 1780, 2240),
            Enemy(2760, GROUND_Y - 26, 28, 26, 2740, 3040),
        ]
        self.particles: list[Particle] = []
        self.player = RectEntity(96, GROUND_Y - PLAYER_H, PLAYER_W, PLAYER_H)
        self.player_vx = 0.0
        self.player_vy = 0.0
        self.player_anim = 0.0
        self.on_ground = True
        self.facing = 1

    def _bind_keys(self) -> None:
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.bind("<Escape>", lambda _event: self.hide())

    def _start_hotkey_listener(self) -> None:
        def run_listener() -> None:
            listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+m": self._queue_toggle})
            listener.run()

        threading.Thread(target=run_listener, daemon=True).start()

    def _start_tray(self) -> None:
        def run_tray() -> None:
            menu = pystray.Menu(
                pystray.MenuItem("Show / Hide", lambda: self._queue_toggle()),
                pystray.MenuItem("Reset Run", lambda: self.command_queue.put("reset")),
                pystray.MenuItem("Quit", lambda: self.command_queue.put("quit")),
            )
            self.icon = pystray.Icon(
                "desktop-mario-mac",
                self._tray_image(),
                "Desktop Mario Mac",
                menu,
            )
            self.icon.run()

        threading.Thread(target=run_tray, daemon=True).start()

    def _tray_image(self) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((8, 8, 56, 56), radius=14, fill=(220, 79, 56, 255))
        draw.rectangle((17, 14, 47, 25), fill=(110, 45, 23, 255))
        draw.rectangle((20, 24, 44, 34), fill=(250, 206, 170, 255))
        draw.rectangle((18, 35, 46, 53), fill=(48, 98, 214, 255))
        draw.rectangle((27, 29, 37, 34), fill=(250, 206, 170, 255))
        return img

    def _queue_toggle(self) -> None:
        self.command_queue.put("toggle")

    def _drain_queue(self) -> None:
        while not self.command_queue.empty():
            command = self.command_queue.get_nowait()
            if command == "toggle":
                self.show() if not self.visible else self.hide()
            elif command == "reset":
                self.reset_level()
            elif command == "quit":
                self.quit()
                return
        self.root.after(50, self._drain_queue)

    def _on_key_press(self, event: tk.Event) -> None:
        if event.keysym in ("Left", "a", "A"):
            self.left_pressed = True
        elif event.keysym in ("Right", "d", "D"):
            self.right_pressed = True
        elif event.keysym in ("Shift_L", "Shift_R"):
            self.run_pressed = True
        elif event.keysym == "space":
            self.jump_pressed = True
            self.jump_buffer = 8

    def _on_key_release(self, event: tk.Event) -> None:
        if event.keysym in ("Left", "a", "A"):
            self.left_pressed = False
        elif event.keysym in ("Right", "d", "D"):
            self.right_pressed = False
        elif event.keysym in ("Shift_L", "Shift_R"):
            self.run_pressed = False
        elif event.keysym == "space":
            self.jump_pressed = False
            if self.player_vy < -4.5:
                self.player_vy *= 0.58

    def reset_level(self) -> None:
        self._load_world()
        self.camera_x = 0.0
        self.camera_target_x = 0.0
        self.score = 0
        self.level_complete = False
        self.message = "Fresh run."
        self.message_ticks = 100

    def show(self) -> None:
        self.visible = True
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.message = "Desktop Mario ready"
        self.message_ticks = 80

    def hide(self) -> None:
        self.visible = False
        self.root.withdraw()

    def quit(self) -> None:
        self.running = False
        try:
            if hasattr(self, "icon"):
                self.icon.stop()
        except Exception:
            pass
        self.root.quit()
        self.root.destroy()

    def _tick(self) -> None:
        if not self.running:
            return
        if self.visible:
            self._update()
            self._draw()
        self.root.after(16, self._tick)

    def _update(self) -> None:
        self.player_anim += 0.22
        if self.message_ticks > 0:
            self.message_ticks -= 1
        if self.invuln_ticks > 0:
            self.invuln_ticks -= 1
        if self.jump_buffer > 0:
            self.jump_buffer -= 1
        if self.level_complete:
            self.camera_target_x = max(0, WORLD_WIDTH - self.screen_w)
            self.camera_x += (self.camera_target_x - self.camera_x) * 0.08
            return

        accel = 0.85 if self.on_ground else 0.45
        max_speed = 7.4 if self.run_pressed else 4.8
        target_vx = 0.0
        if self.left_pressed:
            target_vx -= max_speed
        if self.right_pressed:
            target_vx += max_speed
        self.player_vx += (target_vx - self.player_vx) * accel * 0.18
        if abs(target_vx) < 0.1:
            self.player_vx *= 0.78 if self.on_ground else 0.96
        if abs(self.player_vx) < 0.05:
            self.player_vx = 0.0
        if self.player_vx != 0:
            self.facing = 1 if self.player_vx > 0 else -1

        if (self.on_ground or self.coyote_frames > 0) and self.jump_buffer > 0:
            self.player_vy = -11.9 if self.run_pressed else -11.0
            self.on_ground = False
            self.coyote_frames = 0
            self.jump_buffer = 0
            self.audio.play("jump")
            self._burst(self.player.x + self.player.w / 2, self.player.y + self.player.h, "#fff2bf", 5)

        self.player.x += self.player_vx
        self._resolve_horizontal()

        self.player_vy = clamp(self.player_vy + GRAVITY, -20, MAX_FALL)
        self.player.y += self.player_vy
        was_grounded = self.on_ground
        self.on_ground = False
        self._resolve_vertical()
        self.coyote_frames = 6 if self.on_ground else max(0, self.coyote_frames - 1)
        if self.on_ground and not was_grounded:
            self._burst(self.player.x + self.player.w / 2, self.player.y + self.player.h, "#f7df9c", 4)

        if self.player.y > PLAYFIELD_HEIGHT + 40:
            self.player.x = 96
            self.player.y = GROUND_Y - PLAYER_H
            self.player_vx = 0
            self.player_vy = 0
            self.camera_target_x = max(0, self.player.x - self.screen_w * 0.35)
            self.message = "Watch the gaps."
            self.message_ticks = 110
            self.audio.play("hit")

        self.camera_target_x = clamp(self.player.x - self.screen_w * 0.35, 0, max(0, WORLD_WIDTH - self.screen_w))
        self.camera_x += (self.camera_target_x - self.camera_x) * 0.12

        for coin in self.coins:
            coin.phase += 0.2
            if coin.collected:
                continue
            if self._circle_hits_player(coin.x, coin.y, 12):
                coin.collected = True
                self.score += 100
                self.best_score = max(self.best_score, self.score)
                self.message = "+100"
                self.message_ticks = 28
                self.audio.play("coin")
                self._burst(coin.x, coin.y, "#f7c73a", 8)

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
                    self.message_ticks = 48
                    self.audio.play("stomp")
                    self._burst(enemy.x + enemy.w / 2, enemy.y + enemy.h / 2, "#8e5a2f", 10)
                elif self.invuln_ticks == 0:
                    self.invuln_ticks = 90
                    self.player.x = max(40, self.player.x - 70)
                    self.player_vx = -4 * self.facing
                    self.message = "Ouch."
                    self.message_ticks = 60
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
            self.message_ticks = 220
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
                    if (plat.x, plat.y) in self.question_blocks:
                        self.message = "Bonk."
                        self.message_ticks = 20

    def _circle_hits_player(self, x: float, y: float, radius: float) -> bool:
        nearest_x = max(self.player.x, min(x, self.player.x + self.player.w))
        nearest_y = max(self.player.y, min(y, self.player.y + self.player.h))
        dx = x - nearest_x
        dy = y - nearest_y
        return dx * dx + dy * dy <= radius * radius

    def _rects_overlap(self, a: RectEntity, b: RectEntity) -> bool:
        return a.x < b.x + b.w and a.x + a.w > b.x and a.y < b.y + b.h and a.y + a.h > b.y

    def _burst(self, x: float, y: float, color: str, count: int) -> None:
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
        self.canvas.delete("all")
        self.canvas.image = []
        self._draw_environment()
        self._draw_world()
        self._draw_particles()
        self._draw_overlay_ui()

    def _draw_environment(self) -> None:
        horizon = self.playfield_top
        self.canvas.create_rectangle(
            0,
            horizon,
            self.screen_w,
            self.screen_h,
            fill="#78c9ff",
            outline="",
        )
        self.canvas.create_rectangle(
            0,
            horizon,
            self.screen_w,
            horizon + 40,
            fill="#bce6ff",
            outline="",
        )
        for idx in range(5):
            cloud_x = ((idx * 320) - (self.camera_x * (0.12 + idx * 0.01))) % (self.screen_w + 160) - 80
            cloud_y = horizon + 40 + (idx % 2) * 28
            self._draw_cloud(cloud_x, cloud_y)
        for idx, color in enumerate(("#b8d8a2", "#92bf74", "#6ea254")):
            parallax = 0.18 + idx * 0.07
            base_y = horizon + 180 + idx * 26
            points = []
            for x in range(-120, self.screen_w + 121, 120):
                world_x = x + self.camera_x * parallax
                height = 28 + (math.sin(world_x / 130) + 1) * 24 + idx * 8
                points.extend([x, base_y - height])
            polygon = [0, self.screen_h, 0, base_y] + points + [self.screen_w, self.screen_h]
            self.canvas.create_polygon(polygon, fill=color, outline="")

    def _draw_cloud(self, x: float, y: float) -> None:
        for dx, dy, r in [(0, 8, 22), (24, 0, 24), (52, 10, 18), (78, 8, 14)]:
            self.canvas.create_oval(x + dx, y + dy, x + dx + r * 2, y + dy + r * 2, fill="white", outline="")

    def _draw_world(self) -> None:
        for plat in self.platforms:
            if plat.y >= GROUND_Y:
                self._draw_ground(plat)
            else:
                self._draw_block_platform(plat)

        for coin in self.coins:
            if coin.collected:
                continue
            frame = 0 if math.sin(coin.phase) > 0 else 1
            img = self.sprites.coin_frame(frame)
            self.canvas.create_image(coin.x - self.camera_x, self.playfield_top + coin.y, image=img)
            self.canvas.image.append(img)

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            img = self.sprites.enemy_frame(int(enemy.frame) % 2, 1 if enemy.vx > 0 else -1)
            self.canvas.create_image(enemy.x - self.camera_x + enemy.w / 2, self.playfield_top + enemy.y + enemy.h / 2, image=img)
            self.canvas.image.append(img)

        pose = "jump"
        if self.on_ground and abs(self.player_vx) < 0.6:
            pose = "idle"
        elif self.on_ground:
            pose = "run1" if int(self.player_anim) % 2 == 0 else "run2"
        player_img = self.sprites.player(pose, self.facing)
        if not (self.invuln_ticks > 0 and self.invuln_ticks % 8 < 4):
            self.canvas.create_image(
                self.player.x - self.camera_x + self.player.w / 2,
                self.playfield_top + self.player.y + self.player.h / 2,
                image=player_img,
            )
        self.canvas.image.append(player_img)

        flag_x = WORLD_WIDTH - self.camera_x - 90
        pole_top = self.playfield_top + 70
        pole_bottom = self.playfield_top + GROUND_Y
        self.canvas.create_rectangle(flag_x, pole_top, flag_x + 6, pole_bottom, fill="#ececec", outline="")
        self.canvas.create_polygon(
            flag_x + 6,
            pole_top + 8,
            flag_x + 52,
            pole_top + 22,
            flag_x + 6,
            pole_top + 36,
            fill="#f14a37",
            outline="",
        )

    def _draw_ground(self, plat: RectEntity) -> None:
        x1 = plat.x - self.camera_x
        y1 = self.playfield_top + plat.y
        x2 = x1 + plat.w
        y2 = y1 + plat.h
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#9c6b30", outline="#5f3f15", width=2)
        self.canvas.create_rectangle(x1, y1, x2, y1 + 18, fill="#65b54b", outline="")
        for x in range(int(x1), int(x2), 26):
            self.canvas.create_line(x, y1 + 18, x + 10, y2, fill="#7a4b1e", width=2)

    def _draw_block_platform(self, plat: RectEntity) -> None:
        tile_size = 32
        frame = self.sprites.block_frame() if (plat.x, plat.y) in self.question_blocks else self.sprites.brick_frame()
        self.canvas.image = getattr(self.canvas, "image", [])
        for x in range(int(plat.x), int(plat.x + plat.w), tile_size):
            self.canvas.create_image(x - self.camera_x + tile_size / 2, self.playfield_top + plat.y + tile_size / 2, image=frame)
        self.canvas.image.append(frame)

    def _draw_particles(self) -> None:
        for particle in self.particles:
            x = particle.x - self.camera_x
            y = self.playfield_top + particle.y
            self.canvas.create_rectangle(
                x,
                y,
                x + particle.size,
                y + particle.size,
                fill=particle.color,
                outline="",
            )

    def _draw_overlay_ui(self) -> None:
        panel_x = 24
        panel_y = 24
        panel_w = 360
        panel_h = 96
        self.canvas.create_rectangle(panel_x, panel_y, panel_x + panel_w, panel_y + panel_h, fill="#0e1420", outline="", stipple="gray50")
        self.canvas.create_text(panel_x + 18, panel_y + 18, anchor="nw", text=f"Score {self.score}", fill="#ffffff", font=("Menlo", 20, "bold"))
        self.canvas.create_text(
            panel_x + 18,
            panel_y + 48,
            anchor="nw",
            text=f"Best {self.best_score}    Ctrl+Alt+M toggle    Esc hide",
            fill="#f7d56d",
            font=("Menlo", 11),
        )
        self.canvas.create_text(
            panel_x + 18,
            panel_y + 68,
            anchor="nw",
            text="Arrows move, Space jumps, Shift runs",
            fill="#c9e7ff",
            font=("Menlo", 11),
        )
        if self.message_ticks > 0:
            self.canvas.create_text(
                self.screen_w // 2,
                46,
                text=self.message,
                fill="#ffffff",
                font=("Menlo", 17, "bold"),
            )

        badge = "native mac mode" if HAS_APPKIT else "tk overlay mode"
        sound = "audio on" if HAS_AUDIO else "audio off"
        badge_text = f"{badge}  |  {sound}"
        self.canvas.create_rectangle(self.screen_w - 280, 24, self.screen_w - 24, 62, fill="#162335", outline="", stipple="gray50")
        self.canvas.create_text(self.screen_w - 152, 43, text=badge_text, fill="#d8efff", font=("Menlo", 10))

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DesktopMarioMac().run()
