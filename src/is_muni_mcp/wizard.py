"""Grafický průvodce instalací v prohlížeči (`is-muni-mcp wizard`).

Určeno pro uživatele bez terminálu: Setup aplikace (dvojklik) spustí tento
localhost server a otevře prohlížeč. Uživatel vyplní učo + heslo, zaškrtá
klienty (Codex, Claude Desktop, …) a průvodce za něj nainstaluje server
a zapíše konfigurace.

Bezpečnost: server poslouchá jen na 127.0.0.1, každá URL nese náhodný token,
heslo se drží jen v paměti po dobu jednoho přihlášení a po dokončení
(resp. po 15 minutách nečinnosti) se server sám vypne.
"""

from __future__ import annotations

import html
import secrets
import shutil
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__

IDLE_TIMEOUT_SEC = 15 * 60
AFTER_DONE_SEC = 120

CSS = """
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:640px;
margin:2em auto;padding:0 1em;color:#1a1a1a;line-height:1.5}
h1{font-size:1.5em}.card{border:1px solid #ddd;border-radius:12px;
padding:1.2em;margin:1em 0}.ok{background:#e8f5e9;border-color:#a5d6a7}
.err{background:#fdecea;border-color:#f5a8a8}
label{display:block;margin:.6em 0}input[type=text],input[type=password]{
width:100%;padding:.6em;font-size:1em;box-sizing:border-box}
.client{display:flex;gap:.6em;align-items:baseline;padding:.35em 0}
.client small{color:#666}button{font-size:1.1em;padding:.6em 1.4em;
background:#0b2c7a;color:#fff;border:0;border-radius:8px;cursor:pointer}
button:hover{background:#123a9e}.muted{color:#666;font-size:.9em}
code{background:#f0f0f0;padding:.1em .35em;border-radius:4px}
"""


def _page(title: str, body: str) -> bytes:
    return (
        "<!doctype html><html lang=cs><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body><h1>🎓 {html.escape(title)}</h1>{body}</body></html>"
    ).encode()


def install_server_binary() -> tuple[str, list[str]]:
    """Zajistí spustitelný server a vrátí (command, args) pro konfigurace.

    Ve frozen buildu (Setup aplikace) zkopíruje server do uživatelského
    adresáře; v běžné instalaci použije existující `is-muni-mcp`.
    """
    import os

    if getattr(sys, "frozen", False):
        exe = sys.executable
        base = os.path.dirname(exe)
        # macOS .app: server je v Contents/Resources vedle MacOS/ binary.
        candidates = [
            os.path.join(base, "..", "Resources", "is-muni-mcp"),
            os.path.join(base, "is-muni-mcp.exe"),
            os.path.join(base, "is-muni-mcp"),
        ]
        src = next((c for c in candidates if os.path.isfile(c)), exe)
        if os.name == "nt":
            dest_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "is-muni-mcp",
            )
            dest = os.path.join(dest_dir, "is-muni-mcp.exe")
        else:
            dest_dir = os.path.join(os.path.expanduser("~"), ".local", "bin")
            dest = os.path.join(dest_dir, "is-muni-mcp")
        os.makedirs(dest_dir, exist_ok=True)
        if os.path.abspath(src) != os.path.abspath(dest):
            shutil.copy2(src, dest)
        if os.name != "nt":
            os.chmod(dest, 0o755)
        return dest, []
    found = shutil.which("is-muni-mcp")
    if found:
        return found, []
    return sys.executable, ["-m", "is_muni_mcp"]


class _State:
    def __init__(self, token: str) -> None:
        self.token = token
        self.done = False
        self.deadline = time.time() + IDLE_TIMEOUT_SEC


def _form_page(state: _State, error: str = "", uco: str = "") -> bytes:
    from .targets import detect_targets

    rows = []
    for t in detect_targets():
        checked = "checked" if t.detected else ""
        rows.append(
            f"<label class=client><input type=checkbox name=clients "
            f"value='{t.id}' {checked}> <span><b>{html.escape(t.label)}</b><br>"
            f"<small>{html.escape(t.config_path)}</small></span></label>"
        )
    err = f"<div class='card err'>{html.escape(error)}</div>" if error else ""
    body = f"""
{err}
<div class=card><form method=post action='/setup?token={state.token}'>
<label>Učo (osobní číslo do IS MUNI)
<input type=text name=uco value='{html.escape(uco)}' autocomplete=username></label>
<label>Primární heslo do IS MUNI
<input type=password name=password autocomplete=current-password></label>
<p class=muted>Heslo se použije jen k přihlášení a nikam se neukládá.
Uloží se pouze session (viz níže).</p>
<h3>Zapsat do klientů</h3>
{"".join(rows)}
<p><button type=submit>Nainstalovat</button></p>
</form></div>
<p class=muted>Průvodce nainstaluje server <code>is-muni-mcp {html.escape(__version__)}</code>,
ověří přihlášení k IS a do zvolených klientů zapíše jeho konfiguraci.
Session se uloží do <code>~/.config/is-muni-mcp/cookie.txt</code> (jen pro vás).
Tato stránka běží pouze na vašem počítači a po dokončení se vypne.</p>
"""
    return _page("IS MUNI — instalace", body)


