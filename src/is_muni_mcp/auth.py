"""Přihlašování k IS MUNI (učo + primární heslo) a úschova session.

IS MUNI používá centrální přihlášení (muni.islogin.cz) s jednoduchým
formulářem bez CAPTCHA:

    credential_0 = učo nebo přezdívka
    credential_1 = primární heslo

Postup: GET https://is.muni.cz/auth/ → redirect na islogin → GET stránky
→ POST přihlašovacích údajů → redirect zpět na is.muni.cz s nastavenou
session. Heslo se nikam neukládá — uloží se pouze session cookie
(``__Host-issession`` + ``__Host-iscreds``) do souboru s právy 0600:

    ~/.config/is-muni-mcp/cookie.txt   (resp. $XDG_CONFIG_HOME)

Tento modul je záměrně oddělený od read-only datového klienta
(:mod:`is_muni_mcp.client`) — přihlášení je jednorázový akt uživatele,
nikoliv součást čtení dat.
"""

from __future__ import annotations

import os
import stat

import httpx

from .client import BASE_URL, LOGIN_HOST, USER_AGENT, IsMuniError

CONFIG_DIR_NAME = "is-muni-mcp"
COOKIE_FILE_NAME = "cookie.txt"

#: Text, který islogin vrátí při špatném jménu/heslu (HTTP 200, bez redirectu).
LOGIN_FAILED_MARKER = "Nesprávné přihlašovací jméno nebo heslo"


class LoginError(IsMuniError):
    """Přihlášení se nezdařilo (špatné údaje / neočekávaná odpověď IS)."""


#: Proměnné prostředí pro automatické přihlášení (např. z .mcpb balíčku,
#: kde je vyplní uživatel v instalačním dialogu Claude Desktopu).
UCO_ENV_VAR = "ISMU_UCO"
PASSWORD_ENV_VAR = "ISMU_PASSWORD"


def env_credentials() -> tuple[str, str]:
    """Učo + heslo z proměnných prostředí (prázdné řetězce, když chybí)."""
    return (
        os.environ.get(UCO_ENV_VAR, "").strip(),
        os.environ.get(PASSWORD_ENV_VAR, ""),
    )


def auto_login() -> str:
    """Přihlásí se údaji z prostředí a session uloží. Vyhodí LoginError.

    Používá se, když není žádná jiná session (typicky .mcpb instalace)
    a při automatické obnově expirované session. Heslo se nikam neukládá.
    """
    uco, password = env_credentials()
    if not uco or not password:
        raise IsMuniError(
            "Chybí přihlášení k IS MUNI a nejsou k dispozici údaje pro "
            "automatické přihlášení. Spusťte `is-muni-mcp login`."
        )
    try:
        header = login(uco, password)
    finally:
        del password
    save_cookie(header)
    return header


