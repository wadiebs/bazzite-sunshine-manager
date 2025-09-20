# Bazzite Sunshine Manager

A lightweight tool to import Steam, Heroic (Epic/GOG), and Lutris games into [Sunshine](https://github.com/LizardByte/Sunshine).  
It scans local libraries, applies blacklists, fetches cover art (Steam CDN or SteamGridDB), and safely merges everything into Sunshine’s `apps.json`.

this tool is optimized to run under [Bazzite](https://github.com/ublue-os/bazzite).

## ✨ Features
- Steam & Heroic importers (Lutris planned)
- Blacklist by AppID or regex
- Cover art via Steam CDN / SGDB
- Safe `apps.json` backup and merge
- Modular design with separate importers

## 🚀 Quick start
Ensure sunshine is enabled
```bash
ujust setup-sunshine
```
Choice enable is not enabled yet

Go to a folder where you want to download this tool such as Scripts directory under home
```bash
mkdir -p "$HOME/Scripts" && cd "$HOME/Scripts"
```

Clone the repository
```bash
git clone https://github.com/wadiebs/bazzite-sunshine-manager.git
cd bazzite-sunshine-manager
```

To run the import of games to sunshine process, run:
```bash
python sunshine-import.py
```
