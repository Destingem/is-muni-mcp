"""Zkušební termíny (/auth/student/prihl_na_zkousky). Čtení přehledu (bez přihlašování)."""

from __future__ import annotations

import re

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_zkousky(html: str) -> dict:
    """→ {predmety: [{kod_nazev, terminy: [{datum, cas, misto, poznamka, stav, url}]}], info}."""
    s = make_soup(html)
    main = main_content(s)
    info = ""
    for tb in main.find_all("table", class_="navodek"):
        info = clean_text(tb)[:500]
        break

    predmety: list[dict] = []
    # předměty bývají v nadpisech/sekcích, termíny v tabulkách pod nimi
    for h in main.find_all(["h2", "h3", "h4"]):
        nadpis = clean_text(h)
        if not re.search(r"[A-Z]{2,4}\w*\d+", nadpis):
            continue
        terminy: list[dict] = []
        # tabulka následující za nadpisem
        sib = h.find_next_sibling()
        while sib and getattr(sib, "name", None) not in ("table", "h2", "h3", "h4"):
            sib = sib.find_next_sibling()
        if sib and sib.name == "table":
            headers = [clean_text(th) for th in sib.find_all("th")]
            for tr in sib.find_all("tr"):
                tds = tr.find_all("td")
                if not tds:
                    continue
                cells = [clean_text(td) for td in tds]
                row = {
                    headers[i] if i < len(headers) else f"sloupec_{i}": c
                    for i, c in enumerate(cells)
                }
                a = tr.find("a", href=True)
                if a:
                    row["url"] = str(a["href"])
                terminy.append(row)
        predmety.append({"predmet": nadpis, "terminy": terminy})

    # fallback: když nejsou sekce, hledej aspoň text o termínech
    return {"predmety": predmety, "info": info, "prazdne": not predmety}
