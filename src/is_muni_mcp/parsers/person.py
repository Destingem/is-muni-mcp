"""Parser osobní stránky (/auth/osoba/{uco})."""

from __future__ import annotations

import re

from .common import clean_text
from .common import soup as make_soup


def parse_osoba(html: str) -> dict:
    s = make_soup(html)

    h2 = s.find("h2")
    jmeno = clean_text(h2) if h2 else ""
    if not jmeno:
        m = re.search(r"<title>[^<]*?([\p{L}][^<]*)$", html)
        title = s.find("title")
        if title:
            jmeno = clean_text(title).replace("Osobní stránka", "").strip()

    uco = ""
    status = s.find(id="status")
    if status:
        m = re.search(r"(\d{4,8})", clean_text(status))
        if m:
            uco = m.group(1)
    if not uco:
        m = re.search(r"/auth/osoba/(\d+)", html)
        if m:
            uco = m.group(1)

    email = ""
    email_box = s.find(id="email")
    if email_box:
        email = clean_text(email_box)

    studia: list[dict] = []
    for table in s.find_all("table", class_="tab_udaje_table"):
        # jen tabulky studií (mají hlavičku obor + fakulta)
        if not table.find("th", class_="stud-sbal"):
            continue
        studium_id = ""
        tid = str(table.get("id", ""))
        m = re.search(r"tab_studia_(\d+)", tid)
        if m:
            studium_id = m.group(1)
        head = table.find("th", class_="stud-sbal")
        obor_fakulta = clean_text(head) if head else ""
        udaje: dict[str, str] = {}
        for tr in table.find_all("tr"):
            th = tr.find("th")
            tds = tr.find_all("td")
            if th and tds and "stud-sbal" not in str(th.get("class", "")):
                udaje[clean_text(th)] = (
                    clean_text(tds[0])
                    if len(tds) == 1
                    else " | ".join(clean_text(td) for td in tds)
                )
        # Plány mají více řádků bez th — posbírej je
        if "Plány" in udaje or any("Plán" in k for k in udaje):
            pass
        studia.append(
            {
                "studium_id": studium_id,
                "obor_fakulta": obor_fakulta,
                "program": udaje.get("Program", ""),
                "forma": udaje.get("Forma", ""),
                "stav": udaje.get("Stav", ""),
                "plany": udaje.get("Plány", udaje.get("Plán", "")),
            }
        )

    # Kontakt na vyučujícího: telefon, kancelář (když existují)
    kontakt: dict[str, str] = {}
    for box in s.find_all("div", class_="profil_subboxik"):
        text = clean_text(box)
        if "telefon" in text.lower() or text.startswith("+"):
            kontakt["telefon"] = text

    return {
        "jmeno": jmeno,
        "uco": uco,
        "email": email,
        "studia": studia,
        "kontakt": kontakt,
    }
