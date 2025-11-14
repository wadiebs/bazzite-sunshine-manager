#!/usr/bin/env bash
set -Eeuo pipefail

DEST="$HOME/.config/sunshine/helper"
TMP="$(mktemp -d)"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
cleanup() {
  say "Cleaning up temporary files..."
  rm -rf "$TMP"
}
trap cleanup EXIT

# --- Pre-flight checks ---
for bin in curl unzip rsync; do
  command -v "$bin" >/dev/null 2>&1 || { echo "Error: '$bin' is required but not installed."; exit 1; }
done

say "Destination: $DEST"
say "Working directory: $TMP"

# --- Download ---
say "Downloading repository archive..."
curl -fsSL -o "$TMP/repo.zip" "https://github.com/wadiebs/bazzite-sunshine-manager/archive/refs/heads/main.zip"
say "Download complete."

# --- Unzip ---
say "Unpacking archive..."
unzip -q "$TMP/repo.zip" -d "$TMP"
say "Unpack complete."

# --- Prepare destination ---
say "Creating destination directory (if needed)..."
mkdir -p "$DEST"

# --- Sync files ---
SRC_DIR="$(echo "$TMP"/bazzite-sunshine-manager-*)"
if [ ! -d "$SRC_DIR" ]; then
  echo "Error: Source directory not found at '$SRC_DIR'."
  exit 1
fi

say "Syncing files to $DEST ..."
rsync -a --delete --exclude=".git" --exclude=".github" "$SRC_DIR/" "$DEST/"
say "Sync complete."

# --- Ownership ---
CURRENT_USER="$(id -un)"
CURRENT_GROUP="$(id -gn)"
say "Setting ownership to $CURRENT_USER:$CURRENT_GROUP ..."
if chown -R "$CURRENT_USER:$CURRENT_GROUP" "$DEST" 2>/dev/null; then
  say "Ownership set successfully."
else
  say "Warning: Failed to change ownership. You may need to run this with sudo."
fi

# --- Permissions ---
say "Setting permissions to sunshine-import.sh"
chmod +x "$DEST/sunshine-import.sh"

# --- Create/refresh the symlink in $HOME/.local/bin (create this folder if it doesn't exist) ---
if [ ! -d "${HOME}/.local/bin" ]; then
  mkdir "${HOME}/.local/bin"
fi
say "Create Symlink for sunshine-import.sh"
ln -sfn "$DEST/sunshine-import.sh" "${HOME}/.local/bin/sunshine-import"

say "All done! Files are now in: $DEST"
