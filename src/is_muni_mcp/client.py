"""Read-only HTTP klient pro IS MUNI.

Klient záměrně umí pouze HTTP GET — neexistuje v něm žádná metoda pro POST/PUT/DELETE,
takže žádný nástroj nad ním postavený nemůže nic měnit (posílat poštu, registrovat
předměty, přihlašovat na zkoušky...). Všechny nástroje MCP jsou pouze ke čtení.

Klient je read-only ve smyslu "žádné změny ve studiu": umí GET a POST pouze na
povolené čtecí endpointy (typicky AJAX vyhledávání). Metody pro PUT/PATCH/DELETE
neexistují a POST na nic jiného než allowlist vyhodí chybu.

Autentizace: primárně session uložená příkazem `is-muni-mcp login`
(soubor ~/.config/is-muni-mcp/cookie.txt). Alternativně proměnné prostředí:

    ISMU_COOKIE="__Host-issession=...; __Host-iscreds=..."
    # nebo po částech:
    ISMU_SESSION=...  ISMU_CREDS=...
    # nebo ze souboru (první řádek = celý Cookie hlavičkový řetězec):
    ISMU_COOKIE_FILE=/cesta/k/souboru
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

BASE_URL = "https://is.muni.cz"
LOGIN_HOST = "muni.islogin.cz"

# Endpointy, na které smí klient posílat POST — výhradně čtecí (AJAX) operace:
# - katalog předmětů: vyhledávání (operace get_courses / refresh_pagination)
POST_READ_ALLOWLIST = ("/auth/predmety/predmety_ajax.pl",)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


class IsMuniError(Exception):
    """Obecná chyba IS MUNI klienta."""


class NotAuthenticatedError(IsMuniError):
    """Session vypršela nebo chybí — je potřeba se znovu přihlásit."""


#: Rada přidávaná k chybám o expiraci session.
RELOGIN_HINT = "Spusťte `is-muni-mcp login` a přihlaste se znovu."


class NotFoundError(IsMuniError):
    """Požadovaná stránka v IS neexistuje (HTTP 404)."""


def load_cookie_header() -> str:
    """Sestaví Cookie hlavičku: env proměnné mají přednost, pak uložená session."""
    cookie = os.environ.get("ISMU_COOKIE", "").strip()
    if cookie:
        return cookie
    cookie_file = os.environ.get("ISMU_COOKIE_FILE", "").strip()
    if cookie_file:
        with open(cookie_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
        raise IsMuniError(f"Soubor s cookie je prázdný: {cookie_file}")
    session = os.environ.get("ISMU_SESSION", "").strip()
    creds = os.environ.get("ISMU_CREDS", "").strip()
    if session and creds:
        return f"__Host-issession={session}; __Host-iscreds={creds}"
    # Uložená session z `is-muni-mcp login` (lazy import kvůli cyklu).
    from .auth import auto_login, env_credentials, load_stored_cookie

    try:
        return load_stored_cookie()
    except IsMuniError:
        pass
    # Poslední záchrana: automatické přihlášení údaji z prostředí
    # (ISMU_UCO + ISMU_PASSWORD, typicky z .mcpb instalace).
    # Případná chyba (např. špatné heslo) probublá ven tak, jak je.
    uco, password = env_credentials()
    if uco and password:
        return auto_login()
    raise IsMuniError(
        "Chybí přihlášení k IS MUNI. " + RELOGIN_HINT + " "
        "(Alternativně nastavte ISMU_COOKIE, dvojici ISMU_SESSION + ISMU_CREDS, "
        "ISMU_COOKIE_FILE, nebo ISMU_UCO + ISMU_PASSWORD — návod viz README.)"
    )


@dataclass
class IsMuniClient:
    """Tenký synchronní klient. Umí pouze GET (read-only)."""

    cookie_header: str | None = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        self._cookie = self.cookie_header or load_cookie_header()
        self._headers = {
            "Cookie": self._cookie,
            "User-Agent": USER_AGENT,
            "Accept-Language": "cs-CZ,cs;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers=self._headers,
            # Redirecty řešíme ručně v get(): httpx při redirectu zahazuje
            # Cookie hlavičku a IS by nás odhlásil.
            follow_redirects=False,
            timeout=self.timeout,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> IsMuniClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- jediné dvě nízkoúrovňové operace: GET text a GET bytes ---------------

    def _refresh_session_once(self) -> bool:
        """Pokusí se obnovit expirovanou session (max. 1× za život klienta).

        Funguje jen když jsou k dispozici údaje pro automatické přihlášení
        (ISMU_UCO + ISMU_PASSWORD). Vrátí True při úspěšné obnově.
        """
        if getattr(self, "_refreshed", False):
            return False
        self._refreshed = True
        from .auth import auto_login

        try:
            self._cookie = auto_login()
        except IsMuniError:
            return False
        self._headers["Cookie"] = self._cookie
        return True

    def get(self, path: str) -> httpx.Response:
        """Provede GET požadavek. Vyhodí NotAuthenticatedError při expiraci session."""
        try:
            return self._get_once(path)
        except NotAuthenticatedError:
            if self._refresh_session_once():
                return self._get_once(path)
            raise

    def _get_once(self, path: str) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._http.get(path)
                break
            except httpx.TransportError as e:
                # IS občas škobrtne — 2× zopakuj
                last_exc = e
                if attempt == 2:
                    raise IsMuniError(f"IS MUNI neodpovídá (síťová chyba): {e}") from e
        else:  # pragma: no cover
            raise IsMuniError(f"IS MUNI neodpovídá: {last_exc}")
        # ruční následování redirectů (se zachováním Cookie hlavičky)
        for _ in range(10):
            if resp.status_code not in (301, 302, 303, 307, 308):
                break
            loc = resp.headers.get("location", "")
            if not loc:
                break
            if LOGIN_HOST in loc:
                raise NotAuthenticatedError(
                    "Session k IS MUNI vypršela (přesměrování na přihlášení). " + RELOGIN_HINT
                )
            resp = self._http.get(loc, headers=self._headers)
        if LOGIN_HOST in str(resp.url):
            raise NotAuthenticatedError(
                "Session k IS MUNI vypršela (přesměrování na přihlášení). " + RELOGIN_HINT
            )
        if resp.status_code == 404:
            raise NotFoundError(f"Stránka v IS neexistuje: {path}")
        resp.raise_for_status()
        return resp

    def get_text(self, path: str) -> str:
        return self.get(path).text

    def get_bytes(self, path: str) -> bytes:
        return self.get(path).content

    def post_read(self, path: str, data: dict[str, str]) -> httpx.Response:
        """POST na povolený čtecí endpoint (viz POST_READ_ALLOWLIST).

        Slouží pouze ke čtení dat přes AJAX formuláře IS (např. vyhledávání
        v katalogu). Jakýkoliv jiný cíl je odmítnut — žádné změny ve studiu.
        """
        try:
            return self._post_read_once(path, data)
        except NotAuthenticatedError:
            if self._refresh_session_once():
                return self._post_read_once(path, data)
            raise

    def _post_read_once(self, path: str, data: dict[str, str]) -> httpx.Response:
        pure_path = path.split("?", 1)[0]
        if pure_path not in POST_READ_ALLOWLIST:
            raise IsMuniError(
                f"POST na '{path}' není povolen — klient smí zapisovat jen "
                f"na čtecí endpointy {list(POST_READ_ALLOWLIST)}."
            )
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._http.post(
                    path,
                    data=data,
                    headers={
                        **self._headers,
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                break
            except httpx.TransportError as e:
                last_exc = e
                if attempt == 2:
                    raise IsMuniError(f"IS MUNI neodpovídá (síťová chyba): {e}") from e
        else:  # pragma: no cover
            raise IsMuniError(f"IS MUNI neodpovídá: {last_exc}")
        if LOGIN_HOST in str(resp.url):
            raise NotAuthenticatedError(
                "Session k IS MUNI vypršela (přesměrování na přihlášení). " + RELOGIN_HINT
            )
        resp.raise_for_status()
        return resp

    def post_read_json(self, path: str, data: dict[str, str]) -> dict:
        return self.post_read(path, data).json()
