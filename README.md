# Desktop Mario for MacBook

This repo is a macOS-first recreation of the idea behind [`bxf1001g/desktop_mario`](https://github.com/bxf1001g/desktop_mario): a Mario-style mini-game that appears directly on your desktop as a transparent overlay.

## What this version includes

- Transparent desktop overlay anchored to the bottom of the screen
- Global `Ctrl+Alt+M` hotkey to show or hide the game
- Menu bar icon with show/hide, reset, and quit actions
- Smoother movement with coyote time, jump buffering, enemy stomps, particles, and win flow
- Generated pixel-art sprite frames for the player, enemies, coins, bricks, and blocks
- Retro synthesized sound effects for jumping, coins, stomps, getting hit, and finishing the run
- Optional native macOS integration via `pyobjc` for accessory-app behavior
- PyInstaller spec and build script for packaging into a `.app`

## Requirements

- macOS
- Python 3.9+
- Tk with macOS support

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

## Controls

- `Ctrl+Alt+M`: Show or hide the overlay
- `Left` / `Right`: Move
- `Space`: Jump
- `Shift`: Run
- `Esc`: Hide the game

## macOS permissions

For the global hotkey and menu bar behavior to work consistently, macOS may ask for:

- `Accessibility`
- `Input Monitoring`

Grant those permissions to the Python interpreter while running from source, or to the packaged `.app` when testing the built bundle.

## Test Flow

1. Run `python3 desktop_mario_mac.py`
2. Press `Ctrl+Alt+M` to reveal the overlay
3. Verify movement, jumping, coin collection, enemy stomps, and sound playback
4. Press `Esc` to hide and use the menu bar icon to re-open or quit
5. Build the app with `./scripts/build_app.sh` and re-test the same flow using `dist/Desktop Mario Mac.app`

## Notes

- This is a Mac adaptation, not a byte-for-byte port of the Windows implementation.
- Sprite assets and sounds are generated locally by the app, so there are no external art or audio files to manage yet.
- If you want a closer visual match to the original Windows project next, we can swap the generated assets for a dedicated sprite sheet and add music.