def config_dir() -> str:
    """Adresář pro konfiguraci (vytvoří ho, pokud chybí)."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, CONFIG_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def cookie_file_path() -> str:
    """Cesta k souboru s uloženou session."""
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, CONFIG_DIR_NAME, COOKIE_FILE_NAME)


def save_cookie(cookie_header: str) -> str:
    """Uloží session cookie do config souboru s právy 0600. Vrátí cestu."""
    path = cookie_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Otevři s 0600 hned při vytvoření (žádné okno s volnějšími právy).
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(cookie_header.strip() + "\n")
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    # Srovnej práva i pro dříve existující soubor.
    os.chmod(path, 0o600)
    return path


def load_stored_cookie() -> str:
    """Přečte uloženou session. Vyhodí IsMuniError, když chybí."""
    path = cookie_file_path()
    if not os.path.exists(path):
        raise IsMuniError(
            "Nejste přihlášeni k IS MUNI. Spusťte `is-muni-mcp login` "
            "a přihlaste se svým učem a primárním heslem."
        )
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    raise IsMuniError(
        f"Soubor s přihlášením je prázdný: {path}. Spusťte znovu `is-muni-mcp login`."
    )


def clear_stored_cookie() -> bool:
    """Smaže uloženou session. Vrátí True, pokud něco smazal."""
    path = cookie_file_path()
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def stored_cookie_permissions_ok() -> bool:
    """Kontrola, že soubor s cookie nemá volnější práva než 0600."""
    path = cookie_file_path()
    if not os.path.exists(path):
        return True
    mode = stat.S_IMODE(os.stat(path).st_mode)
    return mode & 0o077 == 0


def login(uco: str, password: str, timeout: float = 30.0) -> str:
    """Přihlásí se učem+heslem a vrátí Cookie hlavičku s platnou session.

    Heslo se nikam neukládá ani neloguje. Při špatných údajích vyhodí
    :class:`LoginError`, při síťové chybě :class:`IsMuniError`.
    """
    uco = (uco or "").strip()
    if not uco:
        raise LoginError("Zadejte své učo (nebo přezdívku).")
    if not password:
        raise LoginError("Zadejte své primární heslo do IS MUNI.")

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "cs-CZ,cs;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(headers=headers, follow_redirects=False, timeout=timeout) as http:
            # 1) Kam nás IS pošle se přihlásit (+ úvodní cookies).
            resp = http.get(f"{BASE_URL}/auth/")
            login_url = resp.headers.get("location", "")
            if resp.status_code not in (301, 302, 303, 307, 308) or not login_url:
                raise LoginError(
                    "IS MUNI vrátil neočekávanou odpověď (chybí přesměrování "
                    "na přihlášení). Zkuste to prosím znovu později."
                )
            if LOGIN_HOST not in login_url and "/auth/" not in login_url:
                raise LoginError(f"IS MUNI přesměroval na neočekávanou adresu: {login_url}")

            # 2) Načti přihlašovací stránku (stav session na straně IS).
            page = http.get(login_url)
            if page.status_code != 200 or "credential_0" not in page.text:
                raise LoginError(
                    "Přihlašovací stránka IS vypadá jinak, než čekáme "
                    "(změna na straně MU?). Nahláste prosím issue v repozitáři."
                )

            # 3) Odešli přihlašovací formulář.
            form_url = str(page.url)
            done = http.post(
                form_url,
                data={
                    "akce": "login",
                    "credential_0": uco,
                    "credential_1": password,
                    "uloz": "uloz",
                },
            )
    except httpx.TransportError as e:
        raise IsMuniError(f"IS MUNI neodpovídá (síťová chyba): {e}") from e

    # 4) Úspěch = redirect zpět na is.muni.cz; neúspěch = 200 + chybová hláška.
    if done.status_code in (301, 302, 303, 307, 308):
        loc = done.headers.get("location", "")
        if LOGIN_HOST in loc:
            raise LoginError("Přihlášení se nezdařilo — IS vrátil zpět na přihlašovací stránku.")
        # Session cookies drží httpx cookie jar (issession + iscreds).
        # (Klient je sice zavřený, ale jar zůstává — close() ho nemaže.)
        parts = []
        for name in ("__Host-issession", "__Host-iscreds"):
            value = http.cookies.get(name, "")
            if value:
                parts.append(f"{name}={value}")
        if len(parts) < 2:
            raise LoginError(
                "Přihlášení proběhlo, ale IS nevrátil kompletní session. Zkuste to prosím znovu."
            )
        return "; ".join(parts)

    if LOGIN_FAILED_MARKER in done.text:
        raise LoginError("Nesprávné učo nebo heslo. Zkontrolujte údaje a zkuste to znovu.")
    raise LoginError(
        "Přihlášení se nezdařilo (neočekávaná odpověď IS). Zkuste to prosím znovu později."
    )


def verify_cookie(cookie_header: str, timeout: float = 30.0) -> dict:
    """Ověří session proti IS. Vrátí {ok, jmeno, uco} (bez vyhození)."""
    from .client import IsMuniClient
    from .context import resolve_context

    try:
        client = IsMuniClient(cookie_header=cookie_header, timeout=timeout)
    except Exception:
        return {"ok": False, "jmeno": "", "uco": ""}
    try:
        ctx = resolve_context(client)
        if ctx.uco:
            return {"ok": True, "jmeno": ctx.jmeno, "uco": ctx.uco}
        return {"ok": False, "jmeno": "", "uco": ""}
    except Exception:
        return {"ok": False, "jmeno": "", "uco": ""}
    finally:
        client.close()
