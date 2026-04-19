#!/usr/bin/env bash
# Build a distributable DMG from the Desktop Mario Mac .app bundle.
# No external tools required — uses only hdiutil and AppleScript (both built-in).
#
# Usage:
#   ./scripts/build_dmg.sh
#
# Prerequisites:
#   - Run ./scripts/build_app.sh first to produce dist/"Desktop Mario Mac.app"
#   - For a notarized DMG, run ./scripts/notarize.sh before this script

set -euo pipefail

APP_NAME="Desktop Mario Mac"
APP_PATH="dist/${APP_NAME}.app"
DMG_FINAL="dist/${APP_NAME}.dmg"
DMG_TMP="dist/${APP_NAME}_tmp.dmg"
VOLUME_NAME="${APP_NAME}"
DMG_SIZE="160m"

if [ ! -d "$APP_PATH" ]; then
  echo "Error: $APP_PATH not found. Run ./scripts/build_app.sh first."
  exit 1
fi

echo "Cleaning previous DMG artifacts..."
rm -f "$DMG_FINAL" "$DMG_TMP"

# ------------------------------------------------------------------
# 1. Create a temporary read-write disk image large enough for the app
# ------------------------------------------------------------------
echo "Creating temporary disk image (${DMG_SIZE})..."
hdiutil create \
  -volname  "$VOLUME_NAME" \
  -srcfolder "$APP_PATH" \
  -ov \
  -format   UDRW \
  -size     "$DMG_SIZE" \
  "$DMG_TMP"

# ------------------------------------------------------------------
# 2. Mount it so we can customise the Finder window layout
# ------------------------------------------------------------------
echo "Mounting image..."
MOUNT_DIR=$(hdiutil attach "$DMG_TMP" -readwrite -noverify -noautoopen \
  | grep "^/dev" | tail -1 | awk '{print $NF}')
echo "Mounted at: $MOUNT_DIR"

# Give Finder a moment to settle
sleep 2

# ------------------------------------------------------------------
# 3. Add a symbolic link to /Applications for drag-install UX
# ------------------------------------------------------------------
ln -sf /Applications "${MOUNT_DIR}/Applications"

# ------------------------------------------------------------------
# 4. Set Finder window appearance via AppleScript
# ------------------------------------------------------------------
osascript <<EOF
tell application "Finder"
  tell disk "${VOLUME_NAME}"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set the bounds of container window to {400, 100, 950, 420}
    set theViewOptions to the icon view options of container window
    set arrangement of theViewOptions to not arranged
    set icon size of theViewOptions to 128
    set position of item "${APP_NAME}.app" of container window to {140, 160}
    set position of item "Applications" of container window to {400, 160}
    close
    open
    update without registering applications
    delay 2
    close
  end tell
end tell
EOF

# ------------------------------------------------------------------
# 5. Flush and unmount
# ------------------------------------------------------------------
echo "Unmounting..."
sync
hdiutil detach "$MOUNT_DIR" -quiet

# ------------------------------------------------------------------
# 6. Convert to compressed read-only UDZO (standard DMG format)
# ------------------------------------------------------------------
echo "Converting to compressed DMG..."
hdiutil convert "$DMG_TMP" \
  -format UDZO \
  -imagekey zlib-level=9 \
  -o "$DMG_FINAL"

rm -f "$DMG_TMP"

echo ""
echo "Done: ${DMG_FINAL}"
du -sh "$DMG_FINAL"
