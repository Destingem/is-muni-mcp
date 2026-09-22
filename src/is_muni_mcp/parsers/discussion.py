"""Diskuse (/auth/discussion/, vlákna /auth/discussion/...). Pouze čtení."""

from __future__ import annotations

import re

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_diskuse_index(html: str) -> dict:
    """Přehled fór → {sekce: [{nazev, fora: [{nazev, nove, url}]}]}."""
    s = make_soup(html)
    main = main_content(s)
    sekce: list[dict] = []
    for wrap in main.find_all("div", class_="forum_nazev_wrap"):
        h = wrap.find(["h2", "h3"])
        nazev = clean_text(h) if h else ""
        fora: list[dict] = []
        sib = wrap.find_next_sibling()
        while sib and getattr(sib, "name", None):
            classes = sib.get("class", []) if hasattr(sib, "get") else []
            if "forum_nazev_wrap" in classes:
                break
            if "forum_row_wrap" in classes:
                a = sib.select_one("div.forum_nazev a[href]")
                pocet = sib.select_one("div.forum_nove span.pocet")
                if a:
                    fora.append(
                        {
                            "nazev": clean_text(a)[:120],
                            "nove": clean_text(pocet) if pocet else "",
                            "url": str(a.get("href", "")),
                        }
                    )
            sib = sib.find_next_sibling()
        if nazev and fora:
            sekce.append({"nazev": nazev, "fora": fora})
    return {"sekce": sekce}


def parse_vlakno(html: str) -> dict:
    """Vlákno diskuse → {nazev, prispevky: [{autor, autor_uco, datum, text, id}]}."""
    s = make_soup(html)
    main = main_content(s)
    nazev = ""
    title = s.find("title")
    if title:
        # "Volejbal v Brně - celá Masarykova univerzita - Diskuse"
        nazev = clean_text(title).split(" - ")[0]
    if not nazev:
        nz = main.select_one("span.nazev")
        nazev = clean_text(nz) if nz else ""
    prispevky: list[dict] = []
    for post in main.find_all("div", class_="prispevek"):
        if "novy_prispevek" in (post.get("class", [])):
            continue  # editor nového příspěvku, ne příspěvek
        obsah = post.find("div", class_="obsah") or post
        autor_box = obsah.find("div", class_="autor") or post
        osoba = autor_box.find("a", href=re.compile(r"/auth/osoba/\d+"))
        autor = clean_text(osoba) if osoba else ""
        uco = ""
        if osoba:
            m = re.search(r"/auth/osoba/(\d+)", str(osoba.get("href", "")))
            uco = m.group(1) if m else ""
        datum_el = autor_box.find("span", class_="datum")
        datum = ""
        if datum_el:
            datum = str(datum_el.get("title", "")) or clean_text(datum_el)
        # tělo = obsah bez autorského bloku
        for el in obsah.find_all("div", class_="autor"):
            el.decompose()
        text = clean_text(obsah)
        # odstraň hodnotící fráze na konci ("hodnotit Vtipné Zajímavé ...")
        text = re.split(r"\bhodnotit\b", text)[0].strip()
        if not text and not autor:
            continue
        prispevky.append(
            {
                "id": str(post.get("data-id", "")),
                "autor": autor,
                "autor_uco": uco,
                "datum": datum,
                "text": text[:2000],
            }
        )
    return {"nazev": nazev, "prispevky": prispevky[:100]}
