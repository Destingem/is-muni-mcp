"""Sestavení Setup binárek přes PyInstaller (volá se z CI i lokálně).

Výstupy v dist/setup/:
- macOS:   IS MUNI Setup.app (windowed) + server binárka v Resources
- Windows: IS-MUNI-Setup.exe (windowed, slouží i jako server)
- Linux:   is-muni-mcp (konzolová binárka; wizard přes `... wizard`)

Použití:  python packaging/build_bin.py [--out dist/setup]
Vyžaduje: pip install pyinstaller pillow
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGING = REPO_ROOT / "packaging"


def run(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, **kw)


def make_icons(workdir: Path) -> dict[str, str]:
    """Z mcpb/icon.png vyrobí icon.ico (+ icon.icns, když to jde)."""
    try:
        from PIL import Image
    except ImportError:
        print("Pillow chybí — build bez ikon.")
        return {}
    src = Image.open(REPO_ROOT / "mcpb" / "icon.png").convert("RGBA")
    out: dict[str, str] = {}
    ico = workdir / "icon.ico"
    src.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    out["ico"] = str(ico)
    try:
        icns = workdir / "icon.icns"
        src.save(icns)
        out["icns"] = str(icns)
    except Exception as e:  # noqa: BLE001
        print(f".icns ikonu se nepodařilo vyrobit ({e}) — macOS build bez ikony.")
    return out


def build(out_dir: Path) -> None:
    workdir = REPO_ROOT / "build" / "setup-pkg"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    icons = make_icons(workdir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pyi = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm"]
    common = [
        "--distpath",
        str(workdir / "dist"),
        "--workpath",
        str(workdir / "work"),
        "--specpath",
        str(workdir),
    ]

    if sys.platform == "darwin":
        # 1) konzolový server (půjde do Resources .app)
        run(
            pyi
            + common
            + [
                "--onefile",
                "--name",
                "is-muni-mcp",
                str(PACKAGING / "entry_server.py"),
            ]
        )
        server_bin = workdir / "dist" / "is-muni-mcp"
        # 2) windowed .app s wizardem
        app_cmd = (
            pyi
            + common
            + [
                "--windowed",
                "--onedir",
                "--name",
                "IS MUNI Setup",
                "--add-data",
                f"{server_bin}:.",
                "--osx-bundle-identifier",
                "cz.muni.is-mcp.setup",
            ]
        )
        if "icns" in icons:
            app_cmd += ["--icon", icons["icns"]]
        app_cmd.append(str(PACKAGING / "entry_setup.py"))
        run(app_cmd)
        app = workdir / "dist" / "IS MUNI Setup.app"
        # server v Resources musí být spustitelný
        res_bin = app / "Contents" / "Resources" / "is-muni-mcp"
        if res_bin.exists():
            os.chmod(res_bin, 0o755)
        dest = out_dir / "IS MUNI Setup.app"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(app), dest)
        print(f"Hotovo: {dest}")
    elif os.name == "nt":
        # Jedna windowed binárka: dvojklik → wizard, piped → server.
        cmd = pyi + common + ["--onefile", "--windowed", "--name", "IS-MUNI-Setup"]
        if "ico" in icons:
            cmd += ["--icon", icons["ico"]]
        cmd.append(str(PACKAGING / "entry_setup.py"))
        run(cmd)
        dest = out_dir / "IS-MUNI-Setup.exe"
        shutil.move(str(workdir / "dist" / "IS-MUNI-Setup.exe"), dest)
        print(f"Hotovo: {dest}")
    else:
        # Linux: konzolová binárka (wizard přes `./is-muni-mcp wizard`).
        run(
            pyi
            + common
            + ["--onefile", "--name", "is-muni-mcp", str(PACKAGING / "entry_server.py")]
        )
        dest = out_dir / "is-muni-mcp"
        shutil.move(str(workdir / "dist" / "is-muni-mcp"), dest)
        os.chmod(dest, 0o755)
        print(f"Hotovo: {dest}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sestaví Setup binárky.")
    parser.add_argument("--out", default="dist/setup")
    args = parser.parse_args(argv)
    out = Path(args.out)
    build(REPO_ROOT / out if not out.is_absolute() else out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
