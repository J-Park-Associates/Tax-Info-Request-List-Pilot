#!/bin/bash
# ── Build the Mac app and its disk image ───────────────────────────────
# Output: build-portable/installer/<productName>-<version>-mac-arm64.dmg and
# the SHA-256 file beside it. Run it in Terminal on an Apple silicon Mac:
#
#   ./build-mac.sh
#
# This is "Build App.bat" and "pilot/Build Pilot Installer.bat" for a Mac
# (SPEC-mac R16, R17) in one file: the Mac's package is one app bundle, so
# there is no step between the folder and the installer. "Build GPU Pack.bat"
# has no counterpart: the CPU reader is the Mac's reader (R32).
#
# The disk image is exactly what is committed: this refuses a tree with any
# uncommitted change (pilot decision P13), and the commit is recorded in
# BUILD-INFO.txt. The version comes from app/renderer/pilot-content.js, its
# one home; the product's and the API executable's names from app/package.json,
# which the shell reads too, so nothing is typed twice. Nothing is stamped
# into any file.
#
# Reproducible, as the Windows build is: the Python packages (requirements.lock
# and requirements-build.lock, by version and by hash), the Electron packages
# (app/package-lock.json, installed with npm ci) and the freeze itself
# (api_entry.spec) are all pinned in the commit being built.
#
# Seven steps, in this order, and the order is the point:
#   1  freeze the API (arm64, ad-hoc signed by PyInstaller),
#   2  package Electron for darwin/arm64 with the icon and Info.plist keys,
#   3  copy the freeze into the bundle,
#   4  write BUILD-INFO.txt into the bundle,
#   5  sign the bundle ad hoc, inside out, and verify the seal,
#   6  prove the bundle holds no store, log, task file or settings,
#   7  make the disk image and its SHA-256.
# 4 is before 5 because a file written after signing breaks the seal; 5 is
# before 7 because an image of an unsigned or broken-sealed app is the one
# Apple silicon calls damaged. It runs under the /bin/bash 3.2 macOS ships
# (no mapfile, no ${x,,}).

cd "$(dirname "$0")" || exit 1

