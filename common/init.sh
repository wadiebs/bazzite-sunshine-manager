DEST="/var/home/steam/.config/sunshine/helper"
TMP="$(mktemp -d)"

curl -L -o "$TMP/repo.zip" https://github.com/wadiebs/bazzite-sunshine-manager/archive/refs/heads/main.zip
unzip -q "$TMP/repo.zip" -d "$TMP"

mkdir -p "$DEST"
rsync -a --delete --exclude=".git" --exclude=".github" "$TMP"/bazzite-sunshine-manager-*/ "$DEST/"

chown -R steam:steam "$DEST"
rm -rf "$TMP"
