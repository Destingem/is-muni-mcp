"""Vývěska (/auth/vyveska/) a harmonogram semestru (/auth/predmety/obdobi)."""

from __future__ import annotations

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_vyveska(html: str) -> dict:
    """→ {sekce: [{nazev, url_sekce, zpravy: [{nazev, datum, autor, url, nova}]}]}."""
    s = make_soup(html)
    main = main_content(s)
    sekce: list[dict] = []
    for h in main.find_all("h2", class_="nadpis-sekce"):
        nazev = clean_text(h)
        a_h = h.find("a", href=True)
        url_sekce = str(a_h["href"]) if a_h else ""
        # dlaždice jsou v následujícím div.sekce_row_wrap
        wrap = h.find_next("div", class_="sekce_row_wrap")
        if not wrap:
            continue
        zpravy: list[dict] = []
        for tile in wrap.find_all("div", class_="dlazdice"):
            a = tile.select_one("a.noticeboard_zprava[href]")
            if not a:
                continue
            kdy = tile.select_one("span.kdy")
            kdo = tile.select_one("a.kdo")
            zpravy.append(
                {
                    "nazev": clean_text(a)[:200],
                    "datum": clean_text(kdy),
                    "datum_detail": str(kdy.get("title", "")) if kdy else "",
                    "autor": clean_text(kdo) if kdo else "",
                    "nova": "nova" in (tile.get("class", [])),
                    "url": str(a.get("href", "")),
                }
            )
        if nazev and zpravy:
            sekce.append({"nazev": nazev, "url_sekce": url_sekce, "zpravy": zpravy})
    return {"sekce": sekce}


def parse_harmonogram(html: str, fakulta: str = "") -> dict:
    """Harmonogram období → {obdobi, fakulty: [...], udaje: [{ukon, hodnoty: {fakulta: hodnota}}]}.

    Volitelně filtr na jednu fakultu (zkratka, např. 'FSS').
    """
    s = make_soup(html)
    main = main_content(s)
    # najdi největší tabulku (křížová: řádky=údaje, sloupce=fakulty)
    best = None
    best_n = 0
    for tb in main.find_all("table"):
        n = len(tb.find_all("tr"))
        if n > best_n:
            best_n = n
            best = tb
    if best is None:
        return {"obdobi": "", "fakulty": [], "udaje": []}

    rows = best.find_all("tr")
    header = [clean_text(c) for c in rows[0].find_all(["th", "td"])]
    # první sloupec = název údaje, zbytek fakulty
    fakulty = [h for h in header[1:] if h]
    udaje: list[dict] = []
    for tr in rows[1:]:
        cells = [clean_text(c) for c in tr.find_all(["th", "td"])]
        if not cells or not cells[0]:
            continue
        hodnoty = {}
        for i, f in enumerate(fakulty):
            hodnoty[f] = cells[i + 1] if i + 1 < len(cells) else ""
        if fakulta and fakulta not in hodnoty:
            continue
        udaje.append(
            {
                "ukon": cells[0],
                "hodnoty": hodnoty if not fakulta else {fakulta: hodnoty.get(fakulta, "")},
            }
        )
    return {"fakulty": fakulty, "udaje": udaje}
