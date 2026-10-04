"""Traduction de l'interface (français / anglais).

Dans le code, les textes restent écrits en français, entourés de _() :
    _("Fiche enregistrée")                         -> « Card saved » en anglais
    _("Lecture de {drive} …", drive="E:")          -> les {champs} sont remplis après traduction
    _n(n, "{n} jeu supprimé", "{n} jeux supprimés") -> choisit le singulier ou le pluriel
Pour traduire un nouveau texte : ajouter sa version anglaise dans EN (en bas du fichier).
Le test tests/test_i18n.py signale tout texte oublié.

La langue est choisie au démarrage (réglage « language », sinon langue du système) ;
la changer demande de relancer le programme.
"""
import locale

import settings

LANGUAGES = {"fr": "Français", "en": "English"}


def _system_language():
    try:
        name = (locale.getlocale()[0] or "").lower()
    except ValueError:
        name = ""
    return "fr" if name.startswith("fr") or name.startswith("french") else "en"


LANG = settings.get("language") if settings.get("language") in LANGUAGES else _system_language()


def set_language(code):
    global LANG
    LANG = code


def _(text, **fields):
    if LANG == "en":
        text = EN.get(text, text)
    return text.format(**fields) if fields else text


def _n(n, one, many, **fields):
    """Singulier / pluriel. Français : 0 et 1 au singulier ; anglais : seulement 1."""
    single = n <= 1 if LANG == "fr" else n == 1
    return _(one if single else many, n=n, **fields)


