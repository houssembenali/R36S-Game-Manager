<p align="center">
  <img src="docs/banner.png" alt="R36S Game Manager" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-ff3ea5?style=for-the-badge" alt="MIT license">
</p>

<p align="center">
  <b>Organize, clean up and pimp the SD card of your R36S handheld (ArkOS) from your PC.</b><br>
  Box art, videos, favorites, ratings, cleanup, compression… no command line needed.
</p>

<p align="center">
  <img src="docs/demo.gif" alt="Demo" width="90%">
</p>

---

## ✨ Features

| | |
|---|---|
| 🎮 **Library** | All your games as a box-art grid or a list, with **each console's logo**, search and **filters** (genre, players, region, never played…) |
| 📺 **Game details** | Screenshot, **video preview** that starts by itself, ★ rating, region flags 🇺🇸🇪🇺🇯🇵, play count and last played date |
| ⭐ **Favorites & metadata** | The same favorites as on the console, edit any game card (name, rating, description, **images**) |
| ➕ **Add games** | Drag & drop your ROMs: the console is detected, then **image, description, year and genre are fetched from the internet** |
| 🧹 **Cleanup** | Orphan media, entries without a game, games in the wrong folder, duplicates, bulky videos |
| 💿 **Multi-disc & CHD** | Merge multi-CD games into a single `.m3u` entry and **compress** CD games to `.chd` (30–60 % space saved) |
| 💾 **Safety** | Back up your saves to your PC, check BIOS files, and **every operation can be undone** (trash) |

<p align="center">
  <img src="docs/screen-video.jpg" width="49%" alt="Game details with its video">
  <img src="docs/screen-filters.jpg" width="49%" alt="Filters">
</p>

> 🌍 Interface in **English** (default) and **French**: click the flag at the top right to switch instantly, no restart. Your language, view, sort order, panel sizes and video sound are remembered.

## 📥 Download

Grab the file for your system from **[Releases](../../releases/latest)**. Nothing to install:

| System | File |
|---|---|
| 🪟 Windows 10/11 | `R36S-Game-Manager-windows-x64.exe` (double-click) |
| 🐧 Linux x64 | `R36S-Game-Manager-linux-x64.tar.gz` → extract, then `./R36S-Game-Manager` |

> **Optional:** [VLC](https://www.videolan.org) for game videos, [7-Zip](https://www.7-zip.org) (Windows) or `mame-tools` (Linux) for CHD compression.

> 🛡️ **Windows says "Windows protected your PC"?** The executable isn't code-signed (signing certificates are expensive), so SmartScreen warns about any new download. Click **More info → Run anyway**. Some antivirus tools also flag apps built with PyInstaller by mistake: the full source code is here, and you can build the executable yourself with `python build.py`.

## 🚀 Usage

1. **Turn the console off**, take out the SD card and plug it into your PC.
2. Start the program: the **EASYROMS** partition is found automatically.
3. Manage your games, then put the card back in the console. That's it!

**Shortcuts:** `Ctrl+F` search · `F` favorite · `F2` edit game card · `Del` delete · `F5` reload the card · right-click for the game menu.

> 🛟 **Don't panic:** nothing is erased right away. Deleted files go to a hidden trash on the card, and the ↶ button undoes the last operation. *Empty the trash* to actually free the space.

## 🛠️ From source

```bash
pip install -r requirements.txt
python app.py               # or: lancer.bat (Windows) · sh lancer.sh (Linux)
python -m pytest -q         # tests on a fake card (yours is never touched)
python build.py             # builds the executable into dist/
```

To publish a release: `git tag v1.0.0 && git push --tags`. GitHub Actions runs the tests and builds the Windows and Linux executables into *Releases*.

<details>
<summary>🗂️ Code layout</summary>

| File | Role |
|---|---|
| `app.py`, `tools_actions.py` | Main window and menu actions |
| `widgets.py`, `dialogs.py` | Buttons, box-art grid, dialogs |
| `core.py` | Reading the card and `gamelist.xml` files, deleting, moving |
| `journal.py` | Trash and undo for every operation |
| `cleanup.py`, `multidisc.py`, `chd.py`, `saves.py`, `bios.py` | Tools |
| `scraper.py`, `metadata.py`, `net.py` | Images, game info and internet access |
| `theme.py`, `icons.py`, `logos.py`, `systems.py`, `regions.py` | Retro theme, pixel icons, logos, consoles, flags |

</details>

## 🙏 Credits

Images: [libretro-thumbnails](https://github.com/libretro-thumbnails/libretro-thumbnails) · Game info: [libretro-database](https://github.com/libretro/libretro-database), [Wikidata](https://www.wikidata.org) and [Wikipedia](https://www.wikipedia.org) · Compression: `chdman` from [MAME](https://www.mamedev.org) · Videos: [VLC](https://www.videolan.org) · Fonts: *Press Start 2P* and *Chakra Petch* (OFL license).

> ⚠️ No ROMs or BIOS files are included. Console logos are read from the themes already on your card.
> Independent project, not affiliated with the R36S manufacturers or ArkOS.

Released under the [MIT](LICENSE) license.
