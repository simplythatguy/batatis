#!/usr/bin/env bash
# Installs the latest stable Batatis desktop app on a Mac.
# A browser marks a downloaded app as quarantined, and macOS blocks a quarantined app that
# Apple has not notarized. curl adds no quarantine mark, so the app opens straight away.
# The checksum from the release proves the download is the file GitHub Actions built.
set -euo pipefail

REPO="${BATATIS_REPO:-simplythatguy/batatis}"
DEST="${BATATIS_INSTALL_DIR:-/Applications}"
BASE="https://github.com/$REPO/releases/latest/download"

fail() { echo "Batatis install: $*" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || fail "this installer is for macOS."
[ "$(uname -m)" = "arm64" ] || fail "Batatis needs a Mac with Apple silicon (M1 or later)."

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Finding the latest Batatis release..."
curl -fsSL "$BASE/SHA256SUMS" -o "$WORK/SHA256SUMS" || fail "could not reach GitHub."
ZIP="$(awk '/-mac-arm64\.zip$/ { print $2; exit }' "$WORK/SHA256SUMS")"
[ -n "$ZIP" ] || fail "the latest release has no Mac download."

echo "Downloading $ZIP..."
curl -fL --progress-bar "$BASE/$ZIP" -o "$WORK/$ZIP" || fail "the download failed."
(cd "$WORK" && grep " $ZIP\$" SHA256SUMS | shasum -a 256 -c -s) || fail "the download does not match its checksum."

/usr/bin/ditto -x -k "$WORK/$ZIP" "$WORK/app"
[ -d "$WORK/app/Batatis.app" ] || fail "the download has no Batatis.app."

if [ ! -w "$DEST" ]; then
  DEST="$HOME/Applications"
  mkdir -p "$DEST"
fi

if pgrep -xq Batatis; then
  osascript -e 'quit app "Batatis"' >/dev/null 2>&1 || true
  sleep 2
fi
rm -rf "$DEST/Batatis.app"
mv "$WORK/app/Batatis.app" "$DEST/Batatis.app"
xattr -dr com.apple.quarantine "$DEST/Batatis.app" 2>/dev/null || true

echo "Installed Batatis in $DEST. Opening it now."
open "$DEST/Batatis.app"
