"""Testy zapisovačů konfigurací klientů (tmp HOME, žádné skutečné configy)."""

import json
from pathlib import Path

import pytest

from is_muni_mcp import targets


@pytest.fixture(autouse=True)
def _izolace_appdata(tmp_path, monkeypatch):
    # Na Windows vedou některé cesty přes %APPDATA% — přesměrovat do tmp,
    # aby testy nezapisovaly do skutečného profilu ani ho nečetly.
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def test_write_codex_novy_soubor(tmp_path):
    home = str(tmp_path)
    path = targets.write_codex("/bin/is-muni-mcp", [], home)
    assert path == str(tmp_path / ".codex" / "config.toml")
    text = Path(path).read_text(encoding="utf-8")
    assert "[mcp_servers.is-muni]" in text
    assert 'command = "/bin/is-muni-mcp"' in text


def test_write_codex_zachova_zbytek(tmp_path):
    cfg = tmp_path / ".codex" / "config.toml"
    cfg.parent.mkdir()
    cfg.write_text(
        '# muj komentar\nmodel = "gpt-5"\n\n[mcp_servers.jiny]\ncommand = "x"\n',
        encoding="utf-8",
    )
    targets.write_codex("/bin/is-muni-mcp", ["a", "b c"], str(tmp_path))
    text = cfg.read_text(encoding="utf-8")
    assert "# muj komentar" in text
    assert 'model = "gpt-5"' in text
    assert '[mcp_servers.jiny]\ncommand = "x"' in text
    assert 'args = ["a", "b c"]' in text


def test_write_codex_idempotentni_a_prepise_svuj_blok(tmp_path):
    home = str(tmp_path)
    targets.write_codex("/stary", [], home)
    # uživatel si ručně přidal podsekci — přepis ji smaže (je naše)
    cfg = Path(home) / ".codex" / "config.toml"
    with open(cfg, "a", encoding="utf-8") as f:
        f.write('\n[mcp_servers.is-muni.tools.x]\napproval_mode = "approve"\n')
    targets.write_codex("/novy", [], home)
    text = cfg.read_text(encoding="utf-8")
    assert text.count("[mcp_servers.is-muni]") == 1
    assert "approval_mode" not in text
    assert 'command = "/novy"' in text


def test_write_codex_escapuje(tmp_path):
    targets.write_codex('C:\\cesta\\s "uvozovkou"', [], str(tmp_path))
    text = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert 'command = "C:\\\\cesta\\\\s \\"uvozovkou\\""' in text


def test_write_json_klienti(tmp_path):
    home = str(tmp_path)
    targets.write_cursor("/bin/s", [], home)
    data = json.loads((tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert data["mcpServers"]["is-muni"]["command"] == "/bin/s"

    targets.write_vscode("/bin/s", [], home)
    from is_muni_mcp.targets import vscode_mcp_path

    data = json.loads(Path(vscode_mcp_path(home)).read_text(encoding="utf-8"))
    assert data["servers"]["is-muni"]["type"] == "stdio"

    # existující záznamy zůstanou
    cur = tmp_path / ".cursor" / "mcp.json"
    data = json.loads(cur.read_text(encoding="utf-8"))
    data["mcpServers"]["jiny"] = {"command": "x"}
    cur.write_text(json.dumps(data), encoding="utf-8")
    targets.write_cursor("/bin/s2", [], home)
    data = json.loads(cur.read_text(encoding="utf-8"))
    assert data["mcpServers"]["jiny"] == {"command": "x"}
    assert data["mcpServers"]["is-muni"]["command"] == "/bin/s2"


def test_write_claude_code_bez_binarky(tmp_path, monkeypatch):
    monkeypatch.setattr(targets.shutil, "which", lambda _: None)
    path = targets.write_claude_code("/bin/s", [], str(tmp_path))
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert data["mcpServers"]["is-muni"]["command"] == "/bin/s"


def test_write_target_neznamy_klient():
    with pytest.raises(ValueError, match="Neznámý klient"):
        targets.write_target("lynx", "/bin/s")


def test_preview_target():
    toml = targets.preview_target("codex", "/bin/s", ["a"])
    assert "[mcp_servers.is-muni]" in toml
    js = json.loads(targets.preview_target("vscode", "/bin/s", []))
    assert js["servers"]["is-muni"]["type"] == "stdio"
    js = json.loads(targets.preview_target("cursor", "/bin/s", []))
    assert "mcpServers" in js
    with pytest.raises(ValueError, match="Neznámý klient"):
        targets.preview_target("lynx", "/bin/s", [])


def test_detect_targets(tmp_path, monkeypatch):
    monkeypatch.setattr(targets.shutil, "which", lambda _: None)
    assert all(not t.detected for t in targets.detect_targets(str(tmp_path)))
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("", encoding="utf-8")
    found = {t.id: t.detected for t in targets.detect_targets(str(tmp_path))}
    assert found["codex"] is True
    assert found["cursor"] is False


def test_cesty_pod_tmp_home(tmp_path):
    # Díky _izolace_appdata vedou i APPDATA cesty (win) pod tmp.
    home = str(tmp_path)
    assert targets.codex_config_path(home).startswith(home)
    assert targets.cursor_mcp_path(home).startswith(home)
    assert targets.vscode_mcp_path(home).startswith(home)
    assert targets.claude_code_config_path(home).startswith(home)
    assert targets.claude_desktop_config_path(home).startswith(home)
