# Changelog

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/).

## [1.2.0] — 2026-09-22

### Přidáno

- **Setup aplikace bez terminálu** pro Codex, Claude Code, VS Code a Cursor:
  stažení z Releases → dvojklik → průvodce v prohlížeči (učo + heslo,
  výběr klientů, instalace serveru, zápis configů). Nový příkaz
  `is-muni-mcp wizard` (localhost, token v URL, auto-vypnutí).
- PyInstaller buildy v releasu (`IS-MUNI-Setup-macos-arm64.zip`,
  `IS-MUNI-Setup-windows-x64.exe`, `is-muni-mcp-linux-x64`) + CI smoke test.
- `setup --client codex|vscode|cursor` (nový modul `targets.py` — zápis
  Codex TOML po sekcích bez poškození komentářů).
- One-click badge VS Code / Cursor v README (deep-linky).

## [1.1.0] — 2026-09-22

### Přidáno

- Instalace bez terminálu: **`.mcpb` balíček** pro Claude Desktop (dvojklik,
  učo + heslo v instalačním dialogu, Python i závislosti zařídí Desktop).
  Sestavení: `python mcpb/build.py`; releasy ho přikládají automaticky.
- Automatické přihlášení serveru z `ISMU_UCO` + `ISMU_PASSWORD` (první běh
  i tichá obnova expirované session s jedním retry).
- CI job `mcpb` (validace manifestu + build balíčku).

## [1.0.0] — 2026-09-22

První produkční vydání.

### Přidáno

- Přihlášení učem + primárním heslem: `is-muni-mcp login` (heslo se neukládá,
  session ano — `~/.config/is-muni-mcp/cookie.txt`, práva 0600).
- `is-muni-mcp status` / `logout` — ověření a smazání session.
- `is-muni-mcp setup --client claude-desktop|claude-code|json` — napojení
  na AI klienta na jeden příkaz.
- `is-muni-mcp serve --transport streamable-http` — HTTP režim pro vzdálený
  přístup / vlastní hosting.
- Nouzové přihlášení hotovou cookie z prohlížeče (`login --cookie ...`).
- Dockerfile, CI (pytest + ruff na Python 3.10–3.13), release workflow na PyPI.
- Dokumentace: README (CZ + EN shrnutí), CONTRIBUTING, SECURITY, CHANGELOG.

### Změněno

- Vstupní bod `is-muni-mcp` je nově CLI (`cli:main`); bez argumentů se chová
  jako dřív — spustí server přes stdio.
- Chybové hlášky o expiraci session nově odkazují na `is-muni-mcp login`.
