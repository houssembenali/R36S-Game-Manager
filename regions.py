"""Région et langues d'un jeu, lues dans les étiquettes du nom de fichier (norme No-Intro / Redump).

  « Zelda (USA, Europe) (En,Fr,De).zip » -> régions [us, eu], langues [En, Fr, De]
Pour ajouter une région : une entrée dans REGIONS (+ son drapeau dans icons.FLAGS si besoin).
"""
import re

# étiquette (minuscules) -> code ; le code sert aussi de nom de drapeau dans icons.FLAGS
ALIASES = {
    "usa": "us", "u": "us", "us": "us", "america": "us",
    "europe": "eu", "eu": "eu", "eur": "eu", "e": "eu", "pal": "eu",
    "japan": "jp", "j": "jp", "jpn": "jp",
    "world": "world", "w": "world", "jue": "world", "ue": "world",
    "france": "fr", "f": "fr", "germany": "de", "g": "de", "spain": "es", "s": "es",
    "italy": "it", "i": "it", "uk": "gb", "united kingdom": "gb", "australia": "au",
    "brazil": "br", "korea": "kr", "k": "kr", "china": "cn", "taiwan": "tw", "hong kong": "cn",
    "asia": "asia", "canada": "ca", "netherlands": "nl", "sweden": "se",
}
REGIONS = {
    "us": "USA", "eu": "Europe", "jp": "Japon", "world": "Universel", "fr": "France", "de": "Allemagne",
    "es": "Espagne", "it": "Italie", "gb": "Royaume-Uni", "au": "Australie", "br": "Brésil", "kr": "Corée",
    "cn": "Chine", "tw": "Taïwan", "asia": "Asie", "ca": "Canada", "nl": "Pays-Bas", "se": "Suède",
}
LANGUAGES = {
    "en": "Anglais", "fr": "Français", "de": "Allemand", "es": "Espagnol", "it": "Italien",
    "nl": "Néerlandais", "pt": "Portugais", "sv": "Suédois", "no": "Norvégien", "da": "Danois",
    "fi": "Finnois", "ja": "Japonais", "pl": "Polonais", "zh": "Chinois", "ko": "Coréen", "ru": "Russe",
    "ca": "Catalan", "el": "Grec", "tr": "Turc", "cs": "Tchèque", "hu": "Hongrois",
}


def _tags(name):
    return re.findall(r"\(([^()]*)\)", name)


def regions(name):
    """Codes de région trouvés dans le nom (ordre conservé, sans doublon)."""
    out = []
    for tag in _tags(name):
        for part in re.split(r"\s*,\s*", tag):
            code = ALIASES.get(part.strip().lower())
            if code and code not in out:
                out.append(code)
    return out


def languages(name):
    """Codes de langue : « (En,Fr,De) », « (EnFrDeEsIt) » ou « (Es+En) »."""
    out = []
    for tag in _tags(name):
        parts = re.split(r"\s*[,+]\s*", tag)
        if len(parts) == 1 and re.fullmatch(r"(?:[A-Z][a-z]){2,}", tag):
            parts = re.findall(r"[A-Z][a-z]", tag)  # « EnFrDeEsIt » collé
        codes = [p.lower() for p in parts]
        if codes and all(c in LANGUAGES for c in codes):
            out += [c for c in codes if c not in out]
    return out


def describe(name):
    """(codes région, texte des régions, texte des langues)."""
    codes = regions(name)
    return (codes, ", ".join(REGIONS[c] for c in codes),
            ", ".join(LANGUAGES[c] for c in languages(name)))
