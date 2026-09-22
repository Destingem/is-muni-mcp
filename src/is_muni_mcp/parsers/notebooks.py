"""Parser poznámkových bloků (/auth/student/poznamkove_bloky_nahled)."""

from __future__ import annotations

import re

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_bloky_nahled(html: str) -> dict:
    """→ {posledni_zmena, predmety: [{kod_nazev, zmeneno, bloky: [{nazev, obsah, body, zmeneno, kym}]}]}."""
    s = make_soup(html)
    main = main_content(s)

    posledni_zmena = ""
    a = main.find("a", id="odkaz_na_posledni_akci")
    if a:
        posledni_zmena = clean_text(a)

    predmety: list[dict] = []
    for li in main.find_all("li", class_="accordion-item"):
        title = li.find("a", class_="accordion-title")
        if not title:
            continue
        # název předmětu je textový uzel v .column (bez Změněno)
        kod_nazev = ""
        for div in title.find_all("div", class_="column"):
            t = clean_text(div)
            if t and "Změněno" not in t and "img" not in t.lower():
                # přeskoč sloupec s ikonou (prázdný text)
                if len(t) > 3:
                    kod_nazev = t
                    break
        if not kod_nazev:
            # fallback: celý titulek bez data
            kod_nazev = re.sub(r"Změněno:.*", "", clean_text(title)).strip()

        zmeneno_span = title.find("span", class_="ws-nowrap")
        zmeneno = clean_text(zmeneno_span) if zmeneno_span else ""

        bloky: list[dict] = []
        content = li.find("div", class_="accordion-content")
        if content:
            for pol in content.find_all("div", class_="ipb-pol"):
                nazev_el = pol.find("div", class_="ipb-nazev")
                obsah_el = pol.find("div", class_="ipb-obsah")
                zmeneno_el = pol.find("div", class_="ipb-zmeneno")
                obsah = obsah_el.get_text("\n", strip=True) if obsah_el else ""
                # body: hvězdička + číslo (*4), finální hodnocení za @
                body = re.findall(r"\*(\d+(?:[.,]\d+)?)", obsah)
                final = re.findall(r"@\s*([A-Fa-f])", obsah)
                bloky.append(
                    {
                        "nazev": clean_text(nazev_el) if nazev_el else "",
                        "obsah": obsah,
                        "body": body,
                        "finalni": final,
                        "zmeneno": clean_text(zmeneno_el) if zmeneno_el else "",
                    }
                )
        predmety.append(
            {
                "predmet": kod_nazev,
                "zmeneno": zmeneno,
                "bloky": bloky,
            }
        )

    return {"posledni_zmena": posledni_zmena, "predmety": predmety}
