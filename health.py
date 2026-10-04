"""Vérification de la carte SD : chaque fichier est relu en entier pour trouver ceux qui sont abîmés.

Les cartes livrées avec la R36S lâchent souvent. Signes d'une carte qui meurt :
  unreadable  fichier illisible (erreur de lecture du lecteur)
  corrupt     archive .zip dont le contenu ne correspond plus à son empreinte (CRC)
  empty       ROM de 0 octet (copie interrompue)
  gamelist    gamelist.xml illisible (EmulationStation perd les fiches de la console)
  slow        lecture anormalement lente (secteurs fatigués)
"""
import os
import time
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field

import journal
import systems

SKIP_DIRS = {journal.TRASH.lower(), "system volume information", "$recycle.bin"}
CHUNK = 4 << 20
SLOW_SECONDS = 5      # un bloc de 4 Mo lu en plus de 5 s : la carte peine à lire cet endroit
SLOW_SPEED = 8 << 20  # moins de 8 Mo/s en moyenne : carte lente (ou fatiguée)
ARCHIVES = (".zip", ".7z", ".chd", ".rvz", ".cso", ".pbp")


@dataclass
class Problem:
    kind: str
    path: str
    detail: str = ""


@dataclass
class Result:
    problems: list = field(default_factory=list)
    read: int = 0         # octets relus
    total: int = 0        # octets à relire
    files: int = 0        # fichiers vérifiés
    seconds: float = 0.0
    cancelled: bool = False

    @property
    def speed(self):
        """Vitesse moyenne de lecture (octets/s), 0 si inconnue."""
        return self.read / self.seconds if self.seconds > 0.5 else 0


def card_files(root):
    """[(chemin, taille)] de tous les fichiers de la carte, hors corbeille et dossiers système."""
    out = []
    for top, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        for f in files:
            p = os.path.join(top, f)
            try:
                out.append((p, os.path.getsize(p)))
            except OSError:  # même sa taille est illisible
                out.append((p, -1))
    return out


def _read(path, slow):
    """Relit tout le fichier ; ajoute le chemin à slow si un bloc met trop longtemps."""
    with open(path, "rb") as f:
        while True:
            t = time.monotonic()
            chunk = f.read(CHUNK)
            if time.monotonic() - t > SLOW_SECONDS:
                slow.add(path)
            if not chunk:
                return


def check_file(path, size):
    """Problème trouvé sur ce fichier, ou None."""
    name = os.path.basename(path).lower()
    ext = os.path.splitext(name)[1]
    slow = set()
    try:
        if size < 0:
            raise OSError("taille illisible")
        if size == 0:
            if ext in ARCHIVES or systems.systems_for_extension(path):
                return Problem("empty", path)
            return None
        if ext == ".zip":
            with zipfile.ZipFile(path) as z:
                bad = z.testzip()  # relit et vérifie l'empreinte de chaque fichier de l'archive
            if bad:
                return Problem("corrupt", path, bad)
        elif name == "gamelist.xml":
            ET.parse(path)
        else:
            _read(path, slow)
    except zipfile.BadZipFile as e:
        return Problem("corrupt", path, str(e))
    except ET.ParseError as e:
        return Problem("gamelist", path, str(e))
    except OSError as e:
        return Problem("unreadable", path, e.strerror or str(e))
    except (RuntimeError, ValueError):  # NotImplementedError compris
        return None  # archive chiffrée ou compression inconnue : impossible à vérifier, pas une erreur
    return Problem("slow", path) if slow else None


def check(root, report=None, cancel=None):
    """Vérifie toute la carte. report(octets lus, total, chemin) suit l'avancement."""
    items = card_files(root)
    result = Result(total=sum(max(s, 0) for _p, s in items))
    start = time.monotonic()
    for path, size in items:
        if cancel is not None and cancel.is_set():
            result.cancelled = True
            break
        if report:
            report(result.read, result.total, path)
        problem = check_file(path, size)
        if problem:
            result.problems.append(problem)
        result.read += max(size, 0)
        result.files += 1
    result.seconds = time.monotonic() - start
    return result