def _done_page(results: list[tuple[str, str, str]], jmeno: str) -> bytes:
    items = []
    for label, path, status in results:
        cls = "ok" if status == "OK" else "err"
        items.append(
            f"<div class='card {cls}'><b>{html.escape(label)}</b>: "
            f"{html.escape(status)}<br><small>{html.escape(path)}</small></div>"
        )
    body = f"""
<p>Přihlášeno jako <b>{html.escape(jmeno)}</b>. Server je nainstalovaný
a zapsaný do zvolených klientů:</p>
{"".join(items)}
<p><b>Teď restartujte své AI klienty</b> (Claude Desktop, VS Code, …)
a v chatu se objeví nástroje <code>is-muni</code>. Zkuste třeba:
<i>„Co mám příští týden v rozvrhu?“</i></p>
<p class=muted>Toto okno můžete zavřít — průvodce se sám vypne.</p>
"""
    return _page("Hotovo ✅", body)


def _make_handler(state: _State) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "is-muni-setup/1"

        def log_message(self, *a: object) -> None:
            pass  # ticho — běžíme na pozadí za prohlížečem

        def _check_token(self) -> bool:
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            if params.get("token", [""])[0] != state.token:
                self.send_response(403)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write("Špatný nebo chybějící token.".encode())
                return False
            return True

        def _send(self, data: bytes) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            if not self._check_token():
                return
            self._send(_form_page(state))

        def do_POST(self) -> None:  # noqa: N802
            from .auth import save_cookie, verify_cookie
            from .client import IsMuniError
            from .targets import detect_targets, write_target

            if not self._check_token():
                return
            length = int(self.headers.get("Content-Length", "0"))
            fields = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            uco = fields.get("uco", [""])[0].strip()
            password = fields.get("password", [""])[0]
            clients = fields.get("clients", [])
            labels = {t.id: t.label for t in detect_targets()}
            try:
                if not uco or not password:
                    raise IsMuniError("Vyplňte prosím učo i heslo.")
                if not clients:
                    raise IsMuniError("Vyberte aspoň jednoho klienta.")
                unknown = [c for c in clients if c not in labels]
                if unknown:
                    raise IsMuniError(f"Neznámý klient: {', '.join(unknown)}")
                try:
                    command, args = install_server_binary()
                except OSError as e:
                    raise IsMuniError(f"Instalace serveru selhala: {e}") from e
                from .auth import login as do_login

                try:
                    header = do_login(uco, password)
                finally:
                    del password
                save_cookie(header)
                info = verify_cookie(header)
                results: list[tuple[str, str, str]] = []
                for client_id in clients:
                    try:
                        path = write_target(client_id, command, args)
                        results.append((labels[client_id], path, "OK"))
                    except Exception as e:  # noqa: BLE001
                        results.append((labels[client_id], "", f"Chyba: {e}"))
                state.done = True
                state.deadline = min(state.deadline, time.time() + AFTER_DONE_SEC)
                self._send(_done_page(results, info.get("jmeno") or uco))
            except IsMuniError as e:
                self._send(_form_page(state, error=str(e), uco=uco))

    return Handler


def run_wizard(port: int = 0, open_browser: bool = True) -> str:
    """Spustí průvodce, otevře prohlížeč, po dokončení skončí. Vrátí URL."""
    state = _State(secrets.token_urlsafe(24))
    server = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(state))
    url = f"http://127.0.0.1:{server.server_address[1]}/?token={state.token}"
    print(f"Průvodce běží na {url}")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    server.timeout = 1.0
    try:
        # Po dokončení handler zkrátí deadline (rezerva na dočtení stránky).
        while time.time() < state.deadline:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print("Průvodce ukončen.")
    return url