EN = {
    # --- barre d'état / astuces
    "Clic : sélectionner": "Click: select",
    "Ctrl/Maj + clic : sélection multiple": "Ctrl/Shift + click: multiple selection",
    "F ou ★ : favori": "F or ★: favorite",
    "Suppr : supprimer": "Del: delete",
    "Double-clic : ouvrir le dossier": "Double-click: open folder",
    "Ctrl+F : rechercher": "Ctrl+F: search",
    "ASTUCES": "TIPS",
    # --- tris, légende, unités
    "Nom A → Z": "Name A → Z", "Nom Z → A": "Name Z → A", "Mieux notés": "Top rated",
    "Plus joués": "Most played", "Derniers joués": "Recently played", "Plus gros": "Largest",
    "Plus petits": "Smallest", "Système": "System", "Jeux": "Games", "Images": "Images",
    "Vidéos": "Videos", "Corbeille": "Trash", "o Ko Mo Go To": "B KB MB GB TB",
    "CARTE SD": "SD CARD", "{free} libres / {total}": "{free} free / {total}",
    # --- dates et parties
    "Jamais joué": "Never played", "{n} partie": "{n} play", "{n} parties": "{n} plays", "aujourd'hui": "today", "hier": "yesterday",
    "il y a {n} jour": "{n} day ago", "il y a {n} jours": "{n} days ago",
    "il y a un mois": "a month ago", "il y a {n} mois": "{n} months ago", "il y a {n} an": "{n} year ago", "il y a {n} ans": "{n} years ago",
    "janv. févr. mars avr. mai juin juil. août sept. oct. nov. déc.":
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec",
    # --- en-tête et boutons
    "Relire la carte (F5)": "Reload the card (F5)", "Rien à annuler": "Nothing to undo",
    "Nettoyer la carte : médias orphelins, fiches sans jeu, jeux mal rangés…":
        "Clean up the card: orphan media, entries without a game, misplaced games…",
    "Ajouter des jeux depuis le PC (ou glisse-les dans la fenêtre)":
        "Add games from your PC (or drag them into the window)",
    "OUTILS": "TOOLS", "SUPPRIMER": "DELETE", "DOSSIER": "FOLDER", "FAVORI": "FAVORITE",
    "FILTRES": "FILTERS", "IMAGES": "IMAGES", "IMAGES OK": "IMAGES OK",
    "Télécharger depuis internet les images des jeux affichés qui n'en ont pas":
        "Download images from the internet for the displayed games that have none",
    "RETIRER DES FAVORIS": "REMOVE FAVORITE", "AJOUTER AUX FAVORIS": "ADD TO FAVORITES",
    "DANS LES FAVORIS": "IN FAVORITES", "Modifier la fiche (F2)": "Edit game card (F2)",
    "Supprimer aussi les sauvegardes": "Also delete save files",
    # --- liste des systèmes / jeux
    "Systèmes": "Systems", "Tous les jeux": "All games", "Favoris": "Favorites", "Doublons": "Duplicates",
    "{n} jeu": "{n} game", "{n} jeux": "{n} games", "recherche « {query} »": "search “{query}”",
    "{n} filtre": "{n} filter", "{n} filtres": "{n} filters",
    "{n} jeu sélectionné": "{n} game selected", "{n} jeux sélectionnés": "{n} games selected",
    "Sélectionne un jeu": "Select a game", "Aucun jeu": "No games",
    # --- filtres
    "GENRE": "GENRE", "JOUEURS": "PLAYERS", "RÉGION": "REGION", "Sans image": "No image",
    "Sans note": "No rating", "Effacer les filtres": "Clear filters", "Tous": "All", "Toutes": "All",
    "1 joueur": "1 player", "2 joueurs et +": "2+ players", "3 joueurs et +": "3+ players",
    "4 joueurs et +": "4+ players",
    # --- vue liste / fiche
    "NOTE": "RATING", "FICHIER": "FILE", "TAILLE": "SIZE", "NOM": "NAME", "VERSION": "VERSION",
    "LANGUES": "LANGUAGES", "PARTIES": "PLAYS", "DERNIÈRE": "LAST PLAYED", "ANNÉE": "YEAR",
    "DÉV.": "DEV.", "ÉDITEUR": "PUBLISHER",
    "Ce jeu n'est pas dans le gamelist.xml (pas de fiche).": "This game is not in gamelist.xml (no game card).",
    "Fichiers supprimés avec ce jeu": "Files deleted with this game",
    # --- lecture de la carte
    "Lecture de {drive} …": "Reading {drive} …",
    "{n} jeu chargé depuis {drive}": "{n} game loaded from {drive}",
    "{n} jeux chargés depuis {drive}": "{n} games loaded from {drive}",
    "Erreur": "Error", "Erreurs": "Errors", "Impossible de lire {drive} :": "Cannot read {drive}:",
    "Partition non reconnue": "Unrecognized partition",
    "{drive} ne ressemble pas à une carte ArkOS : aucun dossier de console (gba, psx, nes, bios…) n'y a été "
    "trouvé.\nChoisis la partition EASYROMS de ta carte SD.":
        "{drive} doesn't look like an ArkOS card: no console folder (gba, psx, nes, bios…) was found.\n"
        "Choose the EASYROMS partition of your SD card.",
    "CHARGER QUAND MÊME": "LOAD ANYWAY",
    "Aucun jeu trouvé sur {drive}.\nEst-ce bien la partition EASYROMS ?":
        "No games found on {drive}.\nIs this really the EASYROMS partition?",
    # --- opérations
    "Préparation…": "Preparing…", "L'opération a échoué :": "The operation failed:",
    "Analyse": "Scan", "Analyse de la carte…": "Scanning the card…", "Nettoyage": "Cleanup",
    "Nettoyage de la carte": "Card cleanup", "Nettoyage terminé : {n} élément": "Cleanup done: {n} item",
    "Nettoyage terminé : {n} éléments": "Cleanup done: {n} items",
    "{size} dans la corbeille": "{size} in the trash",
    "Certains éléments n'ont pas pu être nettoyés :": "Some items could not be cleaned:",
    "Images manquantes": "Missing images", "Images téléchargées": "Images downloaded",
    "Recherche : {name}": "Searching: {name}", "Mise à jour des gamelist.xml…": "Updating gamelist.xml…",
    "{n} jeu sur {total} a maintenant une image.": "{n} game out of {total} now has an image.",
    "{n} jeux sur {total} ont maintenant une image.": "{n} games out of {total} now have an image.",
    "Introuvables sur libretro-thumbnails ({count}) :": "Not found on libretro-thumbnails ({count}):",
    "Ajout aux favoris": "Add to favorites", "Retrait des favoris": "Remove from favorites",
    "{n} jeu ajouté aux favoris": "{n} game added to favorites",
    "{n} jeux ajoutés aux favoris": "{n} games added to favorites",
    "{n} jeu retiré des favoris": "{n} game removed from favorites",
    "{n} jeux retirés des favoris": "{n} games removed from favorites",
    "Les favoris n'ont pas pu être enregistrés :": "Favorites could not be saved:",
    "ROM, images, vidéos, sauvegardes": "ROM, images, videos, saves", "ROM, images, vidéos": "ROM, images, videos",
    "{n} jeu va être supprimé de la carte SD.": "{n} game will be deleted from the SD card.",
    "{n} jeux vont être supprimés de la carte SD.": "{n} games will be deleted from the SD card.",
    "{files} fichiers · {size} ({what}).": "{files} files · {size} ({what}).",
    "Ils passent par la corbeille : tu pourras annuler. Vide la corbeille pour libérer la place.":
        "They go to the trash, so you can undo. Empty the trash to free the space.",
    "Suppression": "Deleting", "Suppression : {name}": "Deleting: {name}",
    "Suppression de {n} jeu": "Delete {n} game", "Suppression de {n} jeux": "Delete {n} games",
    "{n} jeu supprimé": "{n} game deleted", "{n} jeux supprimés": "{n} games deleted",
    "Certains fichiers n'ont pas pu être supprimés :": "Some files could not be deleted:",
    "Supprimer ?": "Delete?",
    # --- compression / outils internes
    "Installe chdman avec ton gestionnaire de paquets (ex. : sudo apt install mame-tools)":
        "Install chdman with your package manager (e.g. sudo apt install mame-tools)",
    "7-Zip est nécessaire pour extraire chdman (https://www.7-zip.org)":
        "7-Zip is required to extract chdman (https://www.7-zip.org)",
    "chdman.exe introuvable dans l'archive MAME": "chdman.exe not found in the MAME archive",
    "{file} existe déjà": "{file} already exists", "Téléchargement annulé": "Download cancelled",
    "Extraction de chdman…": "Extracting chdman…", "Conversion annulée": "Conversion cancelled",
    "échec de chdman": "chdman failed",
    "Téléchargement de MAME : {done} / {total} Mo": "Downloading MAME: {done} / {total} MB",
    "{file} : existe déjà dans {system}": "{file}: already exists in {system}",
    "Copie : {file}": "Copying: {file}",
    # --- nettoyage
    "Médias orphelins": "Orphan media",
    "Images, vidéos et manuels de jeux qui ne sont plus sur la carte.":
        "Images, videos and manuals of games that are no longer on the card.",
    "Fiches sans jeu": "Entries without a game",
    "Entrées du gamelist.xml dont la ROM a été supprimée.": "gamelist.xml entries whose ROM was deleted.",
    "Sauvegardes sans jeu": "Saves without a game",
    "Sauvegardes (.srm, .state…) de jeux qui ne sont plus sur la carte.":
        "Save files (.srm, .state…) of games that are no longer on the card.",
    "Jeux dans le mauvais dossier": "Games in the wrong folder",
    "ROM dont le format ne correspond pas à la console du dossier : la console ne la lancera pas.":
        "ROMs whose format doesn't match the folder's console: the console won't launch them.",
    "Anciennes copies de gamelist": "Old gamelist copies",
    "plutôt pour : {systems}": "rather for: {systems}",
    "format non pris en charge par cette console": "format not supported by this console",
    "NETTOYER": "CLEAN UP", "Voir le détail": "Show details", "Masquer le détail": "Hide details",
    "Rien de coché": "Nothing checked", "{n} élément à nettoyer": "{n} item to clean",
    "{n} éléments à nettoyer": "{n} items to clean", "{title} : rien à nettoyer": "{title}: nothing to clean",
    "{size} libérés": "{size} freed",
    # --- fenêtres
    "Ajouter des jeux": "Add games", "AJOUTER": "ADD", "Recherche…": "Searching…",
    "Modifier la fiche": "Edit game card", "ENREGISTRER": "SAVE",
    "Historique et corbeille": "History & trash",
    "Les fichiers supprimés ou remplacés sont gardés dans une corbeille cachée sur la carte : on peut annuler "
    "la dernière opération, puis la précédente… Vider la corbeille libère la place mais rend ces opérations "
    "définitives.":
        "Deleted or replaced files are kept in a hidden trash on the card: you can undo the last operation, "
        "then the one before… Emptying the trash frees the space but makes these operations permanent.",
    "Aucune opération à annuler.": "No operation to undo.", "ANNULER LA DERNIÈRE": "UNDO LAST",
    "CONSOLE": "CONSOLE", "pas assez de place ({free} libres)": "not enough space ({free} free)",
    "Choisir une image": "Choose an image", "Presse-papiers sans image": "No image in the clipboard",
    "IMAGE (fiche du jeu)": "IMAGE (game details)", "JAQUETTE (vue grille)": "BOX ART (grid view)",
    "Effacer": "Clear", "ANNULER": "CANCEL", "Tout": "All", "Rien": "None",
    "{n} sélectionné": "{n} selected", "{n} sélectionnés": "{n} selected",
    "Compléter ensuite les fiches depuis internet (image, description, année, genre…)":
        "Then complete the game cards from the internet (image, description, year, genre…)",
    "à choisir": "to choose", "{n} jeu sans console": "{n} game without a console",
    "{n} jeux sans console": "{n} games without a console",
    "COLLER": "PASTE", "INTERNET": "INTERNET", "RETIRER": "REMOVE",
    "Fichier non reconnu comme image": "File is not a recognized image", "VIDER LA CORBEILLE": "EMPTY TRASH",
    "FERMER": "CLOSE",
    "Vérifie la console de chaque jeu. Sélectionne une ou plusieurs lignes pour changer leur console.":
        "Check each game's console. Select one or more rows to change their console.",
    "Console de la sélection :": "Console for the selection:", "Aucune image": "No image",
    "Tous les fichiers": "All files", "Introuvable sur internet": "Not found on the internet",
    "DESCRIPTION": "DESCRIPTION",
    "Nom": "Name", "Année": "Year", "Genre": "Genre", "Développeur": "Developer", "Éditeur": "Publisher",
    "Joueurs": "Players",
    # --- menus
    "Ajouter des jeux…": "Add games…", "Compléter les fiches incomplètes…": "Complete incomplete game cards…",
    "Regrouper les jeux multi-disques…": "Merge multi-disc games…",
    "Compresser les jeux CD en CHD…": "Compress CD games to CHD…", "Supprimer des vidéos…": "Delete videos…",
    "Nettoyer la carte…": "Clean up the card…", "Sauvegarder mes parties sur le PC…": "Back up my saves to the PC…",
    "Restaurer des parties…": "Restore saves…", "Vérifier les BIOS…": "Check BIOS files…",
    "Historique et corbeille…": "History & trash…", "Langue": "Language",
    "Ouvrir le dossier": "Open folder", "Modifier la fiche…": "Edit game card…",
    "Retirer des favoris": "Remove from favorites", "Ajouter aux favoris": "Add to favorites",
    "Compléter la fiche depuis internet": "Complete the game card from the internet",
    "Déplacer vers": "Move to", "Supprimer…": "Delete…",
    "La langue sera changée au redémarrage du programme.": "The language will change when the program restarts.",
    "PLUS TARD": "LATER", "REDÉMARRER": "RESTART",
    # --- actions des outils
    "Certaines opérations ont échoué :": "Some operations failed:",
    "Fiche modifiée : {name}": "Card edited: {name}", "Fiche enregistrée": "Game card saved",
    "Déplacement": "Moving", "Déplacement : {name}": "Moving: {name}",
    "Déplacement vers {system}": "Move to {system}",
    "{n} jeu déplacé vers {system}": "{n} game moved to {system}",
    "{n} jeux déplacés vers {system}": "{n} games moved to {system}",
    "Choisir des jeux à ajouter": "Choose games to add",
    "Aucun jeu reconnu dans ce qui a été déposé.": "No games recognized in what was dropped.",
    "Ajout de jeux": "Adding games", "Ajout de {n} jeu": "Add {n} game", "Ajout de {n} jeux": "Add {n} games",
    "{n} jeu ajouté": "{n} game added", "{n} jeux ajoutés": "{n} games added",
    "Certains jeux n'ont pas été ajoutés :": "Some games were not added:",
    "Ces fiches sont déjà complètes": "These game cards are already complete",
    "Fiches depuis internet": "Game cards from the internet",
    "{n} fiche complétée": "{n} game card completed", "{n} fiches complétées": "{n} game cards completed",
    "rien trouvé pour {n} jeu": "nothing found for {n} game",
    "rien trouvé pour {n} jeux": "nothing found for {n} games",
    "Fiches complétées ({n} jeu)": "Game cards completed ({n} game)",
    "Fiches complétées ({n} jeux)": "Game cards completed ({n} games)",
    "Fiches": "Game cards",
    "Toutes les fiches ont une description, une année, un genre et une image.":
        "Every game card has a description, a year, a genre and an image.",
    "description": "description", "année": "year", "genre": "genre", "image": "image",
    "manque : {list}": "missing: {list}", "Compléter les fiches": "Complete game cards",
    "Cherche sur internet (base libretro, Wikidata, Wikipédia, images libretro) ce qui manque à ces fiches. "
    "Rien n'est écrasé. Compter quelques secondes par jeu ; un jeu introuvable est simplement passé.":
        "Searches the internet (libretro database, Wikidata, Wikipedia, libretro images) for what these game "
        "cards are missing. Nothing is overwritten. Allow a few seconds per game; a game that can't be found "
        "is simply skipped.",
    "COMPLÉTER": "COMPLETE", "Multi-disques": "Multi-disc",
    "Aucun jeu en plusieurs disques à regrouper.": "No multi-disc games to merge.",
    "{n} disque": "{n} disc", "{n} disques": "{n} discs", "Jeux multi-disques": "Multi-disc games",
    "Chaque jeu sélectionné n'apparaîtra plus qu'une seule fois sur la console. Les disques sont rangés dans "
    "un dossier caché « .multidisc » et on change de disque depuis le menu RetroArch (Hotkey + X → Contrôle "
    "du disque).":
        "Each selected game will appear only once on the console. The discs are moved to a hidden “.multidisc” "
        "folder and you switch discs from the RetroArch menu (Hotkey + X → Disc Control).",
    "REGROUPER": "MERGE", "Regroupement : {name}": "Merging: {name}",
    "Regroupement multi-disques": "Merge multi-disc games",
    "{n} jeu regroupé": "{n} game merged", "{n} jeux regroupés": "{n} games merged",
    "Il n'y a aucune vidéo de présentation sur la carte.": "There are no preview videos on the card.",
    "{n} vidéo": "{n} video", "{n} vidéos": "{n} videos", "Supprimer des vidéos": "Delete videos",
    "Les vidéos de présentation ne servent qu'à l'aperçu dans la liste des jeux. Les jeux, images et "
    "sauvegardes ne sont pas touchés.":
        "Preview videos are only used for the preview in the game list. Games, images and saves are not touched.",
    "Vidéos : {system}": "Videos: {system}", "Suppression des vidéos": "Delete videos",
    "Vidéos supprimées": "Videos deleted",
    "Aucun jeu CD au format .cue / .gdi à compresser.": "No .cue / .gdi CD games to compress.",
    "  (disque {n})": "  (disc {n})",
    "L'outil chdman (MAME) sera téléchargé automatiquement la première fois (≈ 85 Mo).":
        "The chdman tool (MAME) will be downloaded automatically the first time (≈ 85 MB).",
    "Compression CHD": "CHD compression",
    "Compresse les jeux CD sans perte au format .chd, lu directement par la console : on gagne souvent 30 à "
    "60 % de place. Compter environ une minute par jeu. Les sauvegardes restent valables.":
        "Losslessly compresses CD games to .chd, read directly by the console: you often save 30 to 60 % of "
        "space. Allow about one minute per game. Save files remain valid.",
    "COMPRESSER": "COMPRESS", "Compression : {name}": "Compressing: {name}",
    "Compression terminée": "Compression done", "{size} compressés": "{size} compressed",
    "Certains jeux n'ont pas pu être compressés :": "Some games could not be compressed:",
    "Sauvegardes": "Saves", "Aucune sauvegarde trouvée sur la carte.": "No save files found on the card.",
    "sauvegardes": "saves", "Enregistrer les sauvegardes": "Save the backups", "Archive zip": "Zip archive",
    "{n} sauvegarde copiée dans {file}": "{n} save copied to {file}",
    "{n} sauvegardes copiées dans {file}": "{n} saves copied to {file}",
    "{n} fichier de sauvegarde a été copié dans :\n{file}": "{n} save file was copied to:\n{file}",
    "{n} fichiers de sauvegarde ont été copiés dans :\n{file}": "{n} save files were copied to:\n{file}",
    "Sauvegarde des parties": "Backing up saves",
    "Choisir une sauvegarde à restaurer": "Choose a backup to restore", "Restaurer": "Restore",
    "Que faire si une sauvegarde existe déjà sur la carte ?": "What if a save already exists on the card?",
    "GARDER CELLE DE LA CARTE": "KEEP THE CARD'S ONE", "REMPLACER": "REPLACE",
    "Restauration": "Restore", "Restauration des parties": "Restore saves",
    "{n} sauvegarde restaurée": "{n} save restored", "{n} sauvegardes restaurées": "{n} saves restored",
    "{n} sauvegarde restaurée, {skipped} ignorée(s).": "{n} save restored, {skipped} skipped.",
    "{n} sauvegardes restaurées, {skipped} ignorée(s).": "{n} saves restored, {skipped} skipped.",
    # --- annulation / corbeille
    "Annuler": "Undo", "Annuler : {label}": "Undo: {label}", "Annulation": "Undoing",
    "Défaire « {label} » ({when}) ?": "Undo “{label}” ({when})?",
    "Les fichiers et les fiches reviennent comme avant cette opération.":
        "Files and game cards go back to how they were before this operation.",
    "NON": "NO", "ANNULER L'OPÉRATION": "UNDO OPERATION", "Opération annulée : {label}": "Operation undone: {label}",
    "Certains éléments n'ont pas pu être remis en place :": "Some items could not be restored:",
    "Vider la corbeille": "Empty the trash", "{size} seront libérés sur la carte.": "{size} will be freed on the card.",
    "Les opérations passées ne pourront plus être annulées.": "Past operations can no longer be undone.",
    "VIDER": "EMPTY", "Corbeille vidée": "Trash emptied",
    # --- BIOS
    "BIOS": "BIOS", "Aucune de tes consoles n'a besoin de BIOS.": "None of your consoles needs a BIOS.",
    "Vérification des BIOS": "BIOS check", "Tout est en ordre pour tes consoles.": "Everything is fine for your consoles.",
    "{n} BIOS requis manquant : les jeux de ces consoles risquent de ne pas démarrer.":
        "{n} required BIOS missing: games for these consoles may not start.",
    "{n} BIOS requis manquants : les jeux de ces consoles risquent de ne pas démarrer.":
        "{n} required BIOS files missing: games for these consoles may not start.",
    "manquant": "missing", "un de ces fichiers dans bios/ : {files}": "one of these files in bios/: {files}",
    "requis": "required", "recommandé": "recommended", "optionnel": "optional",
    "Flash Dreamcast": "Dreamcast flash", "Carte système CD": "CD system card",
    "Carte système CD (jeux CD)": "CD system card (CD games)", "Extension MSX2": "MSX2 extension",
    # ports PortMaster
    "Dossiers de ports sans script": "Port folders without a script",
    "Dossiers de ports PortMaster dont le jeu a été supprimé (son script .sh n'existe plus). "
    "Ils peuvent contenir les fichiers d'un jeu que tu voudrais réinstaller.":
        "PortMaster port folders whose game was deleted (its .sh script no longer exists). "
        "They may hold the files of a game you would like to reinstall.",
    "Port PortMaster": "PortMaster port",
    "Prêt à jouer : aucun fichier à fournir.": "Ready to run: no files to provide.",
    "Ce port a besoin des fichiers du jeu original.": "This port needs the original game files.",
    "Le jeu original est payant.": "The original game is a paid game.",
    "Porté par : {names}": "Ported by: {names}",
    "Catalogue PortMaster": "PortMaster catalogue", "Catalogue PortMaster…": "PortMaster catalogue…",
    "Mises à jour des ports": "Port updates", "Mises à jour des ports…": "Port updates…",
    "Les ports cochés sont copiés dans ports/PortMaster/autoinstall : PortMaster les installe au prochain "
    "lancement sur la console. Les « prêts à jouer » fonctionnent tout de suite ; les autres demandent les "
    "fichiers du jeu original.":
        "Checked ports are copied to ports/PortMaster/autoinstall: PortMaster installs them the next time it is "
        "launched on the console. \"Ready to run\" ports work right away; the others need the original game files.",
    "Rechercher :": "Search:", "Prêts à jouer seulement": "Ready to run only", "Tous les genres": "All genres",
    "PORT": "PORT", "ÉTAT": "STATUS", "COCHER": "CHECK", "DÉCOCHER": "UNCHECK", "INSTALLER": "INSTALL",
    "en attente": "pending", "installé": "installed", "mise à jour": "update",
    "Mis à jour le {date}": "Updated on {date}", "Pas d'image": "No image", "Chargement…": "Loading…",
    "Tous les ports installés sont à jour.": "All installed ports are up to date.",
    "version du {date}": "version of {date}", "METTRE À JOUR": "UPDATE",
    "Une version plus récente de ces ports existe. La nouvelle version remplace l'ancienne au prochain "
    "lancement de PortMaster ; les fichiers du jeu et les sauvegardes sont gardés.":
        "A newer version of these ports exists. It replaces the old one the next time PortMaster is launched; "
        "game files and saves are kept.",
    "Téléchargement : {name}": "Downloading: {name}",
    "Certains téléchargements ont échoué :": "Some downloads failed:",
    "Ports PortMaster": "PortMaster ports",
    "{n} port est prêt à être installé.": "{n} port is ready to be installed.",
    "{n} ports sont prêts à être installés.": "{n} ports are ready to be installed.",
    "{n} bibliothèque nécessaire a aussi été ajoutée.": "{n} required library was also added.",
    "{n} bibliothèques nécessaires ont aussi été ajoutées.": "{n} required libraries were also added.",
    "Remets la carte dans la console et lance PortMaster (dans Ports ou Options) : il installe les ports "
    "déposés, qui apparaissent ensuite dans la liste Ports.":
        "Put the card back in the console and launch PortMaster (in Ports or Options): it installs the ports, "
        "which then appear in the Ports list.",
    "Installation des ports": "Installing ports",
    "Installation de {n} port": "Installing {n} port", "Installation de {n} ports": "Installing {n} ports",
    "Trier par :": "Sort by:", "Nom (A → Z)": "Name (A → Z)", "Nom (Z → A)": "Name (Z → A)",
    "Ajoutés récemment": "Recently added", "Ajoutés il y a longtemps": "Oldest first",
    "Mis à jour récemment": "Recently updated", "Plus petits d'abord": "Smallest first",
    "Plus gros d'abord": "Largest first", "Installés d'abord": "Installed first",
    "AJOUTÉ LE": "ADDED", "MIS À JOUR": "UPDATED",
    "Bibliothèques de ports inutilisées": "Unused port libraries",
    "Bibliothèques de PortMaster (runtimes .squashfs) qu'aucun port de la carte n'utilise. "
    "Le catalogue PortMaster les remet si un port installé plus tard en a besoin.":
        "PortMaster libraries (.squashfs runtimes) that no port on the card uses. "
        "The PortMaster catalogue adds them back if a port installed later needs them.",
    "bibliothèque manquante": "missing library",
    "Les bibliothèques manquantes sont nécessaires pour lancer des ports déjà installés.":
        "The missing libraries are needed to launch ports that are already installed.",
    "{n} bibliothèque ajoutée": "{n} library added", "{n} bibliothèques ajoutées": "{n} libraries added",
    "Installation de {n} bibliothèque": "Installing {n} library",
    "Installation de {n} bibliothèques": "Installing {n} libraries",
    "AJOUTER LES FICHIERS DU JEU…": "ADD GAME FILES…",
    "Copie les fichiers du jeu original (acheté ou téléchargé) dans le port":
        "Copies the original game files (bought or downloaded) into the port",
    "Ajouter les fichiers du jeu…": "Add game files…", "Fichiers du jeu": "Game files",
    "Les fichiers seront copiés dans {folder}.": "The files will be copied to {folder}.",
    "Choisis le dossier du jeu original (tout son contenu est copié) ou seulement certains fichiers, "
    "comme le demandent les instructions :":
        "Choose the original game folder (all its content is copied) or only some files, "
        "as the instructions say:",
    "FICHIERS…": "FILES…", "DOSSIER…": "FOLDER…",
    "Dossier du jeu original": "Original game folder", "Fichiers du jeu original": "Original game files",
    "{n} fichier copié": "{n} file copied", "{n} fichiers copiés": "{n} files copied",
    "Certains fichiers n'ont pas pu être copiés :": "Some files could not be copied:",
    "Fichiers du jeu : {name}": "Game files: {name}",
    "Gratuits et payants": "Free and paid", "Gratuits": "Free", "Payants": "Paid",
    "Adaptés à la R36S seulement": "Suited to the R36S only", "Nouveautés seulement": "New only",
    "nouveau": "new",
    "demande une console plus puissante": "needs a more powerful console",
    "demande 2 Go de mémoire (la R36S en a 1)": "needs 2 GB of memory (the R36S has 1)",
    "demande OpenGL": "needs OpenGL", "ne fonctionne pas sous ArkOS": "does not work on ArkOS",
    "Peut ne pas tourner sur la R36S : {reason}.": "May not run on the R36S: {reason}.",
    "Port expérimental : il peut mal fonctionner.": "Experimental port: it may not work well.",
    "VOIR SUR {store}": "VIEW ON {store}",
    "Les fichiers du jeu ne sont pas encore sur la carte : ce port ne se lancera pas.":
        "The game files are not on the card yet: this port will not start.",
    "Les fichiers du jeu sont sur la carte.": "The game files are on the card.",
    "Place sur la carte : {size} (dossier {folder}, fichiers du jeu compris).":
        "Space on the card: {size} ({folder} folder, game files included).",
    "Ports sans fichiers du jeu": "Ports without game files",
    "Installer un port depuis un .zip…": "Install a port from a .zip…",
    "Ports en attente d'installation…": "Ports waiting to be installed…",
    "version {new} (sur la carte : {old})": "version {new} (on the card: {old})",
    "La nouvelle version de PortMaster est prête.": "The new PortMaster version is ready.",
    "Mise à jour de PortMaster": "PortMaster update",
    "Ports à installer": "Ports to install", "Archives de ports": "Port archives",
    "Ces archives ne sont pas des ports PortMaster :": "These archives are not PortMaster ports:",
    "Ports en attente": "Pending ports", "Aucun port n'attend d'être installé.": "No port is waiting to be installed.",
    "Ces ports seront installés au prochain lancement de PortMaster sur la console. "
    "Coche ceux que tu ne veux plus installer : ils passent par la corbeille.":
        "These ports will be installed the next time PortMaster is launched on the console. "
        "Check the ones you no longer want to install: they go to the trash.",
    "RETIRER": "REMOVE", "{n} port retiré": "{n} port removed", "{n} ports retirés": "{n} ports removed",
    "Retrait de {n} port en attente": "Removing {n} pending port",
    "Retrait de {n} ports en attente": "Removing {n} pending ports",
    # santé de la carte, doublons
    "Chercher les doublons…": "Find duplicates…", "Vérifier la carte SD…": "Check the SD card…",
    "Vérification de la carte": "Card check", "Fichiers illisibles": "Unreadable files",
    "Archives abîmées": "Damaged archives", "ROM vides (0 octet)": "Empty ROMs (0 bytes)",
    "gamelist.xml abîmés": "Damaged gamelist.xml", "Fichiers très lents à lire": "Very slow files",
    "Vérification arrêtée avant la fin : {n} fichiers vérifiés.": "Check stopped before the end: {n} files checked.",
    "La carte a des fichiers abîmés. Sauvegarde tes parties maintenant (Outils → Sauvegarder mes parties) et "
    "pense à passer sur une carte neuve de bonne qualité.":
        "The card has damaged files. Back up your saves now (Tools → Back up my saves) and consider moving to a "
        "new good-quality card.",
    "Rien d'illisible, mais quelques points à surveiller.": "Nothing unreadable, but a few things to watch.",
    "Aucun problème : tous les fichiers se lisent correctement.": "No problem: every file reads correctly.",
    "{n} fichiers relus ({size}) en {minutes} min.": "{n} files read ({size}) in {minutes} min.",
    "Vitesse de lecture moyenne : {speed}/s": "Average read speed: {speed}/s",
    "c'est lent : la carte est peut-être fatiguée ou de mauvaise qualité.":
        "that is slow: the card may be worn out or of poor quality.",
    "Recopie ces fichiers depuis ton PC ; s'ils reviennent, la carte est en fin de vie.":
        "Copy these files again from your PC; if they come back, the card is dying.",
    "Le contenu a changé sans que tu le touches : recopie ces jeux.":
        "The content changed without you touching it: copy these games again.",
    "Copie interrompue : recopie ces jeux.": "Interrupted copy: copy these games again.",
    "Les fiches de cette console sont perdues pour EmulationStation. Annule une opération récente ou recrée les "
    "fiches.": "EmulationStation loses the game cards of this console. Undo a recent operation or recreate the cards.",
    "La carte peine à lire ces endroits : surveille-les.": "The card struggles to read these places: keep an eye on them.",
    "Chaque fichier de la carte a été relu en entier ; les .zip sont aussi contrôlés avec leur empreinte (CRC).":
        "Every file on the card was read in full; .zip files are also checked against their checksum (CRC).",
    "Comparaison : {name}": "Comparing: {name}", "Aucun doublon sur la carte.": "No duplicates on the card.",
    "copie identique de : {name}": "identical copy of: {name}", "autre version de : {name}": "other version of: {name}",
    "a des parties, une note ou est en favori": "has saves, a rating or is a favorite",
    "Pour chaque jeu en double, la meilleure copie est gardée : celle qui a des parties, une note ou un favori, "
    "puis la meilleure région et la révision la plus récente. Les copies cochées seront supprimées (elles passent "
    "par la corbeille).":
        "For each duplicated game the best copy is kept: the one with saves, a rating or a favorite, then the best "
        "region and the latest revision. Checked copies will be deleted (they go to the trash).",
    "{n} doublon supprimé": "{n} duplicate deleted", "{n} doublons supprimés": "{n} duplicates deleted",
    "Suppression de {n} doublon": "Deleting {n} duplicate", "Suppression de {n} doublons": "Deleting {n} duplicates",
    # noms des jeux d'arcade
    "Vrais noms des jeux d'arcade…": "Real names of arcade games…", "Jeux d'arcade": "Arcade games",
    "Tous les jeux d'arcade ont déjà un vrai nom.": "All arcade games already have a real name.",
    "Ces jeux s'affichent sous leur nom de code, parfois précédé d'un numéro. Ils prendront leur vrai titre (liste "
    "FinalBurn Neo) ; le fichier du jeu n'est pas renommé, la console le lance toujours.":
        "These games show under their code name, sometimes with a number in front. They will get their real title "
        "(FinalBurn Neo list); the game file is not renamed, so the console still launches it.",
    "RENOMMER": "RENAME", "{n} jeu renommé": "{n} game renamed", "{n} jeux renommés": "{n} games renamed",
    "Renommage de {n} jeu": "Renaming {n} game", "Renommage de {n} jeux": "Renaming {n} games",
    # catalogue de jeux
    "Catalogue de jeux": "Game catalogue", "Catalogue de jeux…": "Game catalogue…",
    "Aucune console de la carte n'a de catalogue.": "No console on the card has a catalogue.",
    "Tous les jeux sortis sur chaque console, avec ceux que tu as déjà. Les jeux du commerce sont protégés : "
    "copie-les depuis ta cartouche ou ton disque. Les jeux gratuits et légaux (homebrew, Freedoom) s'installent "
    "directement sur la carte.":
        "Every game released on each console, with the ones you already have. Commercial games are protected: copy "
        "them from your own cartridge or disc. Free and legal games (homebrew, Freedoom) install straight to the card.",
    "Console :": "Console:", "Tous les jeux": "All games", "Sur ma carte": "On my card", "Manquants": "Missing",
    "Gratuits à installer": "Free to install", "JEU": "GAME", "RÉGIONS": "REGIONS",
    "SITE DU JEU": "GAME WEBSITE", "Liste indisponible (pas d'internet ?)": "List unavailable (no internet?)",
    "Chargement de la liste…": "Loading the list…",
    "Pas de liste de jeux pour cette console.": "No game list for this console.",
    "Titre (A → Z)": "Title (A → Z)", "Meilleures notes": "Best rated", "Plus populaires": "Most popular",
    "Plus récents": "Newest", "Plus anciens": "Oldest", "Notes : chargement…": "Ratings: loading…",
    "VOTES": "VOTES",
    "Notes et popularité : communauté LaunchBox": "Ratings and popularity: LaunchBox community",
    "Notes indisponibles (pas d'internet ?)": "Ratings unavailable (no internet?)",
    "Note : ": "Rating: ", "{rating} / 5 ({votes} votes)": "{rating} / 5 ({votes} votes)",
    "{shown} jeux affichés · {owned} sur ta carte sur {total}": "{shown} games shown · {owned} of {total} on your card",
    "{n} à installer": "{n} to install", "sur ta carte": "on your card", "gratuit": "free",
    "Ce jeu est sur ta carte.": "This game is on your card.",
    "Gratuit et légal : il s'installe directement sur la carte.": "Free and legal: it installs straight to the card.",
    "Jeu du commerce : copie-le depuis ta propre cartouche ou ton disque, puis ajoute-le avec « Ajouter des jeux ».":
        "Commercial game: copy it from your own cartridge or disc, then add it with \"Add games\".",
    "Année": "Year", "Régions": "Regions", "Licence": "License", "Versions :": "Versions:",
    "{n} jeu gratuit installé": "{n} free game installed", "{n} jeux gratuits installés": "{n} free games installed",
    "Certains jeux n'ont pas pu être installés :": "Some games could not be installed:",
    "Installation de {n} jeu gratuit": "Installing {n} free game",
    "Installation de {n} jeux gratuits": "Installing {n} free games",
}
