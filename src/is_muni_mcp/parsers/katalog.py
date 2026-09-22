"""Vyhledávání v katalogu předmětů (POST /auth/predmety/predmety_ajax.pl, operace get_courses)."""

from __future__ import annotations

import re

from .common import clean_text
from .common import soup as make_soup


def parse_search_response(data: dict) -> dict:
    """Odpověď get_courses → {pocet, predmety: [{kod, nazev, obdobi, fakulta, url}], dalsi_strany}.

    Každý řádek table_tr je HTML s odkazem /auth/predmet/{fak}/{slug}/{kod}.
    """
    predmety: list[dict] = []
    for row_html in data.get("table_tr", []):
        s = make_soup(row_html)
        a = s.find("a", href=re.compile(r"/auth/predmet/\w+/\w+/"))
        if not a:
            continue
        m = re.search(r"/auth/predmet/(\w+)/(\w+)/([A-Za-z0-9]+)", str(a.get("href", "")))
        text = clean_text(s)
        # "CORE014 Příběh svobody a demokracie (podzim 2026) Vyučující"
        tm = re.match(r"^(\S+)\s+(.*?)\s*\(([^)]+)\)", text)
        predmety.append(
            {
                "kod": m.group(3) if m else (tm.group(1) if tm else ""),
                "nazev": tm.group(2) if tm else text[:120],
                "obdobi": tm.group(3) if tm else "",
                "fakulta": m.group(1) if m else "",
                "url": str(a.get("href", "")),
            }
        )
    try:
        pocet = int(data.get("count", len(predmety)))
    except (TypeError, ValueError):
        pocet = len(predmety)
    return {
        "pocet": pocet,
        "predmety": predmety,
        "dalsi_strany": bool(data.get("more_courses")) or pocet > len(predmety),
    }
