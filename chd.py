"""Compression des jeux CD en .chd avec chdman (outil officiel de MAME).

Un .chd est une image CD compressée sans perte, lue directement par les émulateurs de la R36S :
on gagne en général 30 à 60 % de place. chdman.exe est cherché dans tools/ (à côté du
programme) ou dans le PATH ; s'il manque, download_chdman() le récupère dans la dernière
version de MAME (extraction avec 7-Zip).
"""
import json
import os
import shutil
import subprocess
import time
import net

import core
import journal
import paths

TOOLS_DIR = paths.data("tools")
SYSTEMS = {"psx", "segacd", "saturn", "dreamcast", "pcenginecd", "pcengine", "3do", "neogeocd"}
SOURCE_EXT = {".cue", ".gdi"}   # formats que chdman sait convertir
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_chdman():
    local = os.path.join(TOOLS_DIR, "chdman.exe" if paths.WINDOWS else "chdman")
    return local if os.path.isfile(local) else shutil.which("chdman")


def find_7zip():
    for p in (r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if os.path.isfile(p):
            return p
    return shutil.which("7z")


def download_chdman(report=None, cancel=None):
    """Télécharge MAME (≈ 85 Mo), en extrait chdman.exe dans tools/. Retourne son chemin."""
    if not paths.WINDOWS:
        raise OSError("Installe chdman avec ton gestionnaire de paquets (ex. : sudo apt install mame-tools)")
    seven = find_7zip()
    if not seven:
        raise OSError("7-Zip est nécessaire pour extraire chdman (https://www.7-zip.org)")
    assets = json.loads(net.get("https://api.github.com/repos/mamedev/mame/releases/latest"))["assets"]
    asset = next(a for a in assets if a["name"].endswith("_x64.exe"))
    os.makedirs(TOOLS_DIR, exist_ok=True)
    archive = os.path.join(TOOLS_DIR, asset["name"])
    total, done = asset["size"], 0
    with net.open_url(asset["browser_download_url"], timeout=60) as r, open(archive, "wb") as f:
        while chunk := r.read(1 << 20):
            if cancel is not None and cancel.is_set():
                break
            f.write(chunk)
            done += len(chunk)
            if report:
                report(done * 100 // total, f"Téléchargement de MAME : {done >> 20} / {total >> 20} Mo")
    try:
        if cancel is not None and cancel.is_set():
            raise OSError("Téléchargement annulé")
        if report:
            report(100, "Extraction de chdman…")
        subprocess.run([seven, "e", archive, "chdman.exe", f"-o{TOOLS_DIR}", "-y"],
                       check=True, capture_output=True, creationflags=NO_WINDOW)
    finally:
        os.remove(archive)
    path = find_chdman()
    if not path:
        raise OSError("chdman.exe introuvable dans l'archive MAME")
    return path


def sources(game):
    """Fichiers .cue / .gdi à convertir pour ce jeu (plusieurs pour un .m3u multi-disques)."""
    ext = os.path.splitext(game.path)[1].lower()
    if ext in SOURCE_EXT:
        return [game.path]
    if ext == ".m3u":
        return [p for p in core.components(game.path) if os.path.splitext(p)[1].lower() in SOURCE_EXT]
    return []


def convertible(games_by_system):
    return [g for s, games in games_by_system.items() if s.lower() in SYSTEMS
            for g in games if sources(g)]


def convert_file(chdman, src, cancel=None):
    """Convertit un .cue/.gdi en .chd à côté, puis supprime l'original et ses pistes.
    Retourne le chemin du .chd."""
    out = os.path.splitext(src)[0] + ".chd"
    if os.path.exists(out):
        raise OSError(f"{os.path.basename(out)} existe déjà")
    parts = [src] + core.components(src)
    proc = subprocess.Popen([chdman, "createcd", "-i", src, "-o", out], stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, creationflags=NO_WINDOW)
    while proc.poll() is None:
        if cancel is not None and cancel.is_set():
            proc.kill()
            proc.wait()
            break
        time.sleep(0.3)
    if proc.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) == 0:
        if os.path.exists(out):
            os.remove(out)
        if cancel is not None and cancel.is_set():
            raise OSError("Conversion annulée")
        err = proc.stderr.read().decode("utf-8", "replace").strip().splitlines()
        raise OSError(err[-1] if err else "échec de chdman")
    journal.created(out)
    for p in parts:
        journal.remove(p)  # l'original part dans la corbeille : la compression s'annule
    return out


def convert_game(root, chdman, game, cancel=None):
    """Convertit un jeu et met à jour le gamelist.xml (ou le .m3u). Retourne les erreurs."""
    srcs = sources(game)
    done = {}
    for src in srcs:
        done[src] = convert_file(chdman, src, cancel)
    core.clear_cache()
    if os.path.splitext(game.path)[1].lower() == ".m3u":
        with open(game.path, encoding="utf-8") as f:
            text = f.read()
        for src, out in done.items():
            text = text.replace(os.path.basename(src), os.path.basename(out))
        def write(path):
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        journal.write_file(game.path, write)
        return []
    new = done[game.path]
    old_key = core._key_of(game.path)

    def rename(top, entries):
        el = entries.get(old_key)
        if el is not None:
            core._set_tag(el, "path", "./" + core._rel(new, game.sysdir))
    errors = core.edit_gamelist(root, game.sysdir, rename) if game.in_gamelist else []
    game.path = new
    return errors
