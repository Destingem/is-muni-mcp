"""Parser kalendáře a rozvrhu.

Zdroje dat (vše GET):
- /auth/calendar/ — vložený JSON s událostmi (vývěska, odevzdávárny, odpovědníky,
  události semestru, svátky, rozvrh) + legenda typů.
- /auth/rozvrh/zobraz/muj?...;format=ical — iCalendar export rozvrhu na semestr.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .common import clean_text
from .common import soup as make_soup

PRAGUE = ZoneInfo("Europe/Prague")

# Fallback mapování typů (primárně se čte legenda ze stránky)
TYP_FALLBACK = {
    "5_1": "Události z Vývěsky",
    "6_1": "Zkoušky",
    "6_2": "Odevzdávárny",
    "6_3": "Odpovědníky",
    "6_4": "Události v semestru",
    "6_5": "Svátky",
    "8_1": "Rozvrh",
    "8_2": "Rozvrh",
}


def parse_legenda(html: str) -> dict[str, str]:
    """Legenda kalendáře: sw_5_1 → 'Události z Vývěsky'."""
    s = make_soup(html)
    legenda: dict[str, str] = {}
    for div in s.select("div.legenda div[class*='sw_']"):
        label = clean_text(div)
        for cls in div.get("class", []):
            m = re.match(r"sw_(\d+_\d+)", cls)
            if m:
                legenda[m.group(1)] = label
    return legenda


def _extract_json_array(text: str, start: int) -> str:
    """Vyřízne JSON pole začínající na pozici start (bracket matching, respektuje řetězce)."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    raise ValueError("neukončené JSON pole")


def extract_kalendar_events(html: str) -> list[dict]:
    """Vytáhne vložený JSON s událostmi (js_init → RozvrhKalendar → params[0]).

    Událost: {title, start, end, typ, url, popis, ...} — projde surová pole + typ_label.
    """
    legenda = parse_legenda(html)
    legenda = {**TYP_FALLBACK, **legenda}

    # Vložený js_init JSON: { "params": [[udalosti], ...], "method": ..., "module": ... }.
    # Pořadí klíčů se může měnit, proto skenujeme všechny "params" bloky a bereme
    # ty, které obsahují události (dict s "start"/"title"+"typ").
    events: list[dict] = []
    seen_keys: set[str] = set()
    for m in re.finditer(r'"params"\s*:', html):
        arr_start = html.find("[", m.end())
        if arr_start == -1 or arr_start - m.end() > 20:
            continue
        try:
            raw = _extract_json_array(html, arr_start)
            params = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            continue
        # params[0] bývá seznam událostí; případně params je přímo seznam událostí
        candidates = (
            params[0]
            if (isinstance(params, list) and params and isinstance(params[0], list))
            else params
        )
        if not isinstance(candidates, list):
            continue
        for ev in candidates:
            if not isinstance(ev, dict):
                continue
            if "start" not in ev and "title" not in ev:
                continue
            key = str(ev.get("__iskup") or (ev.get("title"), ev.get("start"), ev.get("end")))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            ev = dict(ev)
            typ = str(ev.get("typ", ""))
            ev["typ_label"] = legenda.get(typ, typ)
            events.append(ev)
    return events


def filter_events(
    events: list[dict],
    od: date | None = None,
    do: date | None = None,
    typy: list[str] | None = None,
) -> list[dict]:
    """Filtr událostí podle data (start) a typu (kód '6_2' nebo label)."""
    out = []
    for ev in events:
        if typy:
            typ = str(ev.get("typ", ""))
            label = str(ev.get("typ_label", ""))
            if not any(t == typ or t.lower() in label.lower() for t in typy):
                continue
        if od or do:
            start = str(ev.get("start", ""))[:10]
            try:
                d = date.fromisoformat(start)
            except ValueError:
                out.append(ev)
                continue
            if od and d < od:
                continue
            if do and d > do:
                continue
        out.append(ev)
    return out


def parse_ical_events(ics_text: str, od: date | None = None, do: date | None = None) -> list[dict]:
    """Parsuje iCal export rozvrhu (včetně rozbalení RRULE) → seřazené události."""
    from icalendar import Calendar
    from recurring_ical_events import of as recurring_of

    cal = Calendar.from_ical(ics_text)
    start = datetime(od.year, od.month, od.day) if od else datetime(1990, 1, 1)
    end = datetime(do.year, do.month, do.day, 23, 59, 59) if do else datetime(2100, 1, 1)
    occurrences = recurring_of(cal).between(start, end)
    out: list[dict] = []
    for ev in occurrences:
        dtstart = ev.get("DTSTART")
        dtend = ev.get("DTEND")
        duration = ev.get("DURATION")
        s = dtstart.dt if dtstart else None
        e = dtend.dt if dtend else None
        if s is not None and e is None and duration is not None:
            try:
                e = s + duration.dt
            except Exception:
                pass
        out.append(
            {
                "nazev": str(ev.get("SUMMARY", "")),
                "zacatek": s.isoformat() if hasattr(s, "isoformat") else str(s),
                "konec": e.isoformat() if hasattr(e, "isoformat") else (str(e) if e else ""),
                "misto": str(ev.get("LOCATION", "")),
                "popis": str(ev.get("DESCRIPTION", "")),
                "uid": str(ev.get("UID", "")),
            }
        )
    out.sort(key=lambda x: x["zacatek"])
    return out
