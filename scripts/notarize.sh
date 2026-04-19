#!/usr/bin/env bash
# Codesign and notarize the Desktop Mario Mac .app bundle.
# Requirements:
#   - Xcode Command Line Tools
#   - An Apple Developer account with a valid Developer ID Application certificate
#   - App-specific password stored in Keychain as "notarytool-password"
#     (add via: xcrun notarytool store-credentials "notarytool-password"
#                 --apple-id YOUR_APPLE_ID --team-id YOUR_TEAM_ID --password APP_SPECIFIC_PASSWORD)
#
# Usage:
#   APPLE_ID=you@example.com TEAM_ID=XXXXXXXXXX ./scripts/notarize.sh

set -euo pipefail

APP_NAME="Desktop Mario Mac"
APP_PATH="dist/${APP_NAME}.app"
ZIP_PATH="dist/${APP_NAME}.zip"
BUNDLE_ID="com.sudarshantechlabs.desktopmariomac"
ENTITLEMENTS="scripts/entitlements.plist"

APPLE_ID="${APPLE_ID:?Set APPLE_ID env var}"
TEAM_ID="${TEAM_ID:?Set TEAM_ID env var}"
KEYCHAIN_PROFILE="notarytool-password"

if [ ! -d "$APP_PATH" ]; then
  echo "App not found at $APP_PATH — run ./scripts/build_app.sh first"
  exit 1
fi

# ------------------------------------------------------------------
# 1. Write a minimal entitlements file if none exists
# ------------------------------------------------------------------
if [ ! -f "$ENTITLEMENTS" ]; then
  cat > "$ENTITLEMENTS" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
</dict>
</plist>
EOF
  echo "Created $ENTITLEMENTS"
fi

# ------------------------------------------------------------------
# 2. Deep codesign — sign all binaries inside the bundle first,
#    then sign the outer .app with hardened runtime enabled
# ------------------------------------------------------------------
echo "Codesigning binaries inside the bundle..."
find "$APP_PATH" -type f \( -name "*.so" -o -name "*.dylib" \) | while read -r binary; do
  codesign --force --sign "Developer ID Application: ${TEAM_ID}" \
            --options runtime --timestamp "$binary"
done

echo "Codesigning the .app bundle..."
codesign --force --deep --sign "Developer ID Application: ${TEAM_ID}" \
         --options runtime --timestamp \
         --entitlements "$ENTITLEMENTS" \
         "$APP_PATH"

codesign --verify --deep --strict "$APP_PATH"
echo "Codesigning verified."

# ------------------------------------------------------------------
# 3. Zip for submission (ditto preserves resource forks)
# ------------------------------------------------------------------
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
echo "Created $ZIP_PATH"

# ------------------------------------------------------------------
# 4. Submit for notarization and wait for result
# ------------------------------------------------------------------
echo "Submitting to Apple Notary Service..."
xcrun notarytool submit "$ZIP_PATH" \
  --keychain-profile "$KEYCHAIN_PROFILE" \
  --apple-id "$APPLE_ID" \
  --team-id "$TEAM_ID" \
  --wait

# ------------------------------------------------------------------
# 5. Staple the ticket to the .app so it works offline
# ------------------------------------------------------------------
echo "Stapling notarization ticket..."
xcrun stapler staple "$APP_PATH"
xcrun stapler validate "$APP_PATH"

echo ""
echo "Done. $APP_PATH is signed, notarized, and stapled."
echo "You can now distribute it directly or wrap it in a DMG."
