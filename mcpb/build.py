"""Sestavení .mcpb balíčku pro Claude Desktop (one-click instalace).

Použití:
    python mcpb/build.py [--out dist/is-muni-mcp.mcpb] [--skip-pack]

Skript zkopíruje manifest, entry-point, ikonu, pyproject (+ lock) a zdrojáky
do staging adresáře, zvaliduje manifest a zavolá `mcpb pack` (přes npx).
Vyžaduje node/npx (v CI zajišťuje setup-node).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MCPB_DIR = REPO_ROOT / "mcpb"


def assemble(staging: Path, repo: Path = REPO_ROOT) -> Path:
    """Zkopíruje soubory balíčku do staging adresáře. Vrátí jeho cestu."""
    staging.mkdir(parents=True, exist_ok=True)
    for name in ("manifest.json", "server.py", "icon.png"):
        shutil.copy2(MCPB_DIR / name, staging / name)
    # pyproject odkazuje na README (readme = "README.md") — bez něj build padne.
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(repo / name, staging / name)
    if (repo / "uv.lock").exists():
        shutil.copy2(repo / "uv.lock", staging / "uv.lock")
    shutil.copytree(
        repo / "src" / "is_muni_mcp",
        staging / "src" / "is_muni_mcp",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return staging


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, **kw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sestaví .mcpb balíček.")
    parser.add_argument("--out", default="dist/is-muni-mcp.mcpb", help="Cílový soubor.")
    parser.add_argument(
        "--skip-pack", action="store_true", help="Jen sestavit a validovat, nebalit."
    )
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="mcpb-") as tmp:
        staging = assemble(Path(tmp) / "bundle")
        manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
        print(f"Balím {manifest['name']} v{manifest['version']} …")
        run(["npx", "-y", "@anthropic-ai/mcpb@latest", "validate", str(staging / "manifest.json")])
        if args.skip_pack:
            print("Staging OK (pack přeskočen).")
            return 0
        out = Path(args.out)
        if not out.is_absolute():
            out = REPO_ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        run(["npx", "-y", "@anthropic-ai/mcpb@latest", "pack", str(staging), str(out)])
        print(f"Hotovo: {out} ({out.stat().st_size // 1024} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
