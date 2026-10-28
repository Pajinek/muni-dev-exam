# Evidence školení

Webová aplikace nad exporty školení zaměstnanců (praktický úkol výběrového řízení).

## Přílohy (CSV)

| Soubor | Obsah | Kódování | Oddělovač |
|--------|--------|----------|-----------|
| `zamestnanci.csv` | seznam zaměstnanců | UTF-8 s BOM | `,` |
| `absolvovana_skoleni.csv` | záznamy o absolvovaných školeních | Windows-1250 (cp1250) | `;` |
| `katalog_skoleni.csv` | druhy školení, platnost, povinnost | UTF-8 | `,` |
| `terminy_skoleni.csv` | vypsané termíny s kapacitou | UTF-8 s BOM | `;` |

Export dat: **1. 10. 2026**. Data jsou fiktivní.

## Skript `csv_import.py`

Načte všechny čtyři CSV z kořene projektu, detekuje kódování (`utf-8-sig`, jinak `cp1250`) a oddělovač (`,` / `;`) a uloží stejnojmenné JSON soubory v UTF-8 (`ensure_ascii=False`, formátované s odsazením).

| Vstup | Výstup |
|-------|--------|
| `zamestnanci.csv` | `zamestnanci.json` |
| `absolvovana_skoleni.csv` | `absolvovana_skoleni.json` |
| `katalog_skoleni.csv` | `katalog_skoleni.json` |
| `terminy_skoleni.csv` | `terminy_skoleni.json` |

Každý JSON obsahuje: `source`, `encoding`, `delimiter`, `row_count`, `rows`.

Závislosti: pouze standardní knihovna Pythonu 3.

```bash
python3 csv_import.py
```

Načtení JSON do Django DB (z adresáře `web/`):

```bash
python manage.py import_json --data-dir imports/
python manage.py import_json --data-dir imports/ --clear
```

JSON soubory leží ve `web/imports/` (kopie výstupů `csv_import.py`). Bez `--data-dir` se bere kořen repozitáře.

### Duplicitní a přeskočené záznamy

Import je idempotentní podle primárního klíče. Při opakovaném výskytu stejného ID se do DB uloží jen první výskyt (`duplicit`); neplatné / šumové řádky (prázdné ID, komentáře `#…`, součovací řádky) se počítají jako `přeskočeno`.

Typický výstup z `import_json` nad přiloženými exporty:

```
katalog_skoleni.json: 10 importováno (+10 / ~0), přeskočeno 0, duplicit 0 (řádků v souboru: 10)
zamestnanci.json: 174 importováno (+174 / ~0), přeskočeno 0, duplicit 0 (řádků v souboru: 174)
terminy_skoleni.json: 34 importováno (+34 / ~0), přeskočeno 0, duplicit 0 (řádků v souboru: 34)
absolvovana_skoleni.json: 2850 importováno (+2850 / ~0), přeskočeno 3, duplicit 15 (řádků v souboru: 2868)

Nekonzistence dat (9):
  Neznámý id_zamestnance: 'E9006'
  Neznámý id_zamestnance: 'E9001'
  …
  Neznámý id_zamestnance: 'E9005'
```

U `absolvovana_skoleni` tedy z 2868 řádků zbývá **2850** platných unikátních záznamů (3 přeskočené + 15 duplicit podle `id_zaznamu`).

### Problémy v datech při importu

Některé řádky v `absolvovana_skoleni` odkazují na `id_zamestnance` mimo `zamestnanci` (`E9001`–`E9009`, 9 záznamů). Import je vypíše jako **Nekonzistence dat**, záznam uloží s prázdnou FK a pokračuje dál. Stejně by se ohlásil i neznámý `kod_skoleni`.