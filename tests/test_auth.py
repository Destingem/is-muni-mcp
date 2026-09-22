"""Testy přihlašování a úschovy session (mocknutý HTTP, žádný network)."""

import os
import stat

import httpx
import pytest

from is_muni_mcp import auth
from is_muni_mcp.auth import LOGIN_FAILED_MARKER, LoginError
from is_muni_mcp.client import IsMuniError, load_cookie_header

LOGIN_URL = "https://muni.islogin.cz/login/TOKEN123"


def _resp(status, url, text="", headers=None):
    return httpx.Response(
        status,
        headers=headers or {},
        text=text,
        request=httpx.Request("GET", url),
    )


class FakeClient:
    """Minimální náhrada httpx.Client pro login flow."""

    def __init__(self, post_status=302, post_text="", post_loc="", jar=None):
        self._post_status = post_status
        self._post_text = post_text
        self._post_loc = post_loc
        self.cookies = jar if jar is not None else httpx.Cookies()
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url):
        if url == "https://is.muni.cz/auth/":
            return _resp(302, url, headers={"location": LOGIN_URL})
        if url == LOGIN_URL:
            return _resp(200, url, text='<form><input name="credential_0"></form>')
        raise AssertionError(f"neočekávané GET {url}")

    def post(self, url, data=None):
        self.posts.append((url, data))
        return _resp(
            self._post_status,
            url,
            text=self._post_text,
            headers={"location": self._post_loc} if self._post_loc else {},
        )


def _full_jar():
    jar = httpx.Cookies()
    jar.set("__Host-issession", "SESS")
    jar.set("__Host-iscreds", "CREDS")
    return jar


def test_login_ok(monkeypatch):
    fake = FakeClient(post_loc="https://is.muni.cz/auth/xyz", jar=_full_jar())
    monkeypatch.setattr(httpx, "Client", lambda **kw: fake)
    header = auth.login("990001", "tajne-heslo")
    assert header == "__Host-issession=SESS; __Host-iscreds=CREDS"
    # formulář se poslal se správnými políčky
    assert fake.posts[0][1]["credential_0"] == "990001"
    assert fake.posts[0][1]["credential_1"] == "tajne-heslo"
    assert fake.posts[0][1]["akce"] == "login"


def test_login_spatne_heslo(monkeypatch):
    fake = FakeClient(post_status=200, post_text=f"<div>{LOGIN_FAILED_MARKER}</div>")
    monkeypatch.setattr(httpx, "Client", lambda **kw: fake)
    with pytest.raises(LoginError, match="[Nn]esprávné"):
        auth.login("990001", "spatne")


def test_login_bez_redirectu(monkeypatch):
    class NoRedirect(FakeClient):
        def get(self, url):
            return _resp(200, url, text="divná stránka")

    monkeypatch.setattr(httpx, "Client", lambda **kw: NoRedirect())
    with pytest.raises(LoginError):
        auth.login("990001", "x")


def test_login_neuplna_session(monkeypatch):
    jar = httpx.Cookies()
    jar.set("__Host-issession", "SESS")  # chybí iscreds
    fake = FakeClient(post_loc="https://is.muni.cz/auth/xyz", jar=jar)
    monkeypatch.setattr(httpx, "Client", lambda **kw: fake)
    with pytest.raises(LoginError, match="kompletní session"):
        auth.login("990001", "x")


def test_login_validace_vstupu(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda **kw: FakeClient())
    with pytest.raises(LoginError):
        auth.login("", "x")
    with pytest.raises(LoginError):
        auth.login("990001", "")


def test_login_sitova_chyba(monkeypatch):
    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "Client", lambda **kw: Broken())
    with pytest.raises(IsMuniError, match="neodpovídá"):
        auth.login("990001", "x")


# -- úschova session ----------------------------------------------------


def test_save_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = auth.save_cookie("__Host-issession=A; __Host-iscreds=B")
    assert path == str(tmp_path / "is-muni-mcp" / "cookie.txt")
    assert auth.load_stored_cookie() == "__Host-issession=A; __Host-iscreds=B"
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600, oct(mode)
    assert auth.stored_cookie_permissions_ok()
    assert auth.clear_stored_cookie() is True
    assert auth.clear_stored_cookie() is False
    with pytest.raises(IsMuniError, match="login"):
        auth.load_stored_cookie()


def test_save_cookie_srovna_prava(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = auth.save_cookie("a=b")
    os.chmod(path, 0o644)
    assert not auth.stored_cookie_permissions_ok()
    auth.save_cookie("a=c")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


# -- priorita zdrojů v load_cookie_header --------------------------------


def test_cookie_header_env_ma_prednost(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    auth.save_cookie("__Host-issession=ULOZENA; __Host-iscreds=X")
    monkeypatch.setenv("ISMU_COOKIE", "__Host-issession=ENV; __Host-iscreds=Y")
    assert "ENV" in load_cookie_header()


def test_cookie_header_pouzije_ulozenou(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("ISMU_COOKIE", raising=False)
    monkeypatch.delenv("ISMU_COOKIE_FILE", raising=False)
    monkeypatch.delenv("ISMU_SESSION", raising=False)
    monkeypatch.delenv("ISMU_CREDS", raising=False)
    auth.save_cookie("__Host-issession=ULOZENA; __Host-iscreds=X")
    assert "ULOZENA" in load_cookie_header()


def test_cookie_header_chybi_navede_na_login(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("ISMU_COOKIE", raising=False)
    monkeypatch.delenv("ISMU_COOKIE_FILE", raising=False)
    monkeypatch.delenv("ISMU_SESSION", raising=False)
    monkeypatch.delenv("ISMU_CREDS", raising=False)
    with pytest.raises(IsMuniError, match="is-muni-mcp login"):
        load_cookie_header()
