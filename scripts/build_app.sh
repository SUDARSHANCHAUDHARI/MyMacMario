#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-/tmp/pyinstaller}"

"$PYTHON_BIN" -m PyInstaller --noconfirm DesktopMarioMac.spec

echo
echo "Built app bundle:"
echo "  $ROOT_DIR/dist/Desktop Mario Mac.app"
