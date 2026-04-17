# Desktop Mario for MacBook

This repo is a macOS-first recreation of the idea behind [`bxf1001g/desktop_mario`](https://github.com/bxf1001g/desktop_mario): a lightweight Mario-style mini-game that appears directly on your desktop as a transparent overlay.

## What this version includes

- Transparent always-on-top overlay window on macOS
- Global `Ctrl+Alt+M` hotkey to show or hide the game
- Menu bar icon with show/hide, reset, and quit actions
- Lightweight side-scrolling platformer with coins, enemies, jumping, running, and scoring
- Pure Python app structure so it is easy to tweak

## Requirements

- macOS
- Python 3.11+
- Tk with macOS support

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 desktop_mario_mac.py
```

## Controls

- `Ctrl+Alt+M`: Show or hide the overlay
- `Left` / `Right`: Move
- `Space`: Jump
- `Shift`: Run
- `Esc`: Hide the game

## macOS permissions

For the global hotkey to work consistently, macOS may ask for:

- `Accessibility`
- `Input Monitoring`

Grant those permissions to the Python interpreter or the packaged app you run.

## Notes

- This is a Mac adaptation, not a byte-for-byte port of the Windows implementation.
- The current version uses drawn shapes instead of the original project's sprite sheet assets.
- If you want, the next step can be turning this into a polished `.app` bundle with native menu bar behavior and custom sprite assets.
