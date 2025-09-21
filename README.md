# Bazzite Sunshine Manager

A lightweight tool to import Steam, Heroic (Epic/GOG), and Lutris games into [Sunshine](https://github.com/LizardByte/Sunshine).  
It scans local libraries, applies blacklists, fetches cover art (Steam CDN or SteamGridDB), and safely merges everything into Sunshine’s `apps.json`.

this tool is optimized to run under [Bazzite](https://github.com/ublue-os/bazzite).

## ✨ Features
- Import installed Steam games
- Import installed Heroic games (GOG, Epic, Standealone)
- Blacklist by AppID or regex
- Cover art via Steam CDN, Heroic cache or SteamGrid

## 🚀 Quick start
Ensure sunshine is enabled
```bash
ujust setup-sunshine
```
Choice enable is not enabled yet

Launch the init script, it will:
- create clone the repository into /var/home/steam/.config/sunshine/helper and configure ownership/permissions
- create a symbolic link for sunshine-import.sh in the home directory for easy further use
```bash
curl -fsSL https://raw.githubusercontent.com/wadiebs/bazzite-sunshine-manager/main/common/init.sh | bash
```
To run the import of games to sunshine process, run:
```bash
${HOME}/sunshine-import.sh
```
To run it with steamgrid enabled:
```bash
${HOME}/sunshine-import.sh --sgdb-key "YOUR_STEAMGRID_API"
```


