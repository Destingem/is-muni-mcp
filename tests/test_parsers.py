"""Testy parserů na redigovaných fixture (žádný network)."""

from datetime import date
from pathlib import Path

import pytest

from is_muni_mcp.parsers import (
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

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def test_moje_predmety():
    p = student.parse_moje_predmety(load("predmety.html"))
    assert len(p) == 11
    assert p[0]["kod"] == "BSSb1101"
    assert "bezpečnostních" in p[0]["nazev"]
    assert p[0]["fakulta_id"] == "1423"


def test_moje_znamky():
    z = student.parse_moje_znamky(load("znamky.html"))
    assert len(z) == 12
    assert z[0]["kod"] == "BSSb1101"
    assert z[0]["obdobi"] == "podzim 2026"
    assert z[0]["kredity"] == "6"


def test_predmet_detail():
    d = student.parse_predmet_detail(load("predmet_detail.html"))
    assert d["kod"] == "BSSb1101"
    assert "bezpečnostních a strategických studií" in d["nazev"]
    assert len(d["vyucujici"]) == 3
    assert d["kredity"] == "6"
    assert d["ukonceni"] == "zk."
    assert "Anotace" not in d["anotace"] and len(d["anotace"]) > 100
    assert d["el_url"] == "/auth/el/fss/podzim2026/BSSb1101/"


def test_posta_slozky():
    s = mail.parse_slozky(load("mail_list.html"))
    assert len(s) == 5
    prichozi = next(x for x in s if "Příchozí" in x["nazev"])
    assert prichozi["id"] == "1476993"


def test_posta_seznam():
    data = mail.parse_seznam(load("mail_list.html"))
    assert len(data["zpravy"]) == 274
    assert sum(1 for z in data["zpravy"] if z["neprectena"]) == 103
    first = data["zpravy"][0]
    assert first["id"] == "385691214"
    assert first["od"].startswith("Odesílatel")
    assert first["datum"] == "dnes 11:10"


def test_posta_detail():
    m = mail.parse_detail(load("mail_detail.html"), "385691214")
    assert "odesilatel1@mail.muni.cz" in m["od"]
    assert "2026" in m["datum"]
    assert "redigované tělo" in m["telo"]
    assert m["predmet"]  # zalomený předmět poskládán


def test_kalendar():
    ev = calendar.extract_kalendar_events(load("kalendar.html"))
    assert len(ev) == 272
    labels = {x["typ_label"] for x in ev}
    assert {"Rozvrh", "Odevzdávárny", "Odpovědníky"} <= labels
    f = calendar.filter_events(ev, od=date(2026, 9, 18), do=date(2026, 9, 30))
    assert len(f) == 33
    dl = calendar.filter_events(ev, typy=["6_2", "6_3"])
    assert len(dl) == 9


def test_rozvrh_ical():
    r = calendar.parse_ical_events(load("rozvrh.ics"), od=date(2026, 9, 21), do=date(2026, 9, 27))
    assert len(r) == 11
    assert r[0]["zacatek"].startswith("2026-09-21T10:00")
    assert "BSSb1113" in r[0]["nazev"]
    assert r[0]["misto"] == "U35"


def test_bloky():
    b = notebooks.parse_bloky_nahled(load("bloky.html"))
    assert "Poslední změna" in b["posledni_zmena"]
    assert len(b["predmety"]) == 1
    assert "CORE042" in b["predmety"][0]["predmet"]
    assert [x["body"] for x in b["predmety"][0]["bloky"]] == [["4"], ["4"]]


def test_udalosti_prazdne():
    assert events.parse_zobraz_log(load("udalosti.html"))["prazdne"] is True


def test_pripomenuti():
    p = events.parse_is_pripomina(load("pripomina.html"))
    assert len(p) == 1
    assert "kreditů" in p[0]["text"]
    assert p[0]["plati_od"] == "18. 9. 2026 02:43"


def test_dashboard():
    d = events.parse_dashboard_ajax(load("dashboard.json"))
    assert set(d) == {"prave_se_deje", "ceka_vas", "posledni_udalosti"}
    assert len(d["prave_se_deje"]) == 4


def test_zkousky_prazdne():
    z = exams.parse_zkousky(load("zkousky.html"))
    assert z["prazdne"] is True
    assert "termín" in z["info"]


def test_el_vypis():
    v = files.parse_vypis(load("el_root.html"), "/auth/el/fss/podzim2026/BSSb1101/")
    assert len(v["slozky"]) == 4
    assert v["slozky"][0]["url"].endswith("/um/")
    v2 = files.parse_vypis(
        load("el_prezentace.html"), "/auth/el/fss/podzim2026/BSSb1101/um/prezentace/"
    )
    assert len(v2["soubory"]) == 1
    f = v2["soubory"][0]
    assert f["nazev"] == "Akademicky_zivot_101.pptx"
    assert "dk=REDACTED" in f["stahnout_url"]
    assert f["velikost"] == "10,9 MB"
    assert "Divišová" in f["vlozil"]


def test_diskuse_index():
    d = discussion.parse_diskuse_index(load("discussion.html"))
    assert len(d["sekce"]) == 2
    assert d["sekce"][0]["nazev"] == "Obecná fóra"
    assert d["sekce"][0]["fora"][0]["nove"] == "248"


def test_diskuse_vlakno():
    d = discussion.parse_vlakno(load("vlakno.html"))
    assert d["nazev"] == "Volejbal v Brně"
    assert len(d["prispevky"]) == 2
    assert d["prispevky"][0]["autor"] == "Student A"
    assert d["prispevky"][1]["autor"] == "Studentka B"
    assert "2026" in d["prispevky"][0]["datum"]


def test_vyveska():
    v = board.parse_vyveska(load("vyveska.html"))
    assert len(v["sekce"]) == 5
    assert v["sekce"][0]["nazev"] == "Důležité zprávy"
    assert len(v["sekce"][1]["zpravy"]) == 6
    assert v["sekce"][1]["zpravy"][0]["url"].startswith("/auth/noticeboard/")


def test_harmonogram():
    h = board.parse_harmonogram(load("harmonogram.html"), "FSS")
    assert "FSS" in h["fakulty"]
    assert len(h["udaje"]) == 48
    assert h["udaje"][0]["hodnoty"] == {"FSS": "podzim 2026"}


def test_osoba():
    o = person.parse_osoba(load("osoba.html"))
    assert o["jmeno"] == "Jan Novák"
    assert o["uco"] == "990001"
    assert o["email"] == "990001@mail.muni.cz"
    assert len(o["studia"]) == 1
    assert "Bezpečnostní a strategická studia" in o["studia"][0]["program"]


def test_read_only_client():
    """Klient nesmí umět měnit data: žádné PUT/PATCH/DELETE a POST jen na allowlist."""
    from is_muni_mcp.client import POST_READ_ALLOWLIST, IsMuniClient, IsMuniError

    for meth in ("put", "patch", "delete", "request"):
        assert not hasattr(IsMuniClient, meth), meth
    assert len(POST_READ_ALLOWLIST) >= 1
    c = IsMuniClient.__new__(IsMuniClient)  # bez networku, jen kontrola allowlistu
    with pytest.raises(IsMuniError):
        c.post_read("/auth/mail/mail_posli", {"to": "x"})
    with pytest.raises(IsMuniError):
        c.post_read("/auth/student/zapis", {})


def test_katalog_search():
    import json

    data = json.loads(load("katalog_search.json"))
    r = katalog.parse_search_response(data)
    assert r["pocet"] == 11
    assert len(r["predmety"]) == 11
    assert r["predmety"][0]["kod"] == "CORE014"
    assert r["predmety"][0]["fakulta"] == "fss"
    assert r["predmety"][0]["url"].startswith("/auth/predmet/")


def test_moje_seminare():
    s = seminars.parse_moje_seminare(load("seminare.html"))
    assert len(s["moje_skupiny"]) == 1
    g = s["moje_skupiny"][0]
    assert g["skupina"] == "POLb1001/02"
    assert "U34" in g["terminy"]
    assert "2. 9. 2026" in g["prihlasovani"]
    assert "27. 9. 2026" in g["odhlasovani"]
    assert s["predmety_se_skupinami"] == ["FSS:POLb1008 Tradice politického myšlení"]
    assert len(s["predmety_bez_skupin"]) == 9


def test_helpers():
    from is_muni_mcp.helpers import obdobi_nazev_na_slug, parse_datum

    assert obdobi_nazev_na_slug("podzim 2026") == "podzim2026"
    assert parse_datum("2026-09-18") == date(2026, 9, 18)
    assert parse_datum("") is None
