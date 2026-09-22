"""IS MUNI MCP server — read-only nástroje pro studenty MU.

Spouští se přes stdio (Claude Desktop / jiný MCP klient):

    is-muni-mcp

Přihlášení (jednorázově, před prvním použitím):

    is-muni-mcp login

Detailní autentizace viz client.load_cookie_header.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta

from mcp.server.mcpserver import MCPServer

from .client import IsMuniClient
from .helpers import (
    download_dir,
    get_context,
    parse_datum,
    resolve_predmet,
    slug_na_obdobi_id,
)
from .parsers import (
    board,
    calendar,
    discussion,
    events,
    exams,
    files,
    katalog,
    mail,
    notebooks,
    person,
    seminars,
    student,
)

mcp = MCPServer(
    "is-muni",
    instructions=(
        "Nástroje pro čtení dat z Informačního systému Masarykovy univerzity (IS MUNI). "
        "Server nikdy nic nemění: umí GET a POST jen na povolené čtecí endpointy "
        "(vyhledávání) — neumí odesílat poštu, registrovat předměty, přihlašovat "
        "na zkoušky ani jinak cokoliv měnit."
    ),
)


@contextmanager
def is_client() -> Iterator[IsMuniClient]:
    client = IsMuniClient()
    try:
        yield client
    finally:
        client.close()


# ------------------------------------------------------------------ status ---


@mcp.tool()
def status() -> dict:
    """Ověří přihlášení k IS MUNI a vrátí základní identitu (jméno, učo, vybrané studium/období)."""
    with is_client() as c:
        ctx = get_context(c)
        return {
            "prihlasen": bool(ctx.uco),
            "jmeno": ctx.jmeno,
            "uco": ctx.uco,
            "email": ctx.email,
            "vybrane_studium": ctx.vybrane_studium,
            "vybrane_obdobi": ctx.vybrane_obdobi,
            "vybrana_fakulta": ctx.vybrana_fakulta,
            "studia": [s.__dict__ for s in ctx.studia],
            "obdobi": [o.__dict__ for o in ctx.obdobi],
        }


@mcp.tool()
def profil(uco: str = "") -> dict:
    """Osobní stránka: jméno, e-mail, studia, program, forma, stav, plány. Bez parametru = vlastní profil."""
    with is_client() as c:
        if not uco:
            uco = get_context(c).uco
        return person.parse_osoba(c.get_text(f"/auth/osoba/{uco}"))


@mcp.tool()
def osoba(uco: str) -> dict:
    """Kontakt na osobu (typicky vyučujícího): jméno, e-mail, telefon, pracoviště/studium."""
    with is_client() as c:
        return person.parse_osoba(c.get_text(f"/auth/osoba/{uco}"))


# ----------------------------------------------------------------- studium ---


@mcp.tool()
def moje_predmety(obdobi: str = "") -> list[dict]:
    """Zapsané předměty v daném období (kód, název, fakulta). Období např. 'podzim2026', prázdné = aktuální."""
    with is_client() as c:
        ctx = get_context(c)
        obdobi_id = slug_na_obdobi_id(ctx, obdobi) if obdobi else ctx.vybrane_obdobi
        html = c.get_text(
            f"/auth/student/predmety?fakulta={ctx.vybrana_fakulta};obdobi={obdobi_id};studium={ctx.vybrane_studium}"
        )
        return student.parse_moje_predmety(html)


@mcp.tool()
def predmet_info(kod: str, fakulta: str = "", obdobi: str = "") -> dict:
    """Detail předmětu: název, vyučující, rozsah, kredity, ukončení, rozvrhové časy, anotace, odkaz na e-learning."""
    with is_client() as c:
        ctx = get_context(c)
        ref = resolve_predmet(c, ctx, kod, fakulta, obdobi)
        info = student.parse_predmet_detail(c.get_text(ref.predmet_url))
        info["el_url"] = ref.el_url
        return info


@mcp.tool()
def moje_znamky() -> list[dict]:
    """Moje známky a hodnocení (předmět, kredity, ukončení, hodnocení, datum). Včetně starších období, pokud je IS zobrazuje."""
    with is_client() as c:
        ctx = get_context(c)
        html = c.get_text(
            f"/auth/student/moje_znamky?fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi};studium={ctx.vybrane_studium}"
        )
        return student.parse_moje_znamky(html)


@mcp.tool()
def poznamkove_bloky(predmet: str = "") -> dict:
    """Poznámkové bloky: body a hodnocení z průběžných aktivit. Volitelný filtr na kód předmětu."""
    with is_client() as c:
        ctx = get_context(c)
        html = c.get_text(
            f"/auth/student/poznamkove_bloky_nahled?obdobi={ctx.vybrane_obdobi};studium={ctx.vybrane_studium}"
        )
        data = notebooks.parse_bloky_nahled(html)
        if predmet:
            p = predmet.strip().lower()
            data["predmety"] = [x for x in data["predmety"] if p in x["predmet"].lower()]
        return data


@mcp.tool()
def hledat_predmet(dotaz: str, fakulta_id: str = "", obdobi: str = "", limit: int = 30) -> dict:
    """Vyhledávání v katalogu předmětů (kód, název, období, odkaz na detail).
    Fakulta = číselné ID (prázdné = moje fakulta), období = název ('podzim 2026', prázdné = aktuální)."""
    import json as _json
    import re as _re

    with is_client() as c:
        ctx = get_context(c)
        kat = c.get_text("/auth/predmety/katalog")
        m = _re.search(r"pvysl=(\d+)", kat)
        if not m:
            raise RuntimeError("Nepodařilo se zahájit vyhledávání (chybí pvysl token).")
        pvysl = m.group(1)
        obdobi_nazev = obdobi.strip() or next(
            (o.nazev for o in ctx.obdobi if o.obdobi_id == ctx.vybrane_obdobi), ""
        )
        filters = {
            "faculties": [fakulta_id or ctx.vybrana_fakulta],
            "terms": [obdobi_nazev] if obdobi_nazev else [],
            "offered": ["1"],
        }
        data = c.post_read_json(
            "/auth/predmety/predmety_ajax.pl",
            {
                "type": "result",
                "operace": "get_courses",
                "filters": _json.dumps(filters),
                "pvysl": pvysl,
                "search_text": dotaz,
                "records_per_page": str(max(1, min(limit, 100))),
                "origin_path_info": "/auth/predmety/katalog",
            },
        )
        return katalog.parse_search_response(data)


@mcp.tool()
def moje_seminarni_skupiny() -> dict:
    """Moje seminární skupiny (předmět, skupina, termíny, místnosti) + které předměty skupiny mají.
    Pouze přehled — nástroj nikoho nikam nepřihlašuje ani neodhlásí."""
    with is_client() as c:
        ctx = get_context(c)
        html = c.get_text(
            f"/auth/seminare/student?fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi};studium={ctx.vybrane_studium}"
        )
        return seminars.parse_moje_seminare(html)


@mcp.tool()
def harmonogram(fakulta: str = "") -> dict:
    """Harmonogram semestru: zápisy, výuka, zkouškové a další termíny. Bez parametru všechny fakulty, jinak zkratka (např. 'FSS')."""
    with is_client() as c:
        ctx = get_context(c)
        html = c.get_text(
            f"/auth/predmety/obdobi?fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi}"
        )
        return board.parse_harmonogram(html, fakulta.upper() if fakulta else "")


# -------------------------------------------------------- kalendář a výuka ---


@mcp.tool()
def kalendar(od: str = "", do: str = "", typy: str = "") -> list[dict]:
    """Kalendář: události z vývěsky, odevzdávárny, odpovědníky, události semestru, svátky, zkoušky.
    Data pokrývají aktuální zobrazené období v IS. Datum ve formátu RRRR-MM-DD.
    Typy: čárkou oddělené kódy (5_1,6_1,6_2,6_3,6_4,6_5,8_1) nebo části názvů (např. 'odevzdávárny,zkoušky')."""
    with is_client() as c:
        ctx = get_context(c)
        html = c.get_text(
            f"/auth/calendar/?fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi}"
        )
        udalosti = calendar.extract_kalendar_events(html)
        return calendar.filter_events(
            udalosti,
            od=parse_datum(od),
            do=parse_datum(do),
            typy=[t.strip() for t in typy.split(",") if t.strip()] or None,
        )


@mcp.tool()
def deadlines(od: str = "", do: str = "") -> list[dict]:
    """Blížící se deadliny: odevzdávárny, odpovědníky, zkoušky a události semestru. Výchozí rozsah: dnes až +30 dní."""
    o = parse_datum(od, date.today())
    d = parse_datum(do, (o or date.today()) + timedelta(days=30))
    assert o and d
    with is_client() as c:
        ctx = get_context(c)
        html = c.get_text(
            f"/auth/calendar/?fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi}"
        )
        udalosti = calendar.extract_kalendar_events(html)
        return calendar.filter_events(udalosti, od=o, do=d, typy=["6_1", "6_2", "6_3", "6_4"])


@mcp.tool()
def rozvrh(od: str = "", do: str = "") -> list[dict]:
    """Můj rozvrh na dané období (název, začátek, konec, místo). Výchozí rozsah: aktuální týden (Po–Ne)."""
    today = date.today()
    start_week = today - timedelta(days=today.weekday())
    o = parse_datum(od, start_week)
    d = parse_datum(do, (o or start_week) + timedelta(days=6))
    assert o and d
    with is_client() as c:
        ctx = get_context(c)
        ics = c.get_text(
            f"/auth/rozvrh/zobraz/muj?pref=w;fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi};format=ical"
        )
        return calendar.parse_ical_events(ics, od=o, do=d)


@mcp.tool()
def zkouskove_terminy() -> dict:
    """Vyhlášené zkušební termíny mých předmětů (pouze přehled — nástroj nikoho nikam nepřihlašuje)."""
    with is_client() as c:
        ctx = get_context(c)
        html = c.get_text(
            f"/auth/student/prihl_na_zkousky?pkv=1;fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi};studium={ctx.vybrane_studium}"
        )
        return exams.parse_zkousky(html)


# ------------------------------------------------------------------- pošta ---


@mcp.tool()
def posta_slozky() -> list[dict]:
    """Složky pošty (id, název, počet zpráv)."""
    with is_client() as c:
        return mail.parse_slozky(c.get_text("/auth/mail/"))


@mcp.tool()
def posta_seznam(
    slozka: str = "", start: int = 1, pocet: int = 20, jen_neprectene: bool = False
) -> dict:
    """Seznam zpráv ve složce (id, od, předmět, datum, velikost, nepřečtená).
    Složka = id nebo část názvu (např. 'Příchozí'), prázdné = příchozí pošta. Stránkování přes start."""
    with is_client() as c:
        first = c.get_text("/auth/mail/")
        slozky = mail.parse_slozky(first)
        folder_id = ""
        if not slozka:
            prichozi = next((s for s in slozky if "Příchozí" in s["nazev"]), None)
            folder_id = prichozi["id"] if prichozi else (slozky[0]["id"] if slozky else "")
        elif slozka.isdigit():
            folder_id = slozka
        else:
            hit = next((s for s in slozky if slozka.lower() in s["nazev"].lower()), None)
            if not hit:
                raise ValueError(
                    f"Složku '{slozka}' jsem nenašel. Dostupné: {[s['nazev'] for s in slozky]}"
                )
            folder_id = hit["id"]
        # IS stránkovací parametry ignoruje a vrací vše — stránkujeme na klientovi
        html = (
            first
            if folder_id == next((s["id"] for s in slozky if "Příchozí" in s["nazev"]), "")
            else c.get_text(f"/auth/mail/?folder_id={folder_id}")
        )
        data = mail.parse_seznam(html)
        if jen_neprectene:
            data["zpravy"] = [z for z in data["zpravy"] if z["neprectena"]]
        data["celkem"] = len(data["zpravy"])
        data["zpravy"] = data["zpravy"][max(0, start - 1) : max(0, start - 1) + pocet]
        data["slozka_id"] = folder_id
        return data


@mcp.tool()
def posta_cti(id: str, slozka: str = "") -> dict:
    """Přečte jednu zprávu (hlavička + tělo + přílohy). ID zprávy ze seznamu; složka volitelně (id)."""
    with is_client() as c:
        if slozka:
            html = c.get_text(f"/auth/mail/?show_mail={id};folder_id={slozka}")
        else:
            # bez složky: projdi složky a najdi tu, kde se zpráva otevře
            html = ""
            for s in mail.parse_slozky(c.get_text("/auth/mail/")):
                html = c.get_text(f"/auth/mail/?show_mail={id};folder_id={s['id']}")
                if f"mailHeader_{id}" in html:
                    break
        return mail.parse_detail(html, id)


# --------------------------------------------------------------- notifikace ---


@mcp.tool()
def udalosti() -> dict:
    """Záznamy událostí v ISu (změny zkušebních termínů, bloků, známek, diskusí, vývěsek)."""
    with is_client() as c:
        return events.parse_zobraz_log(c.get_text("/auth/udalosti/zobraz_log"))


@mcp.tool()
def pripomenuti() -> list[dict]:
    """'IS připomíná' — personalizovaná upozornění ke studiu (kredity, zápisy, povinnosti)."""
    with is_client() as c:
        return events.parse_is_pripomina(c.get_text("/auth/student/is_pripomina"))


@mcp.tool()
def dashboard() -> dict:
    """Přehled 'Co se právě děje / Co vás čeká / Poslední studijní události' z titulní stránky Studenta."""
    with is_client() as c:
        return events.parse_dashboard_ajax(
            c.get_text("/auth/student/index_ajax?option=udalosti-init")
        )


# ----------------------------------------------------------------- soubory ---


@mcp.tool()
def soubory_vypis(
    kod: str, cesta: str = "", fakulta: str = "", obdobi: str = "", rekurze: bool = False
) -> dict:
    """Výpis studijních materiálů předmětu (složky: um/odp/ode/op + soubory s odkazy ke stažení).
    Cesta = podsložka (např. 'um/prezentace'). Rekurze=True projde i podsložky (max. 60 stránek)."""
    with is_client() as c:
        ctx = get_context(c)
        ref = resolve_predmet(c, ctx, kod, fakulta, obdobi)
        base = ref.el_url + (cesta.strip("/") + "/" if cesta.strip("/") else "")
        koren = files.parse_vypis(c.get_text(base), base)
        if not rekurze:
            return koren
        # rekurzivní průchod
        vse_soubory = list(koren["soubory"])
        fronta = [s["url"] for s in koren["slozky"]]
        navstiveno = {base}
        while fronta and len(navstiveno) < 60:
            url = fronta.pop(0)
            if url in navstiveno:
                continue
            navstiveno.add(url)
            try:
                vypis = files.parse_vypis(c.get_text(url), url)
            except Exception:
                continue
            vse_soubory.extend(vypis["soubory"])
            fronta.extend(s["url"] for s in vypis["slozky"] if s["url"] not in navstiveno)
        return {
            "cesta": base,
            "slozky": koren["slozky"],
            "soubory": vse_soubory,
            "pocet_souboru": len(vse_soubory),
            "prochazeno_rekurzivne": True,
        }


@mcp.tool()
def soubor_cti(url: str, max_znaku: int = 20000, zkus_txt: bool = True) -> dict:
    """Stáhne soubor z IS. Textové soubory vrátí jako text; binární uloží do ISMU_DOWNLOAD_DIR a vrátí cestu.
    Pro prezentace/dokumenty automaticky zkusí i automaticky generovanou .txt verzi (zkus_txt)."""
    with is_client() as c:
        path = url
        if path.startswith("https://is.muni.cz"):
            path = path[len("https://is.muni.cz") :]
        if not path.startswith("/auth/"):
            raise ValueError(
                "Očekávám URL souboru z IS (začínající /auth/ nebo https://is.muni.cz/auth/)."
            )

        # .txt varianta pro binární dokumenty
        if zkus_txt and not files.is_text_content("", path):
            import re

            txt_path = re.sub(r"\.[a-zA-Z0-9]+$", ".txt", path.split("?")[0])
            if txt_path != path:
                try:
                    resp = c.get(txt_path)
                    if resp.status_code == 200 and len(resp.content) > 0:
                        text = resp.text
                        return {
                            "url": txt_path,
                            "typ": "txt-verze dokumentu",
                            "delka": len(text),
                            "text": text[:max_znaku],
                            "zkraceno": len(text) > max_znaku,
                        }
                except Exception:
                    pass

        resp = c.get(path)
        content_type = resp.headers.get("content-type", "")
        if files.is_text_content(content_type, path):
            text = resp.text
            return {
                "url": path,
                "typ": content_type or "text",
                "delka": len(text),
                "text": text[:max_znaku],
                "zkraceno": len(text) > max_znaku,
            }
        # binární: ulož
        nazev = path.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "soubor"
        cil = os.path.join(download_dir(), nazev)
        with open(cil, "wb") as f:
            f.write(resp.content)
        return {
            "url": path,
            "typ": content_type or "binární",
            "velikost": len(resp.content),
            "ulozeno": cil,
            "poznamka": "Binární soubor uložen na disk. Pro čtení obsahu zkuste .txt variantu (zkus_txt=True).",
        }


# -------------------------------------------------------- diskuse a vývěska ---


@mcp.tool()
def diskuse_prehled() -> dict:
    """Přehled diskusních fór (obecná, předmětová, tematická...) s odkazy na fóra."""
    with is_client() as c:
        return discussion.parse_diskuse_index(c.get_text("/auth/discussion/"))


@mcp.tool()
def diskuse_vlakno(url: str, max_prispevku: int = 30) -> dict:
    """Přečte vlákno diskuse (příspěvky: autor, datum, text). URL z přehledu nebo z kalendáře."""
    with is_client() as c:
        path = url
        if path.startswith("https://is.muni.cz"):
            path = path[len("https://is.muni.cz") :]
        data = discussion.parse_vlakno(c.get_text(path))
        data["prispevky"] = data["prispevky"][:max_prispevku]
        return data


@mcp.tool()
def vyveska(typ: str = "") -> dict:
    """Vývěska: důležité a sledované zprávy, pozvánky, inzerce. Typ: '' (vše), 'pozvanky', 'inzerce'."""
    with is_client() as c:
        path = "/auth/vyveska/"
        if typ in ("pozvanky", "inzerce"):
            path += f"?typ={typ}"
        return board.parse_vyveska(c.get_text(path))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
