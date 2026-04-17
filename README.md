# Desktop Mario for MacBook

This repo is a macOS-first recreation of the idea behind [`bxf1001g/desktop_mario`](https://github.com/bxf1001g/desktop_mario): a Mario-style mini-game for Mac that now runs as a visible native desktop window.

## What this version includes

- Smoother movement with coyote time, jump buffering, enemy stomps, particles, and win flow
- Generated retro visuals for the player, enemies, coins, terrain, and UI
- Retro synthesized sound effects for jumping, coins, stomps, getting hit, and finishing the run
- `pygame`-based macOS window that is confirmed working locally
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

## Controls

- `Left` / `Right`: Move
- `Space` / `Up`: Jump
- `Shift`: Run
- `R`: Reset run
- `Esc`: Quit

## Test Flow

1. Run `python3 desktop_mario_mac.py`
2. Verify the game window appears immediately
3. Test movement, jumping, coin collection, enemy stomps, reset, and sound playback
4. Build the app with `./scripts/build_app.sh`
5. Re-test the same flow using `dist/Desktop Mario Mac.app`

## Notes

- This is a Mac adaptation, not a byte-for-byte port of the Windows implementation.
- The current version uses a `pygame` window because that proved reliable on your Mac, unlike the earlier Tk overlay path.
- Sound is generated locally in code, so there are no external audio assets to manage yet.
- If you want a closer visual match to the original project next, we can swap in sprite sheets, add music, and then revisit a more desktop-like always-on-top presentation.
