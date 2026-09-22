"""Sdílené pomocné funkce pro parsery IS MUNI stránek."""

from __future__ import annotations

import html as html_module
import re

from bs4 import BeautifulSoup, Tag


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def clean_text(el: Tag | str | None) -> str:
    """Vrátí normalizovaný text elementu (sjednocené mezery)."""
    if el is None:
        return ""
    text = el.get_text(" ", strip=True) if isinstance(el, Tag) else str(el)
    text = html_module.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_is_params(href: str) -> dict[str, str]:
    """Parsuje IS-style parametry: /cesta?a=1;b=2 i klasické ?a=1&b=2."""
    params: dict[str, str] = {}
    if "?" in href:
        query = href.split("?", 1)[1].split("#", 1)[0]
        for part in re.split(r"[;&]", query):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
    else:
        # parametry mohou být i za středníkem bez otazníku
        for part in href.split(";")[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = v
    return params


def main_content(soup_obj: BeautifulSoup) -> Tag:
    """Vrátí hlavní obsah stránky (main#app_content) nebo celý dokument."""
    main = soup_obj.find("main", id="app_content")
    return main if isinstance(main, Tag) else soup_obj


def is_logged_in(html: str) -> bool:
    return "Odhlášení ze systému" in html or "Odhlásit se" in html


def parse_uco_from_osoba_link(html: str) -> str | None:
    m = re.search(r"/auth/osoba/(\d+)", html)
    return m.group(1) if m else None
