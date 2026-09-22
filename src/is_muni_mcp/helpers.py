"""Pomocné funkce serveru: resolving předmětů, období, společný klient."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date

from .client import IsMuniClient
from .context import StudyContext, resolve_context


@dataclass
class PredmetRef:
    kod: str
    fakulta: str  # zkratka: fss, fi, ...
    obdobi_slug: str  # podzim2026
    predmet_url: str  # /auth/predmet/fss/podzim2026/BSSb1101
    el_url: str  # /auth/el/fss/podzim2026/BSSb1101/


_obdobi_slug_cache: dict[str, str] = {}  # obdobi_id -> slug
_predmet_cache: dict[str, PredmetRef] | None = None


def obdobi_nazev_na_slug(nazev: str) -> str:
    """'podzim 2026' → 'podzim2026'."""
    return re.sub(r"\s+", "", nazev.strip().lower())


def current_obdobi_slug(ctx: StudyContext) -> str:
    for o in ctx.obdobi:
        if o.obdobi_id == ctx.vybrane_obdobi:
            return obdobi_nazev_na_slug(o.nazev)
    return ""


def slug_na_obdobi_id(ctx: StudyContext, slug: str) -> str:
    for o in ctx.obdobi:
        if obdobi_nazev_na_slug(o.nazev) == slug.lower():
            return o.obdobi_id
    return ctx.vybrane_obdobi


def get_context(client: IsMuniClient) -> StudyContext:
    return resolve_context(client)


def get_predmet_map(client: IsMuniClient, ctx: StudyContext) -> dict[str, PredmetRef]:
    """Mapa kód → PredmetRef ze stránky rozvrhu (obsahuje odkazy všech předmětů)."""
    global _predmet_cache
    if _predmet_cache is not None:
        return _predmet_cache
    html = client.get_text(
        f"/auth/rozvrh/zobraz/muj?fakulta={ctx.vybrana_fakulta};obdobi={ctx.vybrane_obdobi}"
    )
    mapa: dict[str, PredmetRef] = {}
    for fak, slug, kod in set(re.findall(r"/auth/predmet/(\w+)/(\w+)/([A-Za-z0-9]+)", html)):
        mapa[kod] = PredmetRef(
            kod=kod,
            fakulta=fak,
            obdobi_slug=slug,
            predmet_url=f"/auth/predmet/{fak}/{slug}/{kod}",
            el_url=f"/auth/el/{fak}/{slug}/{kod}/",
        )
    _predmet_cache = mapa
    return mapa


def resolve_predmet(
    client: IsMuniClient, ctx: StudyContext, kod: str, fakulta: str = "", obdobi: str = ""
) -> PredmetRef:
    """Přeloží kód předmětu na URL. Explicitní fakulta/obdobi mají přednost."""
    kod = kod.strip()
    if fakulta and obdobi:
        slug = (
            obdobi
            if re.match(r"^(jaro|podzim|leto|zima)\d{4}$", obdobi)
            else obdobi_nazev_na_slug(obdobi)
        )
        return PredmetRef(
            kod,
            fakulta.lower(),
            slug,
            f"/auth/predmet/{fakulta.lower()}/{slug}/{kod}",
            f"/auth/el/{fakulta.lower()}/{slug}/{kod}/",
        )
    mapa = get_predmet_map(client, ctx)
    if kod in mapa:
        ref = mapa[kod]
        if fakulta or obdobi:
            slug = ref.obdobi_slug
            if obdobi:
                slug = (
                    obdobi
                    if re.match(r"^(jaro|podzim|leto|zima)\d{4}$", obdobi)
                    else obdobi_nazev_na_slug(obdobi)
                )
            fak = (fakulta or ref.fakulta).lower()
            return PredmetRef(
                kod, fak, slug, f"/auth/predmet/{fak}/{slug}/{kod}", f"/auth/el/{fak}/{slug}/{kod}/"
            )
        return ref
    raise ValueError(
        f"Předmět '{kod}' jsem nenašel v rozvrhu aktuálního období. "
        f"Zadejte i fakultu a období (např. fakulta='fss', obdobi='podzim2026')."
    )


def parse_datum(s: str | None, default: date | None = None) -> date | None:
    if not s:
        return default
    s = s.strip()
    if s.lower() in ("dnes", "today"):
        return date.today()
    return date.fromisoformat(s)


def download_dir() -> str:
    d = os.environ.get("ISMU_DOWNLOAD_DIR", os.path.expanduser("~/.cache/is-muni-mcp"))
    os.makedirs(d, exist_ok=True)
    return d
