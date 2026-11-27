# Bazzite Sunshine Manager

A lightweight tool to import Steam, Heroic (Epic/GOG/Amazon), and Lutris games into [Sunshine](https://github.com/LizardByte/Sunshine).  
It scans local libraries, applies blacklists, fetches cover art (Steam CDN or SteamGridDB), and creates or updates applications through Sunshine's localhost HTTPS API.

this tool is optimized to run under [Bazzite](https://github.com/ublue-os/bazzite).

## ✨ Features
- Import installed Steam games
- Import installed Heroic games (GOG, Epic, Amazon, Standalone)
- Blacklist by AppID or regex
- Cover art via Steam CDN, Heroic cache or SteamGrid

## 🚀 Quick start
Ensure sunshine is enabled
```bash
ujust setup-sunshine
```
Choice enable is not enabled yet

1. Init command
Launch the init script, it will:
- create clone the repository into /var/home/steam/.config/sunshine/helper and configure ownership/permissions
- create a symbolic link for sunshine-import.sh in `~/.local/bin` for easy further use
- In case it is not the first run, the init command will update the existing files 
```bash
curl -fsSL https://raw.githubusercontent.com/wadiebs/bazzite-sunshine-manager/main/common/init.sh | bash
```

2. Import Script 
To run the import of games to sunshine process:
```bash
sunshine-import
```

Enter your Sunshine Web UI username and password when prompted. For unattended runs,
set `SUNSHINE_USERNAME` and `SUNSHINE_PASSWORD` in the process environment.
You can also pass `--sunshine-user USER` and `--sunshine-password PASSWORD`.
These flags override their corresponding environment variables.

The API must already be running at `https://localhost:47990`. Use
`--sunshine-port PORT` (or `SUNSHINE_PORT`) for a different local port.
Sunshine's self-signed certificate is accepted by default on this localhost-only
connection; `--verify-tls` or `SUNSHINE_VERIFY_TLS=1` enables certificate validation
using the system trust store.

Applications are matched by exact name: existing matches are updated and new names
are created. Other entries, including games now blacklisted or uninstalled, remain
untouched. Duplicate existing names stop the import with an error. Saves take effect
immediately, so `--restart` is optional. It sends `POST /api/restart` after all
saves succeed. If a save or the restart request fails, the command exits nonzero.
Earlier saves remain applied.

The importer no longer reads, backs up, or writes `apps.json`, or changes Sunshine's
global environment (`ENV_PATH_APPEND` is no longer used). Ensure launch commands
are available in Sunshine's existing `PATH`. Cover images are still stored locally;
`--conf-dir` selects their Sunshine directory and must be accessible to Sunshine.
The API contract follows [Sunshine's Web UI handlers](https://github.com/LizardByte/Sunshine/blob/master/src/confighttp.cpp).

To run it with steamgrid enabled and restart sunshine service after import:
```bash
sunshine-import --sgdb-key "YOUR_STEAMGRID_API" --restart
```

