"""Testy .mcpb balíčku (struktura manifestu, sestavení — bez npx)."""

import json
import sys
from pathlib import Path

from is_muni_mcp import __version__

ROOT = Path(__file__).parent.parent
MCPB_DIR = ROOT / "mcpb"

sys.path.insert(0, str(MCPB_DIR))
import build as mcpb_build  # noqa: E402


def load_manifest() -> dict:
    return json.loads((MCPB_DIR / "manifest.json").read_text(encoding="utf-8"))


def test_manifest_povinna_pole():
    m = load_manifest()
    assert m["manifest_version"] == "0.4"
    assert m["name"] == "is-muni"
    assert m["server"]["type"] == "uv"
    assert m["server"]["entry_point"] == "server.py"
    cfg = m["server"]["mcp_config"]
    assert cfg["command"] == "uv"
    assert "${__dirname}" in " ".join(cfg["args"])
    # přihlašovací údaje z instalačního dialogu tečou do prostředí serveru
    assert cfg["env"]["ISMU_UCO"] == "${user_config.uco}"
    assert cfg["env"]["ISMU_PASSWORD"] == "${user_config.password}"


def test_manifest_user_config():
    m = load_manifest()
    uc = m["user_config"]
    assert uc["uco"]["required"] is True
    assert uc["password"]["required"] is True
    assert uc["password"]["sensitive"] is True


def test_manifest_verze_v_souladu():
    assert load_manifest()["version"] == __version__


def test_manifest_vstupni_soubory_existuji():
    m = load_manifest()
    assert (MCPB_DIR / m["server"]["entry_point"]).exists()
    assert (MCPB_DIR / m["icon"]).exists()
    # shim musí odkazovat na skutečný server
    shim = (MCPB_DIR / "server.py").read_text(encoding="utf-8")
    assert "is_muni_mcp.server" in shim


def test_assemble_posklada_balitek(tmp_path):
    staging = mcpb_build.assemble(tmp_path / "bundle")
    for name in (
        "manifest.json",
        "server.py",
        "icon.png",
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "src/is_muni_mcp/server.py",
        "src/is_muni_mcp/auth.py",
        "src/is_muni_mcp/client.py",
    ):
        assert (staging / name).exists(), name
    # žádné cache soubory
    assert not list(staging.rglob("__pycache__"))
    assert not list(staging.rglob("*.pyc"))
