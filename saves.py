"""Sauvegarde et restauration des parties (fichiers .srm, .state, sauvegardes PSP…) sur le PC."""
import os
import zipfile

import core
import journal

# dossiers dont tout le contenu est une sauvegarde (PPSSPP)
SAVE_TREES = {"savedata", "ppsspp_state"}
SKIP_SYSTEMS = {"ports"}  # les ports gardent leurs sauvegardes dans leurs propres dossiers


def collect(root):
    """Tous les fichiers de sauvegarde de la carte (chemins absolus)."""
    out = []
    for system in core.list_systems(root):
        if system.lower() in SKIP_SYSTEMS:
            continue
        for dirpath, dirnames, files in os.walk(os.path.join(root, system)):
            dirnames[:] = [d for d in dirnames if d.lower() not in core.MEDIA_DIRS]
            in_tree = any(part.lower() in SAVE_TREES for part in dirpath.split(os.sep))
            out += [os.path.join(dirpath, f) for f in files if in_tree or core.SAVE_RE.search(f)]
    return out


def backup(root, files, dest_zip, report=None, cancel=None):
    """Copie les sauvegardes dans un .zip (chemins relatifs à la carte). Retourne le nombre copié."""
    count = 0
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for i, f in enumerate(files):
            if cancel is not None and cancel.is_set():
                break
            if report and i % 5 == 0:
                report(i, os.path.relpath(f, root))
            z.write(f, os.path.relpath(f, root))
            count += 1
    return count


def restore(root, src_zip, overwrite, report=None, cancel=None):
    """Remet les sauvegardes d'un .zip sur la carte. Retourne (restaurées, ignorées)."""
    restored = skipped = 0
    with zipfile.ZipFile(src_zip) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        for i, m in enumerate(members):
            if cancel is not None and cancel.is_set():
                break
            target = os.path.normpath(os.path.join(root, m.filename))
            if not target.startswith(os.path.normpath(root)):  # chemin suspect : ignoré
                skipped += 1
                continue
            if os.path.exists(target) and not overwrite:
                skipped += 1
                continue
            if report and i % 5 == 0:
                report(i, m.filename)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            data = z.read(m)

            def write(path, data=data):
                with open(path, "wb") as f:
                    f.write(data)
            journal.write_file(target, write)  # une sauvegarde remplacée reste récupérable
            restored += 1
    return restored, skipped


def zip_count(src_zip):
    with zipfile.ZipFile(src_zip) as z:
        return sum(1 for m in z.infolist() if not m.is_dir())
