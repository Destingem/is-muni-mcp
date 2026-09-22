"""Parser IS pošty (/auth/mail/). Pouze čtení: složky, seznam, detail zprávy."""

from __future__ import annotations

import re

from .common import clean_text, parse_is_params
from .common import soup as make_soup


def parse_slozky(html: str) -> list[dict]:
    """Složky ze select#folder_id → [{id, nazev, pocet}]."""
    s = make_soup(html)
    slozky: list[dict] = []
    sel = s.find("select", id="folder_id")
    if not sel:
        return slozky
    for opt in sel.find_all("option"):
        value = str(opt.get("value", ""))
        if value == "all":
            continue
        text = clean_text(opt)
        m = re.match(r"^(.*?)(?:\s*\((\d+)\))?$", text)
        nazev = m.group(1).strip() if m else text
        pocet = int(m.group(2)) if m and m.group(2) else 0
        slozky.append({"id": value, "nazev": nazev, "pocet": pocet})
    return slozky


def parse_seznam(html: str) -> dict:
    """Seznam zpráv ve složce → {zpravy: [...], strankovani: {...}}.

    zpráva: {id, od, od_uco, od_email, predmet, datum, velikost, neprectena, url}
    """
    s = make_soup(html)
    zpravy: list[dict] = []
    seen: set[str] = set()
    for tr in s.find_all("tr", id=re.compile(r"^mail_\d+$")):
        m = re.search(r"mail_(\d+)", str(tr.get("id", "")))
        if not m:
            continue
        msg_id = m.group(1)
        if msg_id in seen:
            continue
        seen.add(msg_id)
        classes = tr.get("class", [])
        neprectena = "riadok_new" in classes

        from_td = tr.find("td", id=f"from_id_{msg_id}")
        od_email = str(from_td.get("data-from_adr", "")) if from_td else ""
        od_uco = str(from_td.get("data-from_uco", "")) if from_td else ""

        jmeno_a = tr.find("a", class_="jmeno")
        od = clean_text(jmeno_a) if jmeno_a else ""

        read_a = tr.find("a", id=f"read_link_{msg_id}")
        if not read_a:
            read_a = tr.find("a", href=re.compile(r"show_mail=" + msg_id))
        predmet = clean_text(read_a) if read_a else ""
        url = str(read_a.get("href", "")) if read_a else ""

        tds = tr.find_all("td")
        datum = clean_text(tds[-2]) if len(tds) >= 2 else ""
        velikost = clean_text(tds[-1]) if len(tds) >= 1 else ""

        zpravy.append(
            {
                "id": msg_id,
                "od": od,
                "od_uco": od_uco,
                "od_email": od_email,
                "predmet": predmet,
                "datum": datum,
                "velikost": velikost,
                "neprectena": neprectena,
                "url": url,
            }
        )

    # stránkování: odkazy start=N
    strankovani = {"dalsi_start": None, "celkem_stran": None}
    starts: list[int] = []
    for a in s.find_all("a", href=re.compile(r"start=\d+")):
        p = parse_is_params(str(a["href"]))
        if p.get("start", "").isdigit():
            starts.append(int(p["start"]))
    if starts:
        strankovani["max_start"] = max(starts)
    return {"zpravy": zpravy, "strankovani": strankovani}


def parse_detail(html: str, msg_id: str) -> dict:
    """Detail zprávy → {id, od, datum, komu, predmet, telo, prilohy, url_dalsi}."""
    s = make_soup(html)
    header = s.find("div", id=f"mailHeader_{msg_id}")
    od = datum = komu = predmet = ""
    if header:
        lines = [ln.strip() for ln in header.get_text("\n").splitlines()]
        lines = [ln for ln in lines if ln]
        current = None
        for line in lines:
            m = re.match(r"^(From|Date|To|Subject):\s*(.*)$", line)
            if m:
                current = m.group(1)
                value = m.group(2)
                if current == "From":
                    od = value
                elif current == "Date":
                    datum = value
                elif current == "To":
                    komu = value
                elif current == "Subject":
                    predmet = value
            elif current == "Subject" and "přidat do adresáře" not in line:
                # zalomený předmět pokračuje na dalším řádku
                predmet += " " + line
        predmet = re.sub(r"\s+", " ", predmet).strip()

    body = s.find("div", class_="mB_zprava")
    telo = body.get_text("\n", strip=True) if body else ""

    # přílohy: odkazy ke stažení v okolí zprávy (best-effort)
    prilohy: list[dict] = []
    if body:
        container = body.find_parent("td") or body.parent
        for a in container.find_all("a", href=True):
            href = str(a["href"])
            if re.search(r"(download|attach|priloha|stahnout)", href, re.IGNORECASE):
                prilohy.append({"nazev": clean_text(a), "url": href})

    dalsi = None
    prev_next = s.find("div", class_="mB_prev_next_top")
    if prev_next:
        a = prev_next.find("a", href=re.compile(r"show_mail="))
        if a:
            dalsi = str(a.get("href"))

    return {
        "id": msg_id,
        "od": od,
        "datum": datum,
        "komu": komu,
        "predmet": predmet,
        "telo": telo,
        "prilohy": prilohy,
        "url_dalsi": dalsi,
    }
