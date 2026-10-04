@echo off
rem Lance le gestionnaire de jeux R36S sans fenêtre console.
rem Installe au besoin Pillow (images), tkinterdnd2 (glisser-déposer) et python-vlc (vidéos, VLC requis).
python -c "import PIL, tkinterdnd2, vlc" 2>nul || python -m pip install --user pillow tkinterdnd2 python-vlc
start "" pythonw "%~dp0app.py"
