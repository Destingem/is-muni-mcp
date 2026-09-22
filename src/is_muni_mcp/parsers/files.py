"""Generický parser souborového prohlížeče IS ( Studijní materiály /el/, Dokumenty /do/ ...).

Řádky jsou div-based (role=cell): div.nazev / div.vlozil / div.vlozeno / div.prava.
Soubory mají přímý odkaz + variantu ?stahnout=1;dk=... a IS často generuje
i .txt/.pdf verze (uvedené v title atributech s velikostí).
"""

from __future__ import annotations

import re

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_vypis(html: str, base_path: str) -> dict:
    """→ {cesta, slozky: [{nazev, url, vlozil, vlozeno}], soubory: [{nazev, url, stahnout_url, vlozil, vlozeno, velikost, varianty}]}.

    base_path: cesta aktuální složky, např. /auth/el/fss/podzim2026/BSSb1101/um/
    """
    s = make_soup(html)
    main = main_content(s)
    base = base_path.rstrip("/") + "/"

    # stahovací odkazy: plain_url -> full_url (jsou ve vloženém JSON, ne v <a>)
    stahnout: dict[str, str] = {}
    for m in re.finditer(r'"href":"(/auth/[^"]+?)\?stahnout=1(;[^"]*)?"', html):
        stahnout[m.group(1)] = m.group(1) + "?stahnout=1" + (m.group(2) or "")
    for a in main.find_all("a", href=True):
        href = str(a["href"])
        m = re.match(r"^(.+?)\?stahnout=1", href)
        if m:
            stahnout.setdefault(m.group(1), href)

    # velikosti z title "Soubor X, 10,9 MB, pptx"
    velikosti: dict[str, str] = {}
    for div in main.find_all("div", class_="ikona", title=True):
        # "Soubor X.pptx, 10,9 MB, pptx" — velikost obsahuje desetinnou čárku (bez mezery)
        m = re.match(r"Soubor\s+(.*),\s+([\d\s.,]+\s*[KMG]?B),\s+(.+)", str(div["title"]))
        if m:
            velikosti[m.group(1)] = m.group(2)

    slozky: list[dict] = []
    soubory: list[dict] = []
    seen: set[str] = set()

    for nazev_div in main.find_all("div", class_="nazev"):
        a = nazev_div.find("a", href=True)
        if not a:
            continue
        href = str(a["href"])
        if "?" in href or "#" in href:
            continue
        if not href.startswith(base) or href == base:
            continue
        rest = href[len(base) :]
        if "/" in rest.strip("/"):
            continue
        if href in seen:
            continue
        seen.add(href)

        row = nazev_div.find_parent("div", class_=re.compile(r"fmgr_row|row"))
        vlozil = vlozeno = ""
        if row:
            v = row.find("div", class_="vlozil")
            d = row.find("div", class_="vlozeno")
            vlozil = clean_text(v) if v else ""
            vlozeno = clean_text(d) if d else ""
        nazev = clean_text(a) or rest.strip("/")

        if href.endswith("/"):
            slozky.append({"nazev": nazev, "url": href, "vlozil": vlozil, "vlozeno": vlozeno})
        else:
            stem = re.sub(r"\.[a-zA-Z0-9]+$", "", href)
            soubory.append(
                {
                    "nazev": nazev,
                    "url": href,
                    "stahnout_url": stahnout.get(href, ""),
                    "vlozil": vlozil,
                    "vlozeno": vlozeno,
                    "velikost": velikosti.get(nazev, ""),
                    "varianty": {"txt": stem + ".txt", "pdf": stem + ".pdf"},
                }
            )

    return {"cesta": base, "slozky": slozky, "soubory": soubory}


def is_text_content(content_type: str, url: str) -> bool:
    ct = content_type.lower()
    if ct.startswith("text/") or "json" in ct or "xml" in ct or "javascript" in ct:
        return True
    return url.lower().rsplit(".", 1)[-1] in {
        "txt",
        "md",
        "csv",
        "json",
        "xml",
        "html",
        "htm",
        "py",
        "c",
        "h",
        "java",
        "js",
        "ts",
        "tex",
        "r",
        "sql",
        "log",
        "srt",
        "vtt",
    }
