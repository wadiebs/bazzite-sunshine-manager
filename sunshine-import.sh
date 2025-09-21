#!/usr/bin/env bash
# sunshine-import — wrapper to run sunshine-import.py with flags
#
# Usage:
#   sunshine-import [options] [-- <extra-args-to-python-script>]
#
# Options:
#   --steam / --no-steam           Enable/disable Steam importer (EXPORT: IMPORT_STEAM=1/0)
#   --heroic / --no-heroic         Enable/disable Heroic importer (IMPORT_HEROIC=1/0)
#   --launchers / --no-launchers   Enable/disable Launchers importer (IMPORT_LAUNCHERS=1/0)
#   --restart                      Restart Sunshine after import (systemctl --user restart sunshine.service)
#   --python PY                    Python interpreter to use (default: python3)
#   --conf-dir DIR                 Force Sunshine config dir (sets SUNSHINE_CONF_DIR for your script to read)
#   -h, --help                     Show help
#
# Examples:
#   sunshine-import --steam --no-heroic --restart
#   sunshine-import --python /usr/bin/python3
#   sunshine-import --conf-dir "$HOME/.config/sunshine"
#
set -euo pipefail

# Defaults
PYTHON="python3"
RESTART=0
: "${IMPORT_STEAM:=1}"
: "${IMPORT_HEROIC:=1}"
: "${IMPORT_LAUNCHERS:=1}"

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# If this wrapper lives in repo root next to sunshine-import.py, this will resolve correctly.
# Adjust if your layout differs.
PY_SCRIPT="${SCRIPT_DIR}/sunshine-import.py"

usage() { sed -n '1,50p' "$0" | sed -n '1,30p' >&2; exit 1; }

ARGS_TO_PY=()

while (( "$#" )); do
  case "$1" in
    --steam)        IMPORT_STEAM=1; shift ;;
    --no-steam)     IMPORT_STEAM=0; shift ;;
    --heroic)       IMPORT_HEROIC=1; shift ;;
    --no-heroic)    IMPORT_HEROIC=0; shift ;;
    --launchers)    IMPORT_LAUNCHERS=1; shift ;;
    --no-launchers) IMPORT_LAUNCHERS=0; shift ;;
    --restart)      RESTART=1; shift ;;
    --python)       PYTHON="${2:-}"; shift 2 ;;
    --conf-dir)     export SUNSHINE_CONF_DIR="${2:-}"; shift 2 ;;
    -h|--help)      usage ;;
    --)             shift; ARGS_TO_PY+=("$@"); break ;;
    *)              ARGS_TO_PY+=("$1"); shift ;;
  esac
done

# Sanity checks
if [[ ! -f "$PY_SCRIPT" ]]; then
  echo "ERROR: sunshine-import.py not found at: $PY_SCRIPT" >&2
  exit 1
fi

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: Python interpreter not found: $PYTHON" >&2
  exit 1
fi

# Environment toggles exported for the Python script
export IMPORT_STEAM IMPORT_HEROIC IMPORT_LAUNCHERS

echo "[sunshine-import] IMPORT_STEAM=$IMPORT_STEAM IMPORT_HEROIC=$IMPORT_HEROIC IMPORT_LAUNCHERS=$IMPORT_LAUNCHERS" >&2
if [[ -n "${SUNSHINE_CONF_DIR:-}" ]]; then
  echo "[sunshine-import] SUNSHINE_CONF_DIR=$SUNSHINE_CONF_DIR" >&2
fi
echo "[sunshine-import] Running: $PYTHON \"$PY_SCRIPT\" ${ARGS_TO_PY[*]:-}" >&2

set +e
"$PYTHON" "$PY_SCRIPT" "${ARGS_TO_PY[@]:-}"
RET=$?
set -e

if [[ $RET -ne 0 ]]; then
  echo "[sunshine-import] Python exited with code $RET" >&2
  exit "$RET"
fi

if [[ $RESTART -eq 1 ]]; then
  echo "[sunshine-import] Restarting Sunshine (user service)..." >&2
  systemctl --user restart sunshine.service || {
    echo "[sunshine-import] WARNING: failed to restart Sunshine." >&2
  }
fi

echo "[sunshine-import] Done." >&2
