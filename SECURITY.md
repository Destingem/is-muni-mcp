# Bezpečnost (Security Policy)

## Jak se zachází s vašimi údaji

- **Heslo se nikam neukládá.** Příkaz `is-muni-mcp login` ho použije jednou
  pro přihlášení k `muni.islogin.cz` a pak ho zahodí (nikdy se neloguje
  ani nevypisuje).
- **Ukládá se pouze session cookie** (`__Host-issession` + `__Host-iscreds`)
  do `~/.config/is-muni-mcp/cookie.txt` s právy **0600** (čte jen váš uživatel).
- **Server je read-only** — umí data z IS jen číst, nic v něm neměnit.
  Výjimka: samotné přihlášení (odeslání formuláře na islogin.cz), které je
  oddělené v modulu `auth.py` a spouští ho výhradně uživatel příkazem `login`.
- Veškerá komunikace jde přímo mezi vaším počítačem a `is.muni.cz` /
  `muni.islogin.cz` přes HTTPS. Žádný náš server mezi tím není.

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
