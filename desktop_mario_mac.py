import math
import queue
import random
import threading
import tkinter as tk
from dataclasses import dataclass

from PIL import Image, ImageDraw
from pynput import keyboard
import pystray


GRAVITY = 0.55
WALK_SPEED = 4.2
RUN_SPEED = 6.4
JUMP_SPEED = -11.5
PLAYER_W = 28
PLAYER_H = 38
GAME_HEIGHT = 320
GROUND_Y = 250


@dataclass
class RectEntity:
    x: float
    y: float
    w: float
    h: float


@dataclass
class Enemy:
    x: float
    y: float
    w: float
    h: float
    left_bound: float
    right_bound: float
    vx: float = -1.25
    alive: bool = True


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
        self.focused = False
        self.camera_x = 0.0
        self.score = 0
        self.message = "Press Ctrl+Alt+M to jump in"
        self.message_ticks = 240

        self.left_pressed = False
        self.right_pressed = False
        self.run_pressed = False

        self.platforms = self._build_platforms()
        self.coins = self._build_coins()
        self.enemies = self._build_enemies()
        self.player = RectEntity(80, GROUND_Y - PLAYER_H, PLAYER_W, PLAYER_H)
        self.player_vx = 0.0
        self.player_vy = 0.0
        self.on_ground = True
        self.facing = 1

        self._bind_keys()
        self._start_hotkey_listener()
        self._start_tray()

        self.hide()
        self.root.after(16, self._tick)
        self.root.after(50, self._drain_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    def _build_platforms(self) -> list[RectEntity]:
        return [
            RectEntity(0, GROUND_Y, 820, 70),
            RectEntity(920, GROUND_Y, 260, 70),
            RectEntity(1260, GROUND_Y, 210, 70),
            RectEntity(1590, GROUND_Y, 420, 70),
            RectEntity(2080, GROUND_Y, 250, 70),
            RectEntity(470, 180, 80, 22),
            RectEntity(550, 180, 80, 22),
            RectEntity(1030, 160, 80, 22),
            RectEntity(1115, 160, 80, 22),
            RectEntity(1770, 190, 80, 22),
            RectEntity(1855, 190, 80, 22),
            RectEntity(1940, 190, 80, 22),
        ]

    def _build_coins(self) -> list[dict]:
        coins = []
        for x, y in [
            (500, 140),
            (580, 140),
            (1050, 120),
            (1135, 120),
            (1790, 150),
            (1875, 150),
            (1960, 150),
            (1380, 210),
            (1440, 210),
            (1660, 210),
        ]:
            coins.append({"x": x, "y": y, "r": 10, "collected": False, "phase": random.random() * math.tau})
        return coins

    def _build_enemies(self) -> list[Enemy]:
        return [
            Enemy(660, GROUND_Y - 24, 28, 24, 620, 790),
            Enemy(1360, GROUND_Y - 24, 28, 24, 1300, 1440),
            Enemy(1695, GROUND_Y - 24, 28, 24, 1620, 1970),
        ]

    def _bind_keys(self) -> None:
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.bind("<Escape>", lambda _event: self.hide())
        self.root.bind("<FocusIn>", lambda _event: setattr(self, "focused", True))
        self.root.bind("<FocusOut>", lambda _event: setattr(self, "focused", False))

    def _start_hotkey_listener(self) -> None:
        def run_listener() -> None:
            listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+m": self._queue_toggle})
            listener.run()

        threading.Thread(target=run_listener, daemon=True).start()

    def _start_tray(self) -> None:
        def run_tray() -> None:
            image = self._tray_image()
            menu = pystray.Menu(
                pystray.MenuItem("Show / Hide", lambda: self._queue_toggle()),
                pystray.MenuItem("Reset Level", lambda: self.command_queue.put("reset")),
                pystray.MenuItem("Quit", lambda: self.command_queue.put("quit")),
            )
            self.icon = pystray.Icon("desktop-mario-mac", image, "Desktop Mario Mac", menu)
            self.icon.run()

        threading.Thread(target=run_tray, daemon=True).start()

    def _tray_image(self) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((10, 8, 54, 56), radius=10, fill=(212, 52, 39, 255))
        draw.rectangle((20, 18, 44, 32), fill=(255, 225, 190, 255))
        draw.rectangle((20, 34, 44, 50), fill=(42, 90, 220, 255))
        draw.rectangle((16, 14, 48, 22), fill=(125, 36, 18, 255))
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
            if self.on_ground:
                self.player_vy = JUMP_SPEED
                self.on_ground = False
                self.message = "Nice jump."
                self.message_ticks = 45

    def _on_key_release(self, event: tk.Event) -> None:
        if event.keysym in ("Left", "a", "A"):
            self.left_pressed = False
        elif event.keysym in ("Right", "d", "D"):
            self.right_pressed = False
        elif event.keysym in ("Shift_L", "Shift_R"):
            self.run_pressed = False

    def reset_level(self) -> None:
        self.player.x = 80
        self.player.y = GROUND_Y - PLAYER_H
        self.player_vx = 0.0
        self.player_vy = 0.0
        self.on_ground = True
        self.camera_x = 0.0
        self.score = 0
        for coin in self.coins:
            coin["collected"] = False
        for enemy in self.enemies:
            enemy.alive = True
            enemy.vx = -1.25
        self.message = "Level reset."
        self.message_ticks = 100

    def show(self) -> None:
        self.visible = True
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.message = "Desktop Mario ready"
        self.message_ticks = 90

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
        speed = RUN_SPEED if self.run_pressed else WALK_SPEED
        move = 0.0
        if self.left_pressed:
            move -= speed
        if self.right_pressed:
            move += speed
        self.player_vx = move
        if move != 0:
            self.facing = 1 if move > 0 else -1

        self.player.x += self.player_vx
        self._resolve_horizontal()

        self.player_vy += GRAVITY
        self.player.y += self.player_vy
        self.on_ground = False
        self._resolve_vertical()

        if self.player.y > self.screen_h:
            self.player.x = 80
            self.player.y = GROUND_Y - PLAYER_H
            self.player_vx = 0
            self.player_vy = 0
            self.message = "Watch the pits."
            self.message_ticks = 120

        level_width = 2400
        target_camera = self.player.x - self.screen_w * 0.35
        self.camera_x = max(0, min(target_camera, level_width - self.screen_w))

        for coin in self.coins:
            coin["phase"] += 0.18
            if not coin["collected"] and self._circle_hits_player(coin):
                coin["collected"] = True
                self.score += 100
                self.message = "+100 coin"
                self.message_ticks = 35

        for enemy in self.enemies:
            if not enemy.alive:
                continue
            enemy.x += enemy.vx
            if enemy.x <= enemy.left_bound or enemy.x + enemy.w >= enemy.right_bound:
                enemy.vx *= -1
            if self._rects_overlap(self.player, enemy):
                if self.player_vy > 1.5 and self.player.y + self.player.h - 6 <= enemy.y + 12:
                    enemy.alive = False
                    self.player_vy = -7.5
                    self.score += 250
                    self.message = "+250 stomp"
                    self.message_ticks = 50
                else:
                    self.player.x = max(40, self.player.x - 60)
                    self.player_vx = 0
                    self.message = "Ouch."
                    self.message_ticks = 60

        if self.message_ticks > 0:
            self.message_ticks -= 1

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
                if self.player_vy >= 0 and self.player.y + self.player.h - self.player_vy <= plat.y + 4:
                    self.player.y = plat.y - self.player.h
                    self.player_vy = 0
                    self.on_ground = True
                elif self.player_vy < 0:
                    self.player.y = plat.y + plat.h
                    self.player_vy = 0

    def _circle_hits_player(self, coin: dict) -> bool:
        nearest_x = max(self.player.x, min(coin["x"], self.player.x + self.player.w))
        nearest_y = max(self.player.y, min(coin["y"], self.player.y + self.player.h))
        dx = coin["x"] - nearest_x
        dy = coin["y"] - nearest_y
        return dx * dx + dy * dy <= coin["r"] * coin["r"]

    def _rects_overlap(self, a: RectEntity, b: RectEntity) -> bool:
        return (
            a.x < b.x + b.w
            and a.x + a.w > b.x
            and a.y < b.y + b.h
            and a.y + a.h > b.y
        )

    def _draw(self) -> None:
        self.canvas.delete("all")
        self._draw_overlay_ui()

        for plat in self.platforms:
            self._draw_platform(plat)
        for coin in self.coins:
            if not coin["collected"]:
                self._draw_coin(coin)
        for enemy in self.enemies:
            if enemy.alive:
                self._draw_enemy(enemy)
        self._draw_player()

    def _draw_overlay_ui(self) -> None:
        self.canvas.create_rectangle(
            18,
            18,
            310,
            92,
            fill="#111111",
            stipple="gray50",
            outline="",
        )
        self.canvas.create_text(
            34,
            34,
            anchor="nw",
            text=f"Score {self.score}",
            fill="#ffffff",
            font=("Menlo", 18, "bold"),
        )
        self.canvas.create_text(
            34,
            60,
            anchor="nw",
            text="Arrows move, Space jumps, Shift runs, Esc hides",
            fill="#f5d76e",
            font=("Menlo", 11),
        )
        if self.message_ticks > 0:
            self.canvas.create_text(
                self.screen_w // 2,
                46,
                text=self.message,
                fill="#ffffff",
                font=("Menlo", 16, "bold"),
            )

    def _draw_platform(self, plat: RectEntity) -> None:
        x1, y1, x2, y2 = self._world_to_screen(plat.x, plat.y, plat.x + plat.w, plat.y + plat.h)
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#7d4d22", outline="#4a2810", width=2)
        tile = 32
        for x in range(int(x1), int(x2), tile):
            self.canvas.create_line(x, y1, x + tile, y1, fill="#bc7b34", width=2)

    def _draw_coin(self, coin: dict) -> None:
        wobble = math.sin(coin["phase"]) * 2
        x = coin["x"] - self.camera_x
        y = coin["y"] + wobble
        r = coin["r"]
        self.canvas.create_oval(x - r, y - r, x + r, y + r, fill="#f2c230", outline="#9c7000", width=3)
        self.canvas.create_line(x, y - r + 3, x, y + r - 3, fill="#fff1a8", width=2)

    def _draw_enemy(self, enemy: Enemy) -> None:
        x1, y1, x2, y2 = self._world_to_screen(enemy.x, enemy.y, enemy.x + enemy.w, enemy.y + enemy.h)
        self.canvas.create_oval(x1, y1 + 8, x2, y2, fill="#8b4c20", outline="#53270c", width=2)
        self.canvas.create_rectangle(x1 + 5, y1 + 2, x2 - 5, y1 + 14, fill="#5a2c0f", outline="")
        eye_dx = 6 if enemy.vx > 0 else -2
        self.canvas.create_oval(x1 + 8 + eye_dx, y1 + 12, x1 + 12 + eye_dx, y1 + 16, fill="white", outline="")
        self.canvas.create_oval(x1 + 16 + eye_dx, y1 + 12, x1 + 20 + eye_dx, y1 + 16, fill="white", outline="")

    def _draw_player(self) -> None:
        x1, y1, x2, y2 = self._world_to_screen(
            self.player.x,
            self.player.y,
            self.player.x + self.player.w,
            self.player.y + self.player.h,
        )
        mid_x = (x1 + x2) / 2
        self.canvas.create_rectangle(x1 + 5, y1 + 14, x2 - 5, y2, fill="#2554c7", outline="")
        self.canvas.create_rectangle(x1 + 4, y1 + 8, x2 - 4, y1 + 20, fill="#d74b39", outline="")
        self.canvas.create_rectangle(x1 + 6, y1 + 18, x2 - 6, y1 + 28, fill="#f1c89b", outline="")
        self.canvas.create_rectangle(x1 + 3, y1 + 2, x2 - 3, y1 + 10, fill="#8c2b18", outline="")
        self.canvas.create_rectangle(x1 + 1, y1 + 10, x2 - 1, y1 + 14, fill="#d74b39", outline="")
        self.canvas.create_oval(mid_x - 8, y1 + 20, mid_x - 4, y1 + 24, fill="black", outline="")
        self.canvas.create_oval(mid_x + 4, y1 + 20, mid_x + 8, y1 + 24, fill="black", outline="")
        arm_offset = 8 if self.facing > 0 else -8
        self.canvas.create_line(mid_x, y1 + 16, mid_x + arm_offset, y1 + 24, fill="#f1c89b", width=4)

    def _world_to_screen(self, x1: float, y1: float, x2: float, y2: float) -> tuple[float, float, float, float]:
        return x1 - self.camera_x, y1, x2 - self.camera_x, y2

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    DesktopMarioMac().run()
