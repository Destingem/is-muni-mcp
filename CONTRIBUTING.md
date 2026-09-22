# Contributing (jak přispívat)

Díky, že chcete pomoct! Projekt je primárně v češtině (komentáře, hlášky,
dokumentace), protože slouží českým studentům.

## Vývojové prostředí

```bash
git clone https://github.com/Destingem/is-muni-mcp.git
cd is-muni-mcp
uv sync --group dev
uv run pytest -q
```

## Pravidla

1. **Read-only je svaté.** Klient (`src/is_muni_mcp/client.py`) nesmí umět nic
   měnit: žádné PUT/PATCH/DELETE a POST jen na `POST_READ_ALLOWLIST`.
   Hlídá to test `test_read_only_client` — když ho váš patch rozbije,
   je patch špatně.
2. **Žádná reálná data do repozitáře.** Fixture v `tests/fixtures/` musí být
   redigované (fiktivní `Jan Novák, učo 990001`, anonymizovaní odesílatelé).
   Nikdy necommitujte cookie, hesla ani výpisy ze skutečného IS.
3. **Nový parser = nový test.** Každá změna parseru potřebuje fixture
   (redigovanou!) a test v `tests/test_parsers.py`.
4. **Lint musí projít:** `uv run ruff check src tests mcpb packaging` a
   `uv run ruff format --check src tests mcpb packaging`.

## Když IS změní stránky

Nejčastější údržba: IS MUNI občas změní HTML a parser přestane fungovat.

1. Uložte si postiženou stránku (GET přes klienta, nebo z prohlížeče).
2. **Redigujte**: nahraďte jméno/učo/e-maily fiktivními (`Jan Novák`,
   `990001`, `…@mail.muni.cz`), smažte citlivé texty.
3. Přidejte jako fixture, upravte parser, přidejte/upravte test.
4. Ověřte: `uv run pytest -q`.

## Pull requesty

- Jeden PR = jedna věc. Popište, co a proč se mění.
- Uveďte, že prošly `pytest` a `ruff`.
- Změny chování pro uživatele zaznamenejte do `CHANGELOG.md`.

## Release buildy (pro maintainery)

Verze žije na třech místech (hlídají to testy): `pyproject.toml`,
`src/is_muni_mcp/__init__.py` a `mcpb/manifest.json`.

```bash
uv run python mcpb/build.py --out dist/is-muni-mcp.mcpb   # .mcpb (vyžaduje node/npx)
pip install pyinstaller pillow
pip install -e .                                          # projekt musí být importovatelný!
python packaging/build_bin.py --out dist/setup            # Setup binárky pro aktuální OS
```

Vydání: push tagu `vX.Y.Z` → workflow postaví wheel, `.mcpb` i Setup binárky
pro všechny platformy, publikuje na PyPI a přiloží vše ke GitHub Releasu.
