"""Notifikace: Události (/auth/udalosti/zobraz_log), IS připomíná, dashboard."""

from __future__ import annotations

import json
import re

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_zobraz_log(html: str) -> dict:
    """Záznamy událostí → {zaznamy: [{datum, text, url}], prazdne: bool}."""
    s = make_soup(html)
    main = main_content(s)
    text = clean_text(main)
    if "Nemáte žádné záznamy" in text:
        return {"zaznamy": [], "prazdne": True}

    zaznamy: list[dict] = []
    # záznamy bývají v seznamu za filtrem agend — posbírej odstavce/položky s datem
    for el in main.find_all(["li", "p", "div"]):
        t = clean_text(el)
        if re.search(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}", t) and len(t) > 30:
            # jen listové prvky, ne obalující divy (omezení hloubky duplicit)
            if el.name == "div" and el.find(["li", "p"]):
                continue
            a = el.find("a", href=True)
            zaznamy.append(
                {
                    "datum": "",
                    "text": t[:500],
                    "url": str(a["href"]) if a else "",
                }
            )
    # datum z textu
    for z in zaznamy:
        m = re.search(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}(?:\s+\d{1,2}:\d{2})?", z["text"])
        if m:
            z["datum"] = m.group(0)
    return {"zaznamy": zaznamy[:100], "prazdne": not zaznamy}


def parse_is_pripomina(html: str) -> list[dict]:
    """IS připomíná → [{text, plati_od, url}]."""
    s = make_soup(html)
    main = main_content(s)
    prip: list[dict] = []
    for el in main.find_all(["li", "p", "div"]):
        t = clean_text(el)
        if "platí od" in t and len(t) > 40:
            if el.name == "div" and el.find(["li", "p"]):
                continue
            m = re.search(r"platí od\s*([\d.\s:]+)", t)
            prip.append(
                {
                    "text": re.sub(r"\s*platí od.*$", "", t).strip()[:800],
                    "plati_od": m.group(1).strip() if m else "",
                }
            )
    # fallback: když struktura nesedí, vrať aspoň celý text sekce
    if not prip:
        txt = clean_text(main)
        m = re.search(r"Přehled připomenutí(.*?)Přehled vypnutí", txt, re.DOTALL)
        if m and len(m.group(1).strip()) > 20:
            prip.append({"text": m.group(1).strip()[:1500], "plati_od": ""})
    return prip


def parse_dashboard_ajax(json_text: str) -> dict:
    """Dashboard (index_ajax option=udalosti-init) → {prave_se_deje, ceka_vas, posledni_udalosti}.

    Každá sekce: [{nadpis, text, url}].
    """
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return {"prave_se_deje": [], "ceka_vas": [], "posledni_udalosti": []}
    s = make_soup(data.get("html", ""))
    panels = s.find_all("div", class_="tabs-panel")
    result = {"prave_se_deje": [], "ceka_vas": [], "posledni_udalosti": []}
    keys = ["prave_se_deje", "ceka_vas", "posledni_udalosti"]
    for panel, key in zip(panels, keys):
        items: list[dict] = []
        for box in panel.find_all("div", class_="stud_udalosti-box"):
            content = box.find("div", class_="stud_udalosti_content")
            text = clean_text(content or box)
            a = (content or box).find("a", href=True)
            # nadpis = předchozí sourozenec s názvem sekce
            items.append(
                {
                    "text": text[:800],
                    "url": str(a["href"]) if a else "",
                }
            )
        # nadpisy dnů (DNES 18. září apod.)
        for h in panel.find_all("h3"):
            items.append({"nadpis": clean_text(h), "text": "", "url": ""})
        result[key] = items
    return result
