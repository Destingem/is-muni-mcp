# Bezpečnost (Security Policy)

## Jak se zachází s vašimi údaji

- **Heslo serverem jen proteče.** Použije se jednou pro přihlášení
  k `muni.islogin.cz` a pak se zahodí (nikdy se neloguje ani nevypisuje).
  Samotný server si ho nikam neukládá.
- **Ukládá se pouze session cookie** (`__Host-issession` + `__Host-iscreds`)
  do `~/.config/is-muni-mcp/cookie.txt` s právy **0600** (čte jen váš uživatel).
- **.mcpb instalace:** učo a heslo vyplněné v instalačním dialogu spravuje
  zabezpečené úložiště Claude Desktopu a serveru je předává jen jako
  proměnné prostředí (`ISMU_UCO` / `ISMU_PASSWORD`) pro automatické
  (znovu)přihlašování. Kdo nechce heslo svěřit ani Desktopu, může místo
  .mcpb použít terminálovou instalaci s `is-muni-mcp login`.
- **Server je read-only** — umí data z IS jen číst, nic v něm neměnit.
  Výjimka: samotné přihlášení (odeslání formuláře na islogin.cz), které je
  oddělené v modulu `auth.py` a spouští ho uživatel (příkazem `login`,
  automaticky jen při nakonfigurovaných `ISMU_UCO` + `ISMU_PASSWORD`).
- Veškerá komunikace jde přímo mezi vaším počítačem a `is.muni.cz` /
  `muni.islogin.cz` přes HTTPS. Žádný náš server mezi tím není.
- **Setup aplikace / wizard:** průvodce běží jen na `127.0.0.1` s náhodným
  tokenem v URL a po dokončení (nebo 15 minutách) se sám vypne. Binárky
  v Releasu se staví veřejně v GitHub Actions z tohoto repozitáře
  ([workflow](.github/workflows/release.yml)) — nejsou placeně podepsané,
  proto OS při prvním spuštění varuje (viz README).

## Na co si dát pozor

- Session cookie je ekvivalent přihlášení — **nikomu ji neposílejte**,
  nevkládejte do issue ani do chatu s AI mimo svůj počítač.
- HTTP transport (`serve --transport streamable-http`) vystavuje data z IS
  komukoliv s přístupem k URL — provozujte ho jen za autentizací
  a na privátní síti, nikdy otevřeně na internetu.
- Při podezření na únik session se v IS odhlaste ze všech zařízení
  (tím session zneplatníte) a přihlaste se znovu.

## Hlášení zranitelností

Našli jste bezpečnostní problém? **Nezakládejte veřejné issue.**
Napište prosím přes GitHub Security Advisories (záložka Security
v repozitáři) nebo e-mail na adresu uvedenou v profilu maintainera.
Odpovíme co nejdřív a domluvíme koordinované zveřejnění opravy.

## Podporované verze

Opravy dostává pouze aktuální řada 1.x. Aktualizujte přes:

```bash
pipx upgrade is-muni-mcp   # nebo: uv tool upgrade is-muni-mcp
```
