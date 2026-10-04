"""Traduction : aucun texte oublié, mêmes {champs} en français et en anglais, pas de variable « _ »."""
import ast
import glob
import os
import string

import bios
import filters
import i18n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = sorted(glob.glob(os.path.join(ROOT, "*.py")))


def _trees():
    for path in SOURCES:
        with open(path, encoding="utf-8") as f:
            yield os.path.basename(path), ast.parse(f.read())


def translated_texts():
    """Textes français passés à _() et _n() dans le code (hors textes calculés)."""
    texts = set()
    for _name, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("_", "_n"):
                args = node.args[:1] if node.func.id == "_" else node.args[1:3]
                texts |= {a.value for a in args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    # textes traduits indirectement (listes de choix, niveaux de BIOS)
    texts |= set(filters.PLAYERS) | {bios.REQUIRED, bios.RECOMMENDED, bios.OPTIONAL}
    return texts


def fields(text):
    return {f for _lit, f, _spec, _conv in string.Formatter().parse(text) if f}


def test_every_text_has_an_english_translation():
    missing = sorted(t for t in translated_texts() if t not in i18n.EN)
    assert missing == [], "Textes sans traduction anglaise (à ajouter dans i18n.EN) :\n" + "\n".join(missing)


def test_translations_keep_the_same_fields():
    wrong = [(fr, en) for fr, en in i18n.EN.items() if fields(fr) != fields(en)]
    assert wrong == []


def test_no_variable_named_underscore():
    """« _ » est la fonction de traduction : l'utiliser comme variable la casserait dans la fonction."""
    bad = []
    for name, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "_" and isinstance(node.ctx, ast.Store):
                bad.append(f"{name}:{node.lineno}")
            if isinstance(node, ast.arg) and node.arg == "_":
                bad.append(f"{name}:{node.lineno}")
    assert bad == [], "Variable « _ » (renommer en _x) : " + ", ".join(bad)


def test_plurals_and_language_switch():
    old = i18n.LANG
    try:
        i18n.set_language("fr")
        assert i18n._n(0, "{n} jeu", "{n} jeux") == "0 jeu"
        assert i18n._n(2, "{n} jeu", "{n} jeux") == "2 jeux"
        i18n.set_language("en")
        assert i18n._n(0, "{n} jeu", "{n} jeux") == "0 games"
        assert i18n._n(1, "{n} jeu", "{n} jeux") == "1 game"
        assert i18n._("Lecture de {drive} …", drive="E:") == "Reading E: …"
        assert i18n._("texte inconnu") == "texte inconnu"  # pas de traduction : texte d'origine
    finally:
        i18n.set_language(old)


def test_plural_forms_are_distinct():
    """_n(n, singulier, pluriel) : deux textes différents, sinon la traduction ne peut pas les distinguer."""
    same = []
    for name, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_n":
                one, many = node.args[1:3]
                if isinstance(one, ast.Constant) and isinstance(many, ast.Constant) and one.value == many.value:
                    same.append(f"{name}:{node.lineno} {one.value!r}")
    assert same == []
