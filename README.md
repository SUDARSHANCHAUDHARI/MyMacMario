# Desktop Mario for MacBook

This repo is a macOS-first recreation of the idea behind [`bxf1001g/desktop_mario`](https://github.com/bxf1001g/desktop_mario): a Mario-style mini-game for Mac with a working desktop-style overlay mode, global hotkey, and native menu-bar control.

## Table of Contents

- [What this version includes](#what-this-version-includes)
- [Requirements](#requirements)
- [Install](#install)
- [Build A macOS App](#build-a-macos-app)
- [Controls](#controls)
- [Test Flow](#test-flow)
- [Notes](#notes)
- [License](#license)
- [About](#about)

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

## License

MIT — see [LICENSE](LICENSE).

---

## About

I'm Sudarshan Chaudhari, a Senior Quality Engineer, Test Automation specialist, and AI systems builder based in Bangkok, Thailand.

I have 13+ years of experience in software quality engineering, working across SaaS, fintech, gaming, web, mobile, cloud, and digital signage platforms. My background combines hands-on test automation with QA leadership, test strategy, CI/CD, release quality, production investigation, and cross-platform validation.

Alongside my professional QA career, I run [SudarshanTechLabs](https://sudarshantechlabs.com/), my independent engineering and product lab where I design, build, test, and ship software across Android, web, AI, cybersecurity, developer tooling, and cross-platform applications.

### What I work on

- ⚙️ **Quality Engineering & Test Automation** — Playwright, Selenium, Cypress, Appium, API testing, automation frameworks, end-to-end testing, CI/CD, release gates, GitHub Actions, risk-based testing, and production validation
- 🤖 **AI Systems & Automation** — AI agents, multi-agent orchestration, MCP servers, AI-assisted QA, prompt tooling, developer workflows, automation systems, and Claude Code plugins
- 📱 **Mobile & Cross-Platform Applications** — Android applications built with Kotlin and Jetpack Compose, Google Play releases, automated build and publishing pipelines, and cross-platform development spanning iOS, web, Windows, and macOS
- 🌐 **Web Applications & Platforms** — Full-stack applications using Next.js, TypeScript, Firebase, Cloudflare, REST APIs, and modern web infrastructure
- 🛠️ **Developer Tooling & CLI Engineering** — Rust, Python, TypeScript, CLI utilities, multi-repository tooling, build automation, release tooling, and engineering productivity systems
- 🛡️ **Cybersecurity & Observability** — Threat detection, log analysis, security auditing, vulnerability assessment, monitoring, and security-focused developer tools
- 📺 **Digital Signage & Device Platforms** — Content validation, playback testing, device compatibility, production investigation, monitoring, and QA across diverse hardware and operating-system environments

My work sits at the intersection of quality engineering, automation, AI, and software development. I approach products with a QA mindset from the beginning: understanding failure modes, designing for testability, automating repetitive work, and building release confidence into the engineering process.

Through SudarshanTechLabs, I also build products and tools from idea to production, covering architecture, development, testing, CI/CD, release automation, monitoring, and ongoing maintenance.

🌐 [sudarshantechlabs.com](https://sudarshantechlabs.com/) · 💼 [LinkedIn](https://linkedin.com/in/sudarshan-chaudhari) · 🐙 [GitHub](https://github.com/SUDARSHANCHAUDHARI) · ✉️ [sunny.sudarshan@gmail.com](mailto:sunny.sudarshan@gmail.com)