# Before any other command: bash would otherwise look for python3, node, npm
# and git in this folder, or in a relative folder PATH names, before the
# folders that hold the real ones, so a file dropped here named like one of
# them would run instead (E-10). Only absolute folders are kept.
clean_path=""
old_ifs=$IFS
IFS=:
for dir in $PATH; do
  case "$dir" in
    /*) clean_path="${clean_path:+$clean_path:}$dir" ;;
  esac
done
IFS=$old_ifs
PATH=$clean_path

fail() {
  echo "$1"
  exit 1
}

[ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ] ||
  fail "The Mac app is built on an Apple silicon Mac, in a Terminal that is not running under Rosetta (this one reports $(uname -s) $(uname -m))."
for tool in python3 node npm git codesign ditto hdiutil shasum file find; do
  command -v "$tool" >/dev/null 2>&1 || fail "$tool was not found, and the build needs it."
done
python3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >/dev/null 2>&1 ||
  fail "Python was not found, or is older than the app needs. Install Python 3.11+ and run build-mac.sh again."

echo "Checking that everything is committed..."
git rev-parse --verify HEAD >/dev/null 2>&1 ||
  fail "This folder is not a git checkout, or git is not installed: the disk image must be built from a commit."
[ -z "$(git status --porcelain)" ] ||
  fail "Commit or discard your changes first: the disk image must be built from exactly what is committed."
COMMIT=$(git rev-parse HEAD)

OUT=build-portable
PLATFORM=darwin
ARCH=arm64
# The product's name, the API executable's name and the version each live in
# one place; the shell reads the first two from the same file.
NAME=$(node -p "require('./app/package.json').productName") || fail "Could not read productName from app/package.json"
API=$(node -p "require('./app/package.json').config.apiName") || fail "Could not read config.apiName from app/package.json"
VER=$(node -p "require('./app/renderer/pilot-content.js').edition.version") ||
  fail "Could not read the version from app/renderer/pilot-content.js"
[ -n "$NAME" ] && [ -n "$API" ] && [ -n "$VER" ] || fail "The product name, the API name or the version is empty."
APP_ID="com.jparkassociates.taxdocumentconsole"

echo "[1/7] Freezing the Python tracker API (PyInstaller, api_entry.spec)..."
# The freeze runs in its own virtual environment holding exactly the two
# locks. PyInstaller follows every import it can find, including a library's
# optional ones, so freezing from the machine's Python ships whatever else
# happens to be installed there.
VENV="$OUT/venv"
# Made fresh every build: a package once installed into a reused venv would
# be frozen into every later package.
python3 -m venv --clear "$VENV" || fail "Could not create the build environment"
PY="$VENV/bin/python"
# The locks pin the whole tree (decision 137) and name the SHA-256 of every
# file (decision 191); --require-hashes also refuses any package they do not
# name.
"$PY" -m pip install --require-hashes -r requirements.lock -r requirements-build.lock --quiet ||
  fail "Installing requirements.lock and requirements-build.lock failed"
# The reader's own package, without its dependencies (decision 169, R-11):
# its metadata asks for the GUI build of OpenCV, which the app does not ship.
"$PY" -m pip install --require-hashes --no-deps -r requirements-nodeps.lock --quiet ||
  fail "Installing requirements-nodeps.lock failed"
"$PY" -m PyInstaller --noconfirm --clean --distpath "$OUT/py" --workpath "$OUT/pyi-work" api_entry.spec ||
  fail "PyInstaller failed"

echo "[2/7] Packaging Electron (npm ci from package-lock.json)..."
# The packager runs from app/, so --icon, --extend-info and --out are
# relative to it. It is run through its entry script, not the npx shim: the
# shim breaks when the folder's path contains an ampersand. Info-mac.plist
# holds LSMinimumSystemVersion (R6) and the three folder-access purpose
# strings macOS shows when the app first reads the clients folder.
(cd app && npm ci --no-audit --no-fund) || fail "npm ci failed - check your internet connection."
(cd app && node node_modules/@electron/packager/bin/electron-packager.mjs . "$NAME" \
  --platform="$PLATFORM" --arch="$ARCH" --out="../$OUT/dist" \
  --icon=assets/icon.icns --app-bundle-id="$APP_ID" --extend-info=assets/Info-mac.plist \
  --overwrite) || fail "electron-packager failed"
PKG="$OUT/dist/$NAME-$PLATFORM-$ARCH"
APP="$PKG/$NAME.app"
[ -d "$APP/Contents/Resources" ] || fail "The package has no $APP"

echo "[3/7] Copying the freeze into the app..."
rm -rf "${APP:?}/Contents/Resources/$API"
# ditto, not cp: it keeps the links, the modes and the extended attributes
# a signed Mach-O needs.
ditto "$OUT/py/$API" "$APP/Contents/Resources/$API" || fail "Copying the frozen API into the app failed"
[ -x "$APP/Contents/Resources/$API/$API" ] || fail "The app has no $API"

echo "[4/7] Writing BUILD-INFO.txt..."
# In Contents/Resources: tracker.after_install.build_info looks two folders
# above the API executable (Resources/<apiName>/<apiName>), and it must
# be written before signing, which seals what Resources holds.
{
  echo "$NAME"
  echo "Built:    $(date)"
  echo "Built on: $(hostname)"
  echo "Commit:   $COMMIT"
  echo "macOS:    $(sw_vers -productVersion)"
  echo "Python:   $("$PY" --version)"
  echo "Node:     $(node --version)"
  echo "npm:      $(npm --version)"
  echo
  echo "Python packages frozen (pip freeze):"
  "$PY" -m pip freeze
} > "$APP/Contents/Resources/BUILD-INFO.txt" || fail "Could not write BUILD-INFO.txt"

echo "[5/7] Signing the app ad hoc, inside out..."
# Copying the freeze into a packaged app breaks Electron's seal, and on Apple
# silicon an app with a broken seal is called damaged. The freeze is not
# nested code the OS looks for, so each Mach-O in it is signed by hand first;
# then the app, whose resource seal now covers them. --deep is a deviation
# from R17's plain codesign --force --sign -, kept for this ad-hoc test build
# only: electron-packager renames Electron's helper apps and rewrites their
# Info.plist files, which breaks their seals, and without re-signing them
# codesign --verify --deep --strict below fails. With no identity, no hardened
# runtime and no entitlements, one ad-hoc pass over everything nested does no
# harm. A Developer-ID build (R37) signs each helper and framework explicitly,
# inside out, instead.
find "$APP/Contents/Resources/$API" -type f -print0 | while IFS= read -r -d '' file; do
  if file -b "$file" | grep -q "Mach-O"; then
    codesign --force --sign - "$file" || exit 1
  fi
done || fail "Signing a program in the frozen API failed"
codesign --force --deep --sign - "$APP" || fail "Signing the app failed"
codesign --verify --deep --strict "$APP" || fail "The app's seal does not verify"

echo "[6/7] Checking the app holds no store, run log, task file or settings..."
# Decision 186: nothing a data folder or a settings folder holds may be in the
# package (tests/test_build.py holds this list to the names the code owns).
names=(tracker.db tracker.db-wal tracker.db-shm runs.log pass-order.json record-heads.db record-heads.db-journal record-heads.db-wal record-heads.db-shm record-heads.db.damaged recovered last-pass.json tracker-errors.log tracker-errors.log.1 tracker-errors.log.2 tracker-errors.log.3 passes tax-tracker.xml ocr-scratch tax-document-tracker-pilot settings.json)
patterns=('tracker.db.v*.old*' 'record-heads.db.v*.old*')
matchers=()
for name in "${names[@]}" "${patterns[@]}"; do
  matchers+=(-o -name "$name")
done
found=$(find "$APP" \( "${matchers[@]:1}" \) -print)
[ -z "$found" ] || fail "The app holds what belongs in a data folder or a settings folder: $found"

echo "[7/7] Making the disk image..."
STAGE="$OUT/dmg"
rm -rf "$STAGE"
mkdir -p "$STAGE" "$OUT/installer" || fail "Could not make $STAGE"
ditto "$APP" "$STAGE/$NAME.app" || fail "Copying the app into the disk image's folder failed"
ln -s /Applications "$STAGE/Applications" || fail "Could not link /Applications"
DMG_NAME="$(echo "$NAME" | tr ' ' '-')-$VER-mac-$ARCH.dmg"
DMG="$OUT/installer/$DMG_NAME"
rm -f "$DMG"
hdiutil create -volname "$NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG" || fail "hdiutil failed"
[ -f "$DMG" ] || fail "The disk image was not produced: $DMG"
# <hex>  <name>, the form shasum -c reads, beside the image.
(cd "$OUT/installer" && shasum -a 256 "$DMG_NAME" > "$DMG_NAME.sha256") || fail "Could not write the SHA-256 file"

echo
echo "Disk image: $PWD/$DMG"
cat "$OUT/installer/$DMG_NAME.sha256"
echo
echo "Tag this commit pilot-$VER (never v...)"
exit 0
