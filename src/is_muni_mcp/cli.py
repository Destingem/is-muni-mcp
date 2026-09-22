"""Příkazová řádka `is-muni-mcp`.

Bez argumentů spustí MCP server přes stdio (zpětně kompatibilní chování
pro existující konfigurace klientů). Subpříkazy:

    is-muni-mcp login     přihlášení učem + heslem (uloží session)
    is-muni-mcp status    ověření, že přihlášení funguje
    is-muni-mcp logout    smazání uložené session
    is-muni-mcp setup     zápis do konfigurace Claude Desktop / Claude Code
    is-muni-mcp serve     spuštění serveru (stdio / streamable-http)
"""

from __future__ import annotations

import argparse
import getpass
import json
import shutil
import sys

from . import __version__
from .auth import (
    clear_stored_cookie,
    load_stored_cookie,
    login,
    save_cookie,
    verify_cookie,
)
from .client import IsMuniError


def _server_command_args() -> tuple[str, list[str]]:
    """Příkaz pro spuštění serveru z konfigurace MCP klienta."""
    exe = shutil.which("is-muni-mcp")
    if exe:
        return exe, []
    # Fallback: aktuální Python + modul (vývojové prostředí).
    return sys.executable, ["-m", "is_muni_mcp"]


def cmd_login(args: argparse.Namespace) -> int:
    if args.cookie:
        header = args.cookie.strip()
        if "__Host-issession" not in header or "__Host-iscreds" not in header:
            print(
                "Chyba: cookie musí obsahovat __Host-issession i __Host-iscreds.",
                file=sys.stderr,
            )
            return 1
        path = save_cookie(header)
        print(f"Session uložena do {path}")
        return 0

    uco = args.uco or input("Učo (nebo přezdívka): ").strip()
    try:
        password = getpass.getpass("Primární heslo do IS MUNI: ")
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return 1
    print("Přihlašuji k IS MUNI…")
    try:
        header = login(uco, password)
    except IsMuniError as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    finally:
        del password
    path = save_cookie(header)
    info = verify_cookie(header)
    if info["ok"]:
        print(f"Přihlášeno jako {info['jmeno']} (učo {info['uco']}).")
    else:
        print("Session uložena, ale ověření se nezdařilo — zkuste `status`.")
    print(f"Uloženo do {path} (pouze session, heslo se neukládá).")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    try:
        header = load_stored_cookie()
    except IsMuniError as e:
        if args.json:
            print(json.dumps({"ok": False, "chyba": str(e)}, ensure_ascii=False))
        else:
            print(f"Nepřihlášeno: {e}")
        return 1
    info = verify_cookie(header)
    if args.json:
        print(json.dumps(info, ensure_ascii=False))
    elif info["ok"]:
        print(f"Přihlášeno jako {info['jmeno']} (učo {info['uco']}). Session platí.")
    else:
        print("Uložená session nefunguje (vypršela?). Spusťte `is-muni-mcp login`.")
        return 1
    return 0


def cmd_logout(_args: argparse.Namespace) -> int:
    if clear_stored_cookie():
        print("Odhlášeno (uložená session smazána).")
    else:
        print("Nic k odhlášení (žádná uložená session).")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    from .targets import SERVER_NAME, preview_target, write_target

    command, cmd_args = _server_command_args()
    entry: dict = {"command": command}
    if cmd_args:
        entry["args"] = cmd_args

    if args.client == "json":
        print(json.dumps({"mcpServers": {SERVER_NAME: entry}}, indent=2))
        return 0

    if args.print_only:
        if args.client == "claude-code" and shutil.which("claude"):
            print("Spusťte v terminálu:")
            print(
                f"  claude mcp add is-muni -- {command}"
                + (f" {' '.join(cmd_args)}" if cmd_args else "")
            )
            return 0
        try:
            print(preview_target(args.client, command, cmd_args))
        except ValueError as e:
            print(f"Chyba: {e}", file=sys.stderr)
            return 1
        return 0

    try:
        path = write_target(args.client, command, cmd_args)
    except (ValueError, RuntimeError) as e:
        print(f"Chyba: {e}", file=sys.stderr)
        return 1
    print(f"Zapsáno do {path}")
    print("Restartujte klienta — objeví se nástroje `is-muni`.")
    return 0


def cmd_wizard(args: argparse.Namespace) -> int:
    from .wizard import run_wizard

    run_wizard(port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import mcp

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="is-muni-mcp",
        description="Read-only MCP server pro IS MUNI. Bez příkazu spustí server (stdio).",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command")

    pl = sub.add_parser("login", help="Přihlásit se učem a heslem (uloží session).")
    pl.add_argument("--uco", default="", help="Učo nebo přezdívka (jinak se zeptá).")
    pl.add_argument(
        "--cookie",
        default="",
        help="Alternativa: vložit hotovou Cookie hlavičku z prohlížeče.",
    )
    pl.set_defaults(func=cmd_login)

    ps = sub.add_parser("status", help="Ověřit, že přihlášení funguje.")
    ps.add_argument("--json", action="store_true", help="Výstup jako JSON.")
    ps.set_defaults(func=cmd_status)

    po = sub.add_parser("logout", help="Smazat uloženou session.")
    po.set_defaults(func=cmd_logout)

    pc = sub.add_parser("setup", help="Zapsat server do konfigurace MCP klienta.")
    pc.add_argument(
        "--client",
        required=True,
        choices=["claude-desktop", "claude-code", "codex", "vscode", "cursor", "json"],
        help="Cílový klient (json = jen vytisknout konfiguraci).",
    )
    pc.add_argument(
        "--print-only",
        action="store_true",
        help="Jen vytisknout, nic nezapisovat / nespouštět.",
    )
    pc.set_defaults(func=cmd_setup)

    pv = sub.add_parser("serve", help="Spustit MCP server.")
    pv.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http"],
        help="Transport (streamable-http = vzdálený přístup, např. vlastní hosting).",
    )
    pv.add_argument("--host", default="127.0.0.1")
    pv.add_argument("--port", type=int, default=8000)
    pv.add_argument("--path", default="/mcp")
    pv.set_defaults(func=cmd_serve)

    pw = sub.add_parser("wizard", help="Grafický průvodce v prohlížeči (instalace bez terminálu).")
    pw.add_argument("--port", type=int, default=0, help="Port (0 = náhodný).")
    pw.add_argument("--no-browser", action="store_true", help="Neotevírat prohlížeč (vypíše URL).")
    pw.set_defaults(func=cmd_wizard)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        # Bez argumentů: chovej se jako server (zpětná kompatibilita).
        from .server import main as serve_main

        serve_main()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
