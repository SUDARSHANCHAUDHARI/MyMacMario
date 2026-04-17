# Desktop Mario for MacBook

This repo is a macOS-first recreation of the idea behind [`bxf1001g/desktop_mario`](https://github.com/bxf1001g/desktop_mario): a Mario-style mini-game for Mac with a working desktop-style overlay mode, global hotkey, and native menu-bar control.

## What this version includes

- Smoother movement with coyote time, jump buffering, enemy stomps, particles, and win flow
- Generated retro visuals for the player, enemies, coins, terrain, and UI
- Retro synthesized sound effects for jumping, coins, stomps, getting hit, and finishing the run
- `pygame`-based macOS renderer that is confirmed working locally
- Borderless bottom-docked overlay mode
- Global `Ctrl+Alt+O` overlay toggle
- Native macOS menu-bar item (`M`) for overlay, opacity, reset, focus, and quit
- PyInstaller spec and build script for packaging into a `.app`

## Requirements

- macOS
- Python 3.9+

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 desktop_mario_mac.py
```

## Build A macOS App

```bash
source .venv/bin/activate
./scripts/build_app.sh
```

The app bundle will be created at:

```bash
dist/Desktop Mario Mac.app
```

Inside the bundle build output, PyInstaller also creates the supporting onedir app contents it needs for macOS packaging.

## Controls

- `Left` / `Right`: Move
- `Space` / `Up`: Jump
- `Shift`: Run
- `R`: Reset run
- `O` or `F10`: Toggle overlay mode
- `P` or `F11`: Cycle overlay opacity
- `Ctrl+Alt+O`: Global overlay toggle
- `Ctrl+Alt+P`: Global opacity cycle
- `Esc`: Quit or exit overlay mode

## Test Flow

1. Run `python3 desktop_mario_mac.py`
2. Verify the game window appears immediately
3. Test movement, jumping, coin collection, enemy stomps, reset, and sound playback
4. Toggle overlay mode with `O` and verify the app becomes borderless and bottom-docked
5. Use `P` to cycle overlay opacity
6. Verify the native menu-bar item `M` appears and can toggle overlay/focus/reset/quit
7. Test `Ctrl+Alt+O` as a global hotkey
8. Build the app with `./scripts/build_app.sh`
9. Re-test the same flow using `dist/Desktop Mario Mac.app`

## Notes

- This is a Mac adaptation, not a byte-for-byte port of the Windows implementation.
- The current version uses a `pygame` renderer because that proved reliable on your Mac, unlike the earlier Tk overlay path.
- Sound is generated locally in code, so there are no external audio assets to manage yet.
- If you want a closer visual match to the original project next, we can swap in sprite sheets, add music, and further polish the overlay behavior.
