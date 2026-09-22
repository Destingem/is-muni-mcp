"""Zápis serveru do konfigurací MCP klientů.

Podporovaní klienti: claude-desktop, claude-code, codex, vscode, cursor.
Používá ho CLI (`is-muni-mcp setup`) i grafický průvodce (wizard).

Zásady:
- Existující konfigurace se nikdy nepřepisují celé — mění se jen záznam
  `is-muni`, zbytek souboru zůstává nedotčený (včetně komentářů v TOML).
- Zápis je idempotentní: opakované spuštění dá stejný výsledek.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

SERVER_NAME = "is-muni"

# Kódování pro TOML řetězce v configu Codexu.
_TOML_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}


def _toml_str(value: str) -> str:
    return '"' + "".join(_TOML_ESCAPES.get(ch, ch) for ch in value) + '"'


def _home() -> str:
    return os.path.expanduser("~")


def claude_desktop_config_path(home: str = "") -> str:
    home = home or _home()
    if sys.platform == "darwin":
        return os.path.join(
            home, "Library", "Application Support", "Claude", "claude_desktop_config.json"
        )
    if os.name == "nt":
        base = os.environ.get("APPDATA", "")
        return os.path.join(base, "Claude", "claude_desktop_config.json")
    return os.path.join(home, ".config", "Claude", "claude_desktop_config.json")


def claude_code_config_path(home: str = "") -> str:
    return os.path.join(home or _home(), ".claude.json")


def codex_config_path(home: str = "") -> str:
    return os.path.join(home or _home(), ".codex", "config.toml")


def vscode_mcp_path(home: str = "") -> str:
    home = home or _home()
    if sys.platform == "darwin":
        return os.path.join(home, "Library", "Application Support", "Code", "User", "mcp.json")
    if os.name == "nt":
        base = os.environ.get("APPDATA", "")
        return os.path.join(base, "Code", "User", "mcp.json")
    return os.path.join(home, ".config", "Code", "User", "mcp.json")


def cursor_mcp_path(home: str = "") -> str:
    return os.path.join(home or _home(), ".cursor", "mcp.json")


@dataclass
class Target:
    """Jeden podporovaný klient."""

    id: str
    label: str
    config_path: str
    detected: bool


def detect_targets(home: str = "") -> list[Target]:
    """Všichni klienti + zda vypadají nainstalovaně (config nebo binárka)."""
    home = home or _home()
    candidates = [
        ("claude-desktop", "Claude Desktop", claude_desktop_config_path(home), None),
        ("claude-code", "Claude Code", claude_code_config_path(home), "claude"),
        (
            "codex",
            "Codex a ChatGPT desktop (sdílená konfigurace)",
            codex_config_path(home),
            "codex",
        ),
        ("vscode", "VS Code", vscode_mcp_path(home), "code"),
        ("cursor", "Cursor", cursor_mcp_path(home), "cursor"),
    ]
    out = []
    for id_, label, path, binary in candidates:
        detected = os.path.exists(path) or (binary is not None and shutil.which(binary) is not None)
        out.append(Target(id_, label, path, detected))
    return out


def _write_json_config(path: str, key: str, entry: dict) -> str:
    """Zapíše entry pod key → SERVER_NAME, zbytek JSON zachová."""
    config: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                config = json.loads(content)
    if not isinstance(config, dict):
        raise ValueError(f"Konfigurace {path} nemá očekávaný formát (objekt).")
    config.setdefault(key, {})[SERVER_NAME] = entry
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def _stdio_entry(command: str, args: list[str], env: dict[str, str]) -> dict:
    entry: dict = {"command": command}
    if args:
        entry["args"] = args
    if env:
        entry["env"] = env
    return entry


def write_claude_desktop(command: str, args: list[str], home: str = "") -> str:
    return _write_json_config(
        claude_desktop_config_path(home),
        "mcpServers",
        _stdio_entry(command, args, {}),
    )


def write_vscode(command: str, args: list[str], home: str = "") -> str:
    entry = _stdio_entry(command, args, {})
    entry["type"] = "stdio"
    return _write_json_config(vscode_mcp_path(home), "servers", entry)


def write_cursor(command: str, args: list[str], home: str = "") -> str:
    return _write_json_config(cursor_mcp_path(home), "mcpServers", _stdio_entry(command, args, {}))


def write_claude_code(command: str, args: list[str], home: str = "") -> str:
    """Přednostně přes `claude mcp add`, jinak přímým zápisem do ~/.claude.json."""
    claude = shutil.which("claude")
    if claude and not home:
        r = subprocess.run([claude, "mcp", "add", SERVER_NAME, "--", command, *args])
        if r.returncode != 0:
            raise RuntimeError("Příkaz `claude mcp add` selhal.")
        return claude_code_config_path()
    # Přímý zápis (wizard bez claude binárky v PATH, nebo testy).
    return _write_json_config(
        claude_code_config_path(home),
        "mcpServers",
        _stdio_entry(command, args, {}),
    )


_SECTION_RE = re.compile(r"^\s*\[(?P<section>[^\]]+)\]\s*(?:#.*)?$")


def preview_target(client_id: str, command: str, args: list[str]) -> str:
    """Textová podoba záznamu pro daného klienta (pro --print-only)."""
    if client_id not in WRITERS:
        raise ValueError(f"Neznámý klient: {client_id}")
    if client_id == "codex":
        return _render_codex_block(command, args, {})
    key = "servers" if client_id == "vscode" else "mcpServers"
    entry = _stdio_entry(command, args, {})
    if client_id == "vscode":
        entry["type"] = "stdio"
    return json.dumps({key: {SERVER_NAME: entry}}, indent=2)


def _render_codex_block(command: str, args: list[str], env: dict[str, str]) -> str:
    lines = [f"[mcp_servers.{SERVER_NAME}]"]
    lines.append(f"command = {_toml_str(command)}")
    if args:
        lines.append("args = [" + ", ".join(_toml_str(a) for a in args) + "]")
    if env:
        lines.append("env = { " + ", ".join(f"{k} = {_toml_str(v)}" for k, v in env.items()) + " }")
    lines.append("startup_timeout_sec = 60")
    return "\n".join(lines) + "\n"


def write_codex(command: str, args: list[str], home: str = "") -> str:
    """Zapíše `[mcp_servers.is-muni]` do config.toml Codexu.

    Soubor se edituje po řádcích: odstraní se jen naše sekce
    (včetně případných podsekcí `[mcp_servers.is-muni.*]`) a na konec se
    připíše čerstvý blok. Komentáře a ostatní sekce zůstanou nedotčené.

    Pozn.: přihlašovací údaje se do configu Codexu nikdy nezapisují
    (je to plaintext soubor) — server používá uloženou session.
    """
    path = codex_config_path(home)
    block = _render_codex_block(command, args, {})
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(block)
        return path
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    kept: list[str] = []
    skipping = False
    for line in lines:
        m = _SECTION_RE.match(line)
        if m:
            section = m.group("section").strip()
            skipping = section == f"mcp_servers.{SERVER_NAME}" or section.startswith(
                f"mcp_servers.{SERVER_NAME}."
            )
            if skipping:
                continue
        if not skipping:
            kept.append(line)
    text = "".join(kept)
    if text and not text.endswith("\n"):
        text += "\n"
    if text and not text.endswith("\n\n"):
        text += "\n"
    text += block
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


WRITERS = {
    "claude-desktop": write_claude_desktop,
    "claude-code": write_claude_code,
    "codex": write_codex,
    "vscode": write_vscode,
    "cursor": write_cursor,
}


def write_target(
    client_id: str,
    command: str,
    args: list[str] | None = None,
    home: str = "",
) -> str:
    """Zapíše server do konfigurace daného klienta. Vrátí cestu k souboru."""
    if client_id not in WRITERS:
        raise ValueError(f"Neznámý klient: {client_id} (možnosti: {sorted(WRITERS)})")
    return WRITERS[client_id](command, args or [], home)
