"""Test MCP protokolu: server musí odpovídat přes stdio (initialize, tools/list)."""

import json
import os
import subprocess
import sys

import pytest

SERVER_CMD = [sys.executable, "-m", "is_muni_mcp.server"]


def send_recv(proc: subprocess.Popen, payload: dict) -> dict:
    assert proc.stdin and proc.stdout
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line, "server neodpověděl"
    return json.loads(line)


def test_stdio_initialize_and_list_tools():
    # PYTHONUTF8: server v subprocessu musí psát UTF-8 i na Windows (jinak cp1252).
    env = {**os.environ, "ISMU_COOKIE": "dummy; dummy2", "PYTHONUTF8": "1"}
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**env, "PYTHONPATH": "src"},
    )
    try:
        init = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "t", "version": "0"},
                },
            },
        )
        assert "result" in init, init
        tools = send_recv(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = [t["name"] for t in tools["result"]["tools"]]
        for expected in (
            "status",
            "moje_predmety",
            "predmet_info",
            "moje_znamky",
            "poznamkove_bloky",
            "kalendar",
            "deadlines",
            "rozvrh",
            "zkouskove_terminy",
            "posta_slozky",
            "posta_seznam",
            "posta_cti",
            "udalosti",
            "pripomenuti",
            "dashboard",
            "soubory_vypis",
            "soubor_cti",
            "diskuse_prehled",
            "diskuse_vlakno",
            "vyveska",
            "harmonogram",
            "profil",
            "osoba",
            "hledat_predmet",
            "moje_seminarni_skupiny",
        ):
            assert expected in names, f"chybí nástroj {expected}"
        assert len(names) == 25, names
    finally:
        proc.kill()


@pytest.mark.skipif(not os.environ.get("ISMU_LIVE_MCP"), reason="živý test jen s ISMU_LIVE_MCP=1")
def test_stdio_live_status_call():
    """Živé volání nástroje status přes protokol (potřebuje platnou ISMU_COOKIE)."""
    proc = subprocess.Popen(
        SERVER_CMD,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env={**os.environ, "PYTHONPATH": "src", "PYTHONUTF8": "1"},
    )
    try:
        send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "t", "version": "0"},
                },
            },
        )
        resp = send_recv(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "status", "arguments": {}},
            },
        )
        assert "result" in resp, resp
        text = json.dumps(resp["result"])
        assert "prihlasen" in text
    finally:
        proc.kill()
