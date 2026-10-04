"""Ports PortMaster : infos locales (port.json), dossiers orphelins, catalogue et mises à jour."""
import json
import os

import cleanup
import core
import metadata
import ports
from conftest import write

PORT_JSON = {
    "name": "sprout.zip",
    "items": ["Sprout.sh", "sprout/"],
    "attr": {"title": "Sprout Valley", "desc": "Une ferme.", "inst": "Copy data.win into ports/sprout.",
             "genres": ["simulation", "rpg"], "porter": ["Alice", "Bob"], "rtr": False, "availability": "paid",
             "image": {"screenshot": "screenshot.png", "covers": ["cover.png"]}},
    "status": {"source": "PortMaster", "md5": "old-md5", "status": "Installed"},
}


def add_port(card):
    write(card, "ports/Sprout.sh", "#!/bin/bash\n")
    write(card, "ports/sprout/port.json", json.dumps(PORT_JSON))
    write(card, "ports/sprout/screenshot.png", b"png")
    write(card, "ports/sprout/cover.png", b"png")
    core.clear_cache()
    return {os.path.basename(g.path): g for g in core.load_all(card)["ports"]}["Sprout.sh"]


def catalog_entry(md5="new-md5", rtr=False, arch=("aarch64",), runtime=()):
    return {"attr": {"title": "Sprout Valley", "desc": "d", "genres": ["rpg"], "porter": [], "rtr": rtr,
                     "arch": list(arch), "image": {"screenshot": "screenshot.png"}, "runtime": list(runtime)},
            "source": {"size": 1234, "url": "https://example/sprout.zip", "md5": md5, "date_updated": "2026-09-01"}}


def test_card_and_images_from_port_json(card):
    g = add_port(card)
    assert metadata.from_port_json(g) == {"name": "Sprout Valley", "desc": "Une ferme.", "genre": "simulation"}
    media = core.port_media(g)
    assert media["image"].endswith("screenshot.png") and media["thumbnail"].endswith("cover.png")
    assert metadata.needs_images(g)  # images présentes dans le dossier mais pas encore dans la fiche
    assert ports.requirements(g) == (False, "Copy data.win into ports/sprout.", ["Alice", "Bob"], True)


def test_orphan_port_folders_in_cleanup(card):
    add_port(card)
    write(card, "ports/Removed Game/data.pak", b"z" * 300)
    write(card, "ports/PortMaster/pugwash", b"tool")
    games = core.load_all(card)
    orphans = [os.path.basename(d) for d in ports.orphan_dirs(card, games["ports"])]
    assert orphans == ["Removed Game"]
    found = [i for i in cleanup.scan(card, games) if i.kind == "portdir"]
    assert [os.path.basename(i.path) for i in found] == ["Removed Game"] and found[0].size == 300


def test_catalog_parsing_and_updates(card):
    add_port(card)
    data = {"ports": {"sprout.zip": catalog_entry(runtime=["dotnet-8.0.12.squashfs"]),
                      "x86only.zip": catalog_entry(arch=["x86_64"])}}
    catalog = ports._parse(data)
    assert [p.zip for p in catalog] == ["sprout.zip"]  # le port x86 ne tourne pas sur la R36S
    p = catalog[0]
    assert p.screenshot.endswith("/ports/sprout/screenshot.png") and p.runtimes == ["dotnet-8.0.12.squashfs"]
    assert ports.installed(card) == {"sprout.zip": "old-md5"}
    assert ports.updates(card, catalog) == [p]
    assert ports.updates(card, ports._parse({"ports": {"sprout.zip": catalog_entry(md5="old-md5")}})) == []


def test_missing_runtimes(card, monkeypatch):
    monkeypatch.setattr(ports, "load_runtimes", lambda: {"a.squashfs": ("u1", "m1", 1), "b.squashfs": ("u2", "m2", 2)})
    write(card, "ports/PortMaster/libs/a.squashfs", b"lib")
    catalog = ports._parse({"ports": {"sprout.zip": catalog_entry(runtime=["a.squashfs", "b.squashfs", "c.squashfs"])}})
    assert ports.missing_runtimes(card, catalog) == [("b.squashfs", "u2", "m2", 2)]


def test_updates_ignore_port_whose_script_was_deleted(card):
    add_port(card)
    os.remove(os.path.join(card, "ports", "Sprout.sh"))  # dossier resté sur la carte, port supprimé
    core.clear_cache()
    assert ports.installed(card) == {}
    assert ports.updates(card, ports._parse({"ports": {"sprout.zip": catalog_entry()}})) == []


def test_files_target_follows_instructions(card, monkeypatch):
    g = add_port(card)
    assert ports.files_target(g) == os.path.join(card, "ports", "sprout")  # « into ports/sprout. »
    attr = dict(PORT_JSON["attr"], inst="Place the game files in sprout/gamedata/data.")
    monkeypatch.setattr(core, "port_info", lambda path: dict(PORT_JSON, attr=attr))
    assert ports.files_target(g) == os.path.join(card, "ports", "sprout", "gamedata", "data")
    attr["inst"] = "Put the .pck file in the assets folder."
    assert ports.files_target(g) == os.path.join(card, "ports", "sprout", "assets")


def test_runtimes_needed_missing_unused(card, monkeypatch):
    add_port(card)
    data = dict(PORT_JSON, attr=dict(PORT_JSON["attr"], runtime=["mono.squashfs"]))
    write(card, "ports/sprout/port.json", json.dumps(data))
    write(card, "ports/Other.sh", 'runtime="frt_3.5.2"\n')
    write(card, "ports/Third.sh", "mount $controlfolder/libs/godot_4.squashfs\n")
    for name in ("frt_3.5.2", "frt_2.1.6", "godot_4"):
        write(card, f"ports/PortMaster/libs/{name}.squashfs", b"lib")
    core.clear_cache()
    monkeypatch.setattr(ports, "load_runtimes", lambda: {"mono.squashfs": ("u", "m", 5)})
    assert ports.needed_runtimes(card) == ["mono.squashfs", "frt_3.5.2.squashfs"]
    assert ports.missing_installed_runtimes(card) == [("mono.squashfs", "u", "m", 5)]
    unused = ports.unused_runtimes(card)
    assert [os.path.basename(p) for p in unused] == ["frt_2.1.6.squashfs"]
    found = [i for i in cleanup.scan(card, core.load_all(card)) if i.kind == "portlib"]
    assert [os.path.basename(i.path) for i in found] == ["frt_2.1.6.squashfs"]


def test_delete_port_removes_all_its_folders_but_not_shared_ones(card):
    data = {"name": "smb.zip", "items": ["smb1.sh", "smbll.sh", "smworld/", "smconf/"], "attr": {}}
    write(card, "ports/smb1.sh", "#!/bin/bash\n")
    write(card, "ports/smbll.sh", "#!/bin/bash\n")
    write(card, "ports/smworld/port.json", json.dumps(data))
    write(card, "ports/smconf/config.ini", "x")
    core.clear_cache()
    games = core.load_all(card)["ports"]
    smb1 = next(g for g in games if g.path.endswith("smb1.sh"))
    # l'autre script utilise encore les dossiers : seuls le script et ses médias partent
    assert [os.path.basename(p) for p in core.files_to_delete(smb1, games)] == ["smb1.sh"]
    alone = [g for g in games if g is smb1]
    names = sorted(os.path.basename(p) for p in core.files_to_delete(smb1, alone))
    assert names == ["smb1.sh", "smconf", "smworld"]
