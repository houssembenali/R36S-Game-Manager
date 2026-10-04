"""Historique des opérations et corbeille : tout ce que le programme fait sur la carte s'annule.

Pendant une opération (voir operation()), aucune donnée n'est effacée définitivement :
  remove(p)        le fichier/dossier part dans la corbeille
  move(a, b)       le déplacement est noté
  copy(a, b)       la copie est notée (l'éventuel fichier écrasé part dans la corbeille)
  before_write(p)  appelé AVANT de réécrire un fichier existant (gamelist.xml, .m3u…) : copie de sauvegarde
  created(p)       appelé APRÈS avoir créé un fichier
Le journal est enregistré sur la carte (<carte>/.r36s-corbeille/<id>/journal.json), donc une
opération peut être annulée même après avoir fermé le programme. Hors opération, ces fonctions
agissent directement (suppression définitive).

Toutes les écritures sur la carte doivent passer par ce module.
"""
import contextlib
import datetime
import json
import os
import shutil
import threading

TRASH = ".r36s-corbeille"
KEEP = 10  # nombre d'opérations gardées (les plus anciennes sont purgées)

_local = threading.local()


class Operation:
    def __init__(self, root, label):
        self.root = root
        self.label = label
        self.id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.dir = os.path.join(root, TRASH, self.id)
        self.actions = []
        self.backed_up = set()

    def trash_path(self, path, sub="files"):
        return os.path.join(self.dir, sub, os.path.relpath(path, self.root))

    def save(self):
        if not self.actions:
            shutil.rmtree(self.dir, ignore_errors=True)
            return
        os.makedirs(self.dir, exist_ok=True)
        data = {"label": self.label, "date": datetime.datetime.now().isoformat(timespec="seconds"),
                "actions": [[kind] + [os.path.relpath(p, self.root) for p in paths]
                            for kind, *paths in self.actions]}
        with open(os.path.join(self.dir, "journal.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)


def current():
    return getattr(_local, "op", None)


@contextlib.contextmanager
def operation(root, label):
    """Regroupe les modifications faites dans le bloc en une opération annulable."""
    if current() is not None:  # opération imbriquée : on reste dans la première
        yield current()
        return
    _purge_old(root)
    op = Operation(root, label)
    _local.op = op
    try:
        yield op
    finally:
        _local.op = None
        op.save()


# ---------------------------------------------------------------- écritures

def _delete(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.remove(path)


def remove(path):
    op = current()
    if op is None:
        return _delete(path)
    dest = op.trash_path(path)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.lexists(dest):
        _delete(dest)
    shutil.move(path, dest)
    op.actions.append(("removed", path, dest))


def move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)
    op = current()
    if op is not None:
        op.actions.append(("moved", src, dst))


def copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    existed = os.path.exists(dst)
    if existed:
        before_write(dst)
    shutil.copy2(src, dst)
    if not existed:
        created(dst)


def before_write(path):
    op = current()
    if op is None or not os.path.isfile(path) or os.path.normcase(path) in op.backed_up:
        return
    dest = op.trash_path(path, "modified")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(path, dest)
    op.backed_up.add(os.path.normcase(path))
    op.actions.append(("modified", path, dest))


def created(path):
    op = current()
    if op is not None:
        op.actions.append(("created", path))


def write_file(path, writer):
    """Écrit un fichier via writer(chemin) en le rendant annulable (création ou modification)."""
    existed = os.path.exists(path)
    if existed:
        before_write(path)
    writer(path)
    if not existed:
        created(path)


# ---------------------------------------------------------------- historique

def history(root):
    """[(id, libellé, date, taille dans la corbeille)] du plus récent au plus ancien."""
    base = os.path.join(root, TRASH)
    out = []
    if not os.path.isdir(base):
        return out
    for op_id in sorted(os.listdir(base), reverse=True):
        meta = os.path.join(base, op_id, "journal.json")
        try:
            with open(meta, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        out.append((op_id, data["label"], data["date"], _size(os.path.join(base, op_id))))
    return out


def trash_size(root):
    return _size(os.path.join(root, TRASH))


def _size(path):
    total = 0
    for dirpath, _x, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def undo(root, op_id):
    """Défait une opération (en sens inverse). Retourne la liste des erreurs."""
    op_dir = os.path.join(root, TRASH, op_id)
    with open(os.path.join(op_dir, "journal.json"), encoding="utf-8") as f:
        actions = json.load(f)["actions"]
    errors = []
    for kind, *paths in reversed(actions):
        a, b = [os.path.join(root, p) for p in paths] + [None] * (2 - len(paths))
        try:
            if kind == "created" and os.path.lexists(a):
                _delete(a)
            elif kind == "moved" and os.path.lexists(b) and not os.path.lexists(a):
                os.makedirs(os.path.dirname(a), exist_ok=True)
                shutil.move(b, a)
            elif kind == "removed" and os.path.lexists(b):
                os.makedirs(os.path.dirname(a), exist_ok=True)
                if os.path.lexists(a):
                    _delete(a)
                shutil.move(b, a)
            elif kind == "modified" and os.path.isfile(b):
                shutil.copy2(b, a)
        except OSError as e:
            errors.append(f"{paths[0]} : {e}")
    shutil.rmtree(op_dir, ignore_errors=True)
    return errors


def empty_trash(root):
    """Vide la corbeille : libère la place, mais plus aucune opération ne pourra être annulée."""
    shutil.rmtree(os.path.join(root, TRASH), ignore_errors=True)


def _purge_old(root):
    for op_id, *_x in history(root)[KEEP - 1:]:
        shutil.rmtree(os.path.join(root, TRASH, op_id), ignore_errors=True)
