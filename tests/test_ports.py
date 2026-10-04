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
