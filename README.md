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
