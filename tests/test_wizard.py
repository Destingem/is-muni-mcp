"""Testy setup wizardu (localhost server ve vlákně, mocknutý login)."""

import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from is_muni_mcp import auth, targets, wizard


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(targets, "_home", lambda: str(tmp_path))
    state = wizard._State("test-token")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), wizard._make_handler(state))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, state, tmp_path
    httpd.shutdown()
    thread.join(timeout=5)


def _url(server, path="/"):
    port = server.server_address[1]
    return f"http://127.0.0.1:{port}{path}"


def test_token_gate(server):
    httpd, _, _ = server
    # bez tokenu 403
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(_url(httpd, "/"))
    assert exc.value.code == 403
    # se tokenem 200 + formulář
    with urllib.request.urlopen(_url(httpd, "/?token=test-token")) as r:
        body = r.read().decode()
    assert "is-muni" in body.lower() or "IS MUNI" in body
    assert "clients" in body


def test_setup_uspech(server, monkeypatch):
    httpd, state, tmp_path = server
    monkeypatch.setattr(auth, "login", lambda u, p: "__Host-issession=X; __Host-iscreds=Y")
    monkeypatch.setattr(auth, "verify_cookie", lambda h: {"ok": True, "jmeno": "Jan", "uco": "1"})
    monkeypatch.setattr(wizard, "install_server_binary", lambda: ("/bin/s", []))

    data = urllib.parse.urlencode(
        [("uco", "990001"), ("password", "x"), ("clients", "codex"), ("clients", "cursor")]
    ).encode()
    req = urllib.request.Request(_url(httpd, "/setup?token=test-token"), data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
    assert "Hotovo" in body
    assert state.done is True
    # configy zapsané pod tmp HOME (targets._home je mocknuté)
    assert (tmp_path / ".codex" / "config.toml").exists()
    assert (tmp_path / ".cursor" / "mcp.json").exists()
    # session uložena
    assert "X" in auth.load_stored_cookie()


def test_setup_spatne_heslo(server, monkeypatch):
    httpd, state, _ = server

    def boom(u, p):
        raise auth.LoginError("Nesprávné učo nebo heslo.")

    monkeypatch.setattr(auth, "login", boom)
    monkeypatch.setattr(wizard, "install_server_binary", lambda: ("/bin/s", []))
    data = urllib.parse.urlencode(
        [("uco", "990001"), ("password", "spatne"), ("clients", "codex")]
    ).encode()
    req = urllib.request.Request(_url(httpd, "/setup?token=test-token"), data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
    assert "Nesprávné" in body
    assert state.done is False


def test_setup_bez_klienta(server):
    httpd, _, _ = server
    data = urllib.parse.urlencode([("uco", "1"), ("password", "x")]).encode()
    req = urllib.request.Request(_url(httpd, "/setup?token=test-token"), data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
    assert "aspoň jednoho klienta" in body


def test_install_server_binary_which(monkeypatch):
    monkeypatch.delattr("sys.frozen", raising=False)
    monkeypatch.setattr(wizard.shutil, "which", lambda _: "/usr/local/bin/is-muni-mcp")
    assert wizard.install_server_binary() == ("/usr/local/bin/is-muni-mcp", [])
