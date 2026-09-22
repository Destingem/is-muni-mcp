# Changelog

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/).

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
