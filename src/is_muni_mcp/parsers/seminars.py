"""Seminární skupiny (/auth/seminare/student) — pouze čtení přehledu.

Stránka sice obsahuje i přihlašovací akce, ale parser čte jen stav:
do jakých skupin jsem přihlášen + které předměty skupiny mají.
"""

from __future__ import annotations

import re

from .common import clean_text, main_content
from .common import soup as make_soup


def parse_moje_seminare(html: str) -> dict:
    """→ {moje_skupiny: [{predmet, skupina, terminy, prihlasovani, odhlasovani}],
    predmety_se_skupinami: [...], predmety_bez_skupin: [...]}."""
    s = make_soup(html)
    main = main_content(s)

    moje: list[dict] = []
    h = None
    for cand in main.find_all("h3"):
        if "Jsem přihlášen" in clean_text(cand):
            h = cand
            break
    if h:
        table = h.find_next_sibling("table")
        if table:
            for tr in table.find_all("tr"):
                th = tr.find("th")
                if th:
                    predmet = clean_text(th)
                    # následující řádek obsahuje div.seminar bloky
                    det = tr.find_next_sibling("tr")
                    if det:
                        for sem in det.find_all("div", class_="seminar"):
                            h5 = sem.find("h5")
                            skupina = clean_text(h5) if h5 else ""
                            text = sem.get_text(" ", strip=True)
                            terminy = text.split("přihlašuje se")[0].strip(" ,")
                            pm = re.search(r"přihlašuje se\s*(.*?)(?=odhla|$)", text)
                            om = re.search(r"odhla\w*\s+se\s*(.*)", text)
                            moje.append(
                                {
                                    "predmet": predmet,
                                    "skupina": skupina,
                                    "terminy": re.sub(r"\s+", " ", terminy),
                                    "prihlasovani": pm.group(1).strip() if pm else "",
                                    "odhlasovani": om.group(1).strip() if om else "",
                                }
                            )

    se_skupinami: list[str] = []
    box = main.find("div", id="ma_sem_skup")
    if box:
        for a in box.find_all("a", href=True):
            t = clean_text(a)
            if t:
                se_skupinami.append(t)

    bez: list[str] = []
    for cand in main.find_all("h3"):
        if "bez seminárních skupin" in clean_text(cand).lower() or "bez seminárních" in clean_text(
            cand
        ):
            sib = cand.next_sibling
            buf = ""
            while sib is not None and getattr(sib, "name", None) not in ("h3", "table"):
                if isinstance(sib, str):
                    buf += sib + "\n"
                elif getattr(sib, "name", None) == "br":
                    buf += "\n"
                sib = sib.next_sibling
                if len(buf) > 3000:
                    break
            bez = [ln.strip() for ln in buf.splitlines() if ln.strip()]
            break

    return {
        "moje_skupiny": moje,
        "predmety_se_skupinami": se_skupinami,
        "predmety_bez_skupin": bez,
    }
