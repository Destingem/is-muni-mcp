# IS MUNI MCP

[![CI](https://github.com/Destingem/is-muni-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Destingem/is-muni-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/is-muni-mcp.svg)](https://pypi.org/project/is-muni-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

MCP server pro studenty Masarykovy univerzity — propojí AI agenty
(Claude Desktop, Claude Code, …) s Informačním systémem MU, aby pomohli
s plánováním studia: rozvrh, deadliny, e-maily, známky, body z bloků,
studijní materiály a další.

> **Nikdy nic nemění.** Server pouze čte data (GET + POST jen na povolené
> čtecí endpointy, typicky AJAX vyhledávání) — neumí odesílat poštu,
> registrovat předměty, přihlašovat na zkoušky ani jinak cokoliv v IS měnit.
> Garance je přímo v kódu: klient
> [`client.py`](src/is_muni_mcp/client.py) nemá metody pro PUT/PATCH/DELETE
> a POST mimo allowlist odmítne (hlídá to i test `test_read_only_client`).

*English summary: read-only MCP server for Masaryk University students —
connects AI agents to IS MUNI (timetable, deadlines, mail, grades, course
materials). Quickstart below is in Czech; commands are the same in any
language. See [CONTRIBUTING](CONTRIBUTING.md) and [SECURITY](SECURITY.md).*

## Instalace bez terminálu (doporučeno pro studenty) 🖱️

Terminál vůbec nepotřebujete — stačí Claude Desktop a 3 kliknutí:

1. Stáhněte si soubor **`is-muni-mcp.mcpb`** ze stránky
   [Releases](https://github.com/Destingem/is-muni-mcp/releases) (nejnovější verze).
2. **Dvojklikem** ho otevřete (nebo přetáhněte do okna Claude Desktop) —
   objeví se instalační dialog.
3. Vyplňte své **učo a primární heslo** do IS MUNI a potvrďte.

Hotovo. Claude Desktop si sám zařídí zbytek (Python, závislosti) a server se
pak přihlašuje sám — i když session vyprší, obnoví si ji bez ptaní.
V chatu se pak ptejte třeba: *„Co mám příští týden v rozvrhu?“*,
*„Jaké se blíží deadliny?“*, *„Mám nějaké nepřečtené e-maily?“*

> Heslo slouží jen k přihlášení (spravuje ho zabezpečené úložiště Claude
> Desktopu); server si ukládá pouze session. Detaily viz [SECURITY](SECURITY.md).

## Rychlý start s terminálem (3 kroky)

Pro Claude Code, VS Code, Zed a další klienty. Potřebujete Python 3.10+
a své učo + primární heslo do IS MUNI.

**1. Instalace** (jednou z možností):

```bash
pipx install is-muni-mcp        # doporučeno pro běžné uživatele
# nebo: uv tool install is-muni-mcp
# nebo: pip install --user is-muni-mcp
```

**2. Přihlášení** — zeptá se na učo a heslo, heslo se nikam neukládá:

```bash
is-muni-mcp login
is-muni-mcp status   # ověření, že přihlášení funguje
```

Session se uloží do `~/.config/is-muni-mcp/cookie.txt` (práva 0600, jen pro vás).
Když časem vyprší (typicky dny až týdny), stačí `login` zopakovat.

**3. Napojení na AI klienta** — jedna z možností:

```bash
is-muni-mcp setup --client claude-desktop   # zapíše konfiguraci za vás
is-muni-mcp setup --client claude-code      # přes `claude mcp add`
```

Pak restartujte klienta a ptejte se třeba: *„Co mám příští týden v rozvrhu?“*,
*„Jaké se blíží deadliny?“*, *„Mám nějaké nepřečtené e-maily?“*,
*„Kolik mám bodů v poznámkových blocích?“*

## Nástroje (25)

| Oblast | Nástroje |
|---|---|
| Student | `status`, `profil`, `osoba`, `moje_predmety`, `predmet_info`, `moje_znamky`, `moje_seminarni_skupiny`, `hledat_predmet`, `harmonogram` |
| Kalendář a výuka | `kalendar`, `deadlines`, `rozvrh`, `zkouskove_terminy` (pouze přehled) |
| Pošta | `posta_slozky`, `posta_seznam`, `posta_cti` |
| Notifikace | `udalosti`, `pripomenuti` (IS připomíná), `dashboard` (Co se děje / Co vás čeká) |
| Bloky | `poznamkove_bloky` (body a hodnocení z průběžných aktivit) |
| Soubory | `soubory_vypis` (i rekurzivně), `soubor_cti` (text rovnou; u prezentací/dokumentů zkusí i automatickou .txt verzi) |
| Diskuse a vývěska | `diskuse_prehled`, `diskuse_vlakno`, `vyveska` |

## Ruční konfigurace klientů

Když nechcete použít `setup`, přidejte server ručně. Příkaz je vždy `is-muni-mcp`
(bez argumentů spustí server přes stdio; přihlášení si najde samo v
`~/.config/is-muni-mcp/cookie.txt`).

**Claude Desktop** — do `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "is-muni": {
      "command": "is-muni-mcp"
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add is-muni -- is-muni-mcp
```

**Obecné `mcp.json`** (VS Code, Zed, …) — totéž co výše; konfiguraci pro svůj
stroj vytisknete příkazem `is-muni-mcp setup --client json`.

**ChatGPT a další klienti bez lokálního stdio** — ChatGPT umí jen vzdálené
MCP servery (URL), neumí spouštět lokální příkazy. Pro tento případ server umí
i HTTP transport — musíte ho ale provozovat sami (např. na vlastním VPS)
a ChatGPT pak napojit na jeho URL:

```bash
is-muni-mcp serve --transport streamable-http --host 127.0.0.1 --port 8000
# URL pro klienta: http://VAS-SERVER:8000/mcp
```

> ⚠️ HTTP režim vystavuje vaše data z IS komukoliv s přístupem k URL —
> provozujte ho jen za autentizací / na privátní síti (Tailscale, VPN)
> a nikdy ne bez zabezpečení na veřejném internetu.

**Docker:**

```bash
docker build -t is-muni-mcp .
docker run -i --rm -v is-muni-config:/config is-muni-mcp login   # přihlášení (session zůstane ve volume)
docker run -i --rm -v is-muni-config:/config is-muni-mcp         # server přes stdio
```

## Přihlášení — detaily a alternativy

- `is-muni-mcp login` — interaktivní přihlášení učem + heslem (doporučeno).
- `is-muni-mcp login --uco 990001` — učo předvyplněné, zeptá se jen na heslo.
- `is-muni-mcp login --cookie "__Host-issession=...; __Host-iscreds=..."` —
  nouzová varianta: vložení hotové session z prohlížeče
  (Vývojářské nástroje → Application → Cookies → `https://is.muni.cz`).
- `is-muni-mcp logout` — smaže uloženou session.
- Proměnné prostředí (přednost před uloženou session, vhodné pro servery
  a CI): `ISMU_COOKIE` (celý řetězec), `ISMU_SESSION` + `ISMU_CREDS`,
  nebo `ISMU_COOKIE_FILE`. Vzor viz [`.env.example`](.env.example).
- Stažené binární soubory: `ISMU_DOWNLOAD_DIR` (výchozí `~/.cache/is-muni-mcp`).

## Vývoj a testy

```bash
git clone https://github.com/Destingem/is-muni-mcp.git
cd is-muni-mcp
uv sync --group dev
uv run pytest            # fixture testy parserů + test MCP protokolu (offline)
uv run ruff check src tests mcpb && uv run ruff format --check src tests mcpb
ISMU_LIVE_MCP=1 uv run pytest tests/test_mcp.py -q   # + živé volání přes protokol (potřebuje přihlášení)
```

Testy běží nad redigovanými vzorky stránek IS
([`tests/fixtures/`](tests/fixtures/)) — žádný network, žádná reálná data.
Detaily viz [CONTRIBUTING](CONTRIBUTING.md).

## Jak to funguje a limity

- Data se čtou přímo ze stránek IS (HTML + vložený JSON kalendáře + oficiální
  iCal export rozvrhu `format=ical`). Žádné neoficiální API není potřeba.
- Struktura stránek IS se může změnit — když některý nástroj přestane fungovat,
  většinou stačí upravit příslušný parser v [`src/is_muni_mcp/parsers/`](src/is_muni_mcp/parsers/).
- Některé agendy IS (např. přepínače období) se doplňují JavaScriptem — server
  pracuje s aktuálně vybraným obdobím a studiem.
- Odpovědníky se čtou jen z kalendáře a výpisu souborů — nástroj záměrně neotvírá
  testovací rozhraní, aby omylem nezahájil pokus.
- Neoficiální projekt — není dílem ani pod záštitou Masarykovy univerzity.

## Licence

MIT — viz [LICENSE](LICENSE).
