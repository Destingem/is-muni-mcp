"""Entry-point Setup aplikace (PyInstaller, windowed).

- Dvojklik (žádný přesměrovaný stdin) → grafický průvodce v prohlížeči.
- Spuštění s piped stdin (MCP klient) → stdio server.
  (Windows: wizard nainstaluje tuto samu binárku jako server;
  windowed exe s piped stdin/stdout funguje normálně.)
"""

import os
import stat
import sys


def _stdin_is_pipe() -> bool:
    try:
        stdin = sys.stdin
        if stdin is None or stdin.closed:
            return False
        mode = os.fstat(stdin.fileno()).st_mode
        return stat.S_ISFIFO(mode) or stat.S_ISREG(mode) or stat.S_ISSOCK(mode)
    except Exception:
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        from is_muni_mcp.cli import main

        raise SystemExit(main())
    if _stdin_is_pipe():
        from is_muni_mcp.server import main as serve

        serve()
    else:
        from is_muni_mcp.wizard import run_wizard

        run_wizard()
