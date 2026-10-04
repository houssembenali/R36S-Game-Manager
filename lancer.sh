#!/usr/bin/env sh
# Lance le gestionnaire de jeux R36S depuis les sources (Linux).
# Prérequis : python3, python3-tk ; VLC pour les vidéos (sudo apt install python3-tk vlc).
cd "$(dirname "$0")" || exit 1
python3 -c "import PIL, tkinterdnd2, vlc, certifi" 2>/dev/null || python3 -m pip install --user -r requirements.txt
exec python3 app.py
