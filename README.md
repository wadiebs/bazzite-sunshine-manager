# Bazzite Sunshine Manager

A lightweight tool to import Steam, Heroic (Epic/GOG), and Lutris games into [Sunshine](https://github.com/LizardByte/Sunshine).  
It scans local libraries, applies blacklists, fetches cover art (Steam CDN or SteamGridDB), and safely merges everything into Sunshine’s `apps.json`.

## ✨ Features
- Steam & Heroic importers (Lutris planned)
- Blacklist by AppID or regex
- Cover art via Steam CDN / SGDB
- Safe `apps.json` backup and merge
- Modular design with separate importers

## 🚀 Quick start
```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run importer
python main.py
