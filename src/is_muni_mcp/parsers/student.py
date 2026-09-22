"""Parsers studentské agendy: moje předměty, známky, detail předmětu."""

from __future__ import annotations

import re

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_moje_predmety(html: str) -> list[dict]:
    """Parsuje /auth/student/predmety → [{kod, nazev, fakulta_id, predmet_id}]."""
    s = make_soup(html)
    predmety: list[dict] = []
    for div in s.find_all("div", class_="predmet_conteiner"):
        header = div.find("span", class_="predmet_header_name")
        if not header:
            continue
        strong = header.find("strong")
        kod = clean_text(strong) if strong else ""
        nazev = clean_text(header).replace(kod, "", 1).strip()
        img = header.find("img")
        fakulta_id = ""
        if img and img.get("src"):
            m = re.search(r"/(\d+)\.svg", str(img["src"]))
            if m:
                fakulta_id = m.group(1)
        predmet_id = ""
        a = div.find("a", id=re.compile(r"predmet-button-"))
        if a and a.get("id"):
            m = re.search(r"predmet-button-(\d+)", str(a["id"]))
            if m:
                predmet_id = m.group(1)
        if kod:
            predmety.append(
                {
                    "kod": kod,
                    "nazev": nazev,
                    "fakulta_id": fakulta_id,
                    "predmet_id": predmet_id,
                }
            )
    return predmety


def parse_moje_znamky(html: str) -> list[dict]:
    """Parsuje /auth/student/moje_znamky → [{obdobi, kod, predmet, obor, kredity, ukonceni, hodnoceni, zadano}]."""
    s = make_soup(html)
    main = main_content(s)
    vysledky: list[dict] = []
    for table in main.find_all("table"):
        headers = [clean_text(th) for th in table.find_all("th")]
        if "Předmět" not in headers:
            continue
        obdobi = ""
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            cells = [clean_text(td) for td in tds]
            if len(cells) == 1 and cells[0]:
                # oddíl období ("podzim 2026")
                if re.match(r"^(jaro|podzim|léto|leto|zima)\s+\d{4}$", cells[0]):
                    obdobi = cells[0]
                continue
            if len(cells) < 4:
                continue
            if cells[0] in ("Předmět", ""):
                continue
            m = re.match(r"(?:(\w+):)?(\S+)\s+(.*)", cells[0])
            kod = m.group(2) if m else ""
            nazev = m.group(3) if m else cells[0]
            link = tr.find("a", href=re.compile(r"/auth/predmet/"))
            vysledky.append(
                {
                    "obdobi": obdobi,
                    "kod": kod,
                    "predmet": nazev,
                    "obor": cells[1] if len(cells) > 1 else "",
                    "kredity": cells[2] if len(cells) > 2 else "",
                    "ukonceni": cells[3] if len(cells) > 3 else "",
                    "hodnoceni": cells[4] if len(cells) > 4 else "",
                    "zadano": cells[5] if len(cells) > 5 else "",
                    "predmet_url": str(link.get("href", "")) if link else "",
                }
            )
    return vysledky


def parse_predmet_detail(html: str) -> dict:
    """Parsuje /auth/predmet/{fak}/{obdobi}/{kod} (resp. veřejný /predmet/...)."""
    s = make_soup(html)
    main = main_content(s)
    text = clean_text(main)

    # Kód + název z h2 ("BSSb1101 Úvod do bezpečnostních a strategických studií")
    kod = ""
    nazev = ""
    for h in main.find_all("h2"):
        t = clean_text(h)
        m = re.match(r"^([A-Za-z0-9]+)\s+(.{3,})$", t)
        if m and "?" not in t and "Nenašli" not in t:
            kod, nazev = m.group(1), m.group(2)
            break
    if not kod:
        title = s.find("title")
        if title:
            m = re.search(r"\w+:(\S+)\s+(.*?)\s+- Informace o předmětu", clean_text(title))
            if m:
                kod, nazev = m.group(1), m.group(2)

    # Detailní údaje jsou v DL seznamu (DT = název, DD = hodnota)
    udaje: dict[str, str] = {}
    for dl in main.find_all("dl"):
        dts = dl.find_all("dt")
        for dt in dts:
            key = clean_text(dt)
            dd = dt.find_next_sibling("dd")
            if key and dd:
                udaje[key] = clean_text(dd)

    vyucujici: list[str] = []
    for a in main.find_all("a", href=re.compile(r"/auth/osoba/\d+")):
        jmeno = clean_text(a)
        if jmeno and jmeno not in vyucujici and "Kontaktní" not in jmeno:
            vyucujici.append(jmeno)

    # Rozsah/kredity/ukončení z hlavičky ("Rozsah 1/1/0. 6 kr. Ukončení: zk.")
    rozsah = ""
    m = re.search(r"Rozsah\s+([\d/]+)", text)
    if m:
        rozsah = m.group(1)
    kredity = ""
    m = re.search(r"(\d+)\s*kr\.", text)
    if m:
        kredity = m.group(1)
    ukonceni = ""
    m = re.search(r"Ukončení:\s*(\S+)", text)
    if m:
        ukonceni = m.group(1)

    el_url = ""
    el = main.find("a", href=re.compile(r"/auth/el/"))
    if el:
        el_url = str(el.get("href", ""))

    return {
        "kod": kod,
        "nazev": nazev,
        "vyucujici": vyucujici,
        "rozsah": rozsah,
        "kredity": kredity,
        "ukonceni": ukonceni,
        "rozvrh": udaje.get("Rozvrh", ""),
        "predpoklady": udaje.get("Předpoklady", ""),
        "anotace": udaje.get("Anotace", ""),
        "vystupy": udaje.get("Výstupy z učení", ""),
        "klicova_temata": udaje.get("Klíčová témata", ""),
        "garance": udaje.get("Garance", ""),
        "el_url": el_url,
    }
