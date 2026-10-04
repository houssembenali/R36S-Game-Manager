"""Emplacements des fichiers et petites différences Windows / Linux.

- asset(...)  : fichiers fournis avec le programme (polices…), en lecture seule. Dans
                l'exécutable PyInstaller, ils sont décompressés dans un dossier temporaire.
- data(...)   : fichiers écrits par le programme (logos importés, chdman, cache internet).
                Depuis les sources : à côté du programme. Depuis l'exécutable : dans le dossier
                de l'utilisateur (%LOCALAPPDATA%\\R36S-Game-Manager ou ~/.local/share/r36s-game-manager).
"""
import os
import subprocess
import sys

WINDOWS = os.name == "nt"
FROZEN = getattr(sys, "frozen", False)
SOURCE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = getattr(sys, "_MEIPASS", SOURCE)

if not FROZEN:
    DATA = SOURCE
elif WINDOWS:
    DATA = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "R36S-Game-Manager")
else:
    DATA = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
                        "r36s-game-manager")


def asset(*parts):
    return os.path.join(BUNDLE, "assets", *parts)


def data(*parts):
    return os.path.join(DATA, *parts)


def open_file(path):
    """Ouvre un fichier avec le programme associé (notice d'un port…)."""
    import subprocess
    if WINDOWS:
        os.startfile(path)  # noqa: S606 - fichier choisi par le programme sur la carte
    else:
        subprocess.Popen(["xdg-open", path])


def reveal(path):
    """Montre un fichier dans l'explorateur de fichiers (ou ouvre un dossier)."""
    if WINDOWS:
        if os.path.isdir(path):
            os.startfile(path)
        else:
            subprocess.Popen(f'explorer /select,"{path}"')
    else:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
