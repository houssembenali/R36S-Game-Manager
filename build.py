"""Fabrique l'exécutable autonome (un seul fichier) avec PyInstaller.

    python build.py

Windows -> dist/R36S-Game-Manager.exe      Linux -> dist/R36S-Game-Manager
Un exécutable se fabrique sur le système visé (PyInstaller ne compile pas Windows -> Linux) :
GitHub Actions fabrique les deux à chaque version (voir .github/workflows/build.yml).
"""
import os
import sys

import PyInstaller.__main__

HERE = os.path.dirname(os.path.abspath(__file__))
SEP = os.pathsep  # « ; » sous Windows, « : » sous Linux

args = [
    os.path.join(HERE, "app.py"),
    "--name", "R36S-Game-Manager",
    "--onefile",
    "--windowed",                                   # pas de console
    "--noconfirm",
    "--clean",
    "--icon", os.path.join(HERE, "assets", "icon.ico" if os.name == "nt" else "icon.png"),
    "--add-data", f"{os.path.join(HERE, 'assets', 'fonts')}{SEP}assets/fonts",
    "--add-data", f"{os.path.join(HERE, 'assets', 'icon.png')}{SEP}assets",
    "--collect-all", "tkinterdnd2",                 # bibliothèque native du glisser-déposer
    "--hidden-import", "vlc",
]
if __name__ == "__main__":
    PyInstaller.__main__.run(args + sys.argv[1:])
