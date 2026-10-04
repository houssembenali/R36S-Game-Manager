"""Passer à une nouvelle carte SD : copie de toute la partition EASYROMS sur le PC, puis sur la carte neuve.

La copie est incrémentale : un fichier déjà copié (même taille, même date) n'est pas recopié, on peut
donc l'arrêter et la reprendre. Rien n'est jamais supprimé à l'arrivée. Chaque fichier passe par un
fichier .part : une copie interrompue ne laisse jamais de fichier à moitié écrit.
"""
import os
import shutil

import health

BACKUP_NAME = "R36S EASYROMS"


def plan(src, dst):
    """[(source, destination, taille)] des fichiers à copier de src vers dst (hors corbeille du programme)."""
    out = []
    for path, size in health.card_files(src):
        if size < 0:
            continue
        target = os.path.join(dst, os.path.relpath(path, src))
        try:
            st = os.stat(target)
            if st.st_size == size and abs(st.st_mtime - os.path.getmtime(path)) <= 2:
                continue  # déjà copié
        except OSError:
            pass
        out.append((path, target, size))
    return out


def copy(items, report=None, cancel=None):
    """Copie les fichiers prévus. report(octets copiés, chemin). Retourne (copiés, erreurs)."""
    done, copied, errors = 0, 0, []
    for src, dst, size in items:
        if cancel is not None and cancel.is_set():
            break
        if report:
            report(done, src)
        part = dst + ".part"
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, part)
            shutil.copystat(src, part)
            os.replace(part, dst)
            copied += 1
        except OSError as e:
            errors.append(f"{src} : {e.strerror or e}")
            if os.path.exists(part):
                os.remove(part)
        done += size
    return copied, errors
