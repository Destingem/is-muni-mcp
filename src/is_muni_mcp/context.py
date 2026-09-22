"""Studijní kontext: kdo jsem, jaká studia/období/fakulty mám, co je právě vybráno.

IS předává kontext v parametrech odkazů: ?fakulta={id};obdobi={id};studium={id}
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .client import IsMuniClient
from .parsers.common import clean_text, parse_is_params
from .parsers.common import soup as make_soup


@dataclass
class StudyInfo:
    studium_id: str = ""
    fakulta_id: str = ""
    fakulta_nazev: str = ""
    program: str = ""
    popis: str = ""


@dataclass
class ObdobiInfo:
    obdobi_id: str = ""
    nazev: str = ""  # např. "podzim 2026"


@dataclass
class StudyContext:
    uco: str = ""
    jmeno: str = ""
    email: str = ""
    studia: list[StudyInfo] = field(default_factory=list)
    obdobi: list[ObdobiInfo] = field(default_factory=list)
    vybrane_studium: str = ""
    vybrane_obdobi: str = ""
    vybrana_fakulta: str = ""


def _parse_prepinace(html: str) -> tuple[list[StudyInfo], list[ObdobiInfo], str, str, str]:
    """Parsuje přepínač studia/období/fakulty z hlavičky stránky."""
    s = make_soup(html)
    studia: list[StudyInfo] = []
    obdobi: list[ObdobiInfo] = []
    vybrane_studium = vybrane_obdobi = vybrana_fakulta = ""

    # Aktuální výběr bývá v parametrech odkazů ("-" je placeholder přepínače → ignoruj)
    for a in s.find_all("a", href=True):
        href = str(a["href"])
        if "studium=" in href or "obdobi=" in href:
            p = parse_is_params(href)
            if p.get("studium") not in (None, "", "-") and not vybrane_studium:
                vybrane_studium = p["studium"]
            if p.get("obdobi") not in (None, "", "-") and not vybrane_obdobi:
                vybrane_obdobi = p["obdobi"]
            if p.get("fakulta") not in (None, "", "-") and not vybrana_fakulta:
                vybrana_fakulta = p["fakulta"]
            if vybrane_studium and vybrane_obdobi and vybrana_fakulta:
                break

    # Pozn.: přepínače studií/období se v IS doplňují JavaScriptem, takže jejich
    # kompletní výčet ze statického HTML nedostaneme. Držíme aspoň aktuální
    # výběr (a text aktuálního období pro slug).
    for a in s.find_all("a", href=True):
        href = str(a["href"])
        text = clean_text(a)
        # aktuální období z odkazu "Změnit období podzim 2026" (obdobi=-)
        if text.startswith("Změnit období") and not obdobi:
            nazev = text.replace("Změnit období", "").strip()
            if nazev:
                obdobi.append(ObdobiInfo(obdobi_id=vybrane_obdobi, nazev=nazev))

    return studia, obdobi, vybrane_studium, vybrane_obdobi, vybrana_fakulta


def resolve_context(client: IsMuniClient) -> StudyContext:
    """Zjistí identitu a studijní kontext (GET /auth/ a /auth/student/)."""
    ctx = StudyContext()

    home = client.get_text("/auth/")
    s = make_soup(home)
    # Jméno + učo: odkaz /auth/osoba/{uco} s textem "Jméno Příjmení, učo XXXXXX"
    import re

    for osoba in s.find_all("a", href=lambda h: bool(h) and "/auth/osoba/" in h):
        m = re.search(r"/auth/osoba/(\d+)", str(osoba.get("href", "")))
        if m and not ctx.uco:
            ctx.uco = m.group(1)
        text = clean_text(osoba)
        # např. "Jan Novák, učo 990001" nebo "Novák, J."
        if "učo" in text:
            ctx.jmeno = text.split(", učo")[0].strip()
            break

    # Přepínač studia/období/fakulty je nejspolehlivěji na stránce Studenta
    try:
        student_html = client.get_text("/auth/student/")
    except Exception:
        student_html = home
    _, obdobi, studium, obd, fak = _parse_prepinace(student_html)
    ctx.obdobi = obdobi
    ctx.vybrane_studium = studium
    ctx.vybrane_obdobi = obd
    ctx.vybrana_fakulta = fak

    # Detail studií z osobní stránky
    if ctx.uco:
        try:
            from .parsers.person import parse_osoba

            osoba_html = client.get_text(f"/auth/osoba/{ctx.uco}")
            info = parse_osoba(osoba_html)
            ctx.jmeno = info.get("jmeno") or ctx.jmeno
            ctx.email = info.get("email", "")
            for st in info.get("studia", []):
                ctx.studia.append(
                    StudyInfo(
                        program=st.get("program", ""),
                        popis=st.get("popis", ""),
                        fakulta_nazev=st.get("fakulta", ""),
                    )
                )
        except Exception:
            pass

    return ctx
