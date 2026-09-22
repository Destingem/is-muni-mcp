"""Testy CLI (bez networku, bez zápisu do skutečných konfigurací)."""

import json
import re
from pathlib import Path

from is_muni_mcp import __version__
from is_muni_mcp.cli import build_parser, main

ROOT = Path(__file__).parent.parent


def test_verze_v_souladu():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', pyproject, re.M)
    assert m, "pyproject.toml neobsahuje version"
    assert m.group(1) == __version__


def test_setup_json(capsys):
    rc = main(["setup", "--client", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mcpServers"]["is-muni"]["command"]


def test_setup_claude_desktop_print_only(capsys):
    rc = main(["setup", "--client", "claude-desktop", "--print-only"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "is-muni" in data["mcpServers"]


def test_setup_claude_code_print_only(capsys, monkeypatch):
    import shutil

    real_which = shutil.which
    # deterministicky: `claude` existuje → poradí terminálový příkaz
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/claude" if name == "claude" else real_which(name)
    )
    rc = main(["setup", "--client", "claude-code", "--print-only"])
    assert rc == 0
    assert "claude mcp add is-muni" in capsys.readouterr().out


def test_setup_claude_code_print_only_bez_binarky(capsys, monkeypatch):
    import shutil

    real_which = shutil.which
    # deterministicky: `claude` chybí → JSON náhled
    monkeypatch.setattr(
        shutil, "which", lambda name: None if name == "claude" else real_which(name)
    )
    rc = main(["setup", "--client", "claude-code", "--print-only"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "is-muni" in data["mcpServers"]


def test_login_cookie_spatny_format(capsys):
    rc = main(["login", "--cookie", "JSESSIONID=xxx"])
    assert rc == 1
    assert "iscreds" in capsys.readouterr().err


def test_login_cookie_ok(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rc = main(["login", "--cookie", "__Host-issession=A; __Host-iscreds=B"])
    assert rc == 0
    assert (tmp_path / "is-muni-mcp" / "cookie.txt").exists()


def test_parser_bez_prikazu():
    args = build_parser().parse_args([])
    assert args.command is None
