"""Načítání CSV exportů se správným kódováním a oddělovačem.

Soubory z různých systémů:
- UTF-8 (často s BOM): katalog_skoleni, terminy_skoleni, zamestnanci
- Windows-1250 (cp1250): absolvovana_skoleni
- oddělovač čárka nebo středník

Výstup: stejnojmenné *.json v UTF-8 (ensure_ascii=False).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable

# Pořadí pokusů: nejdřív UTF-8 (s BOM), pak české Windows kódování.
_ENCODINGS = ("utf-8-sig", "cp1250")

KNOWN_FILES = (
    "zamestnanci.csv",
    "absolvovana_skoleni.csv",
    "katalog_skoleni.csv",
    "terminy_skoleni.csv",
)

ORIGINAL_FILE_CREATION_DATE = "2026-10-01"


@dataclass(frozen=True)
class CsvLoadResult:
    path: Path
    encoding: str
    delimiter: str
    rows: list[dict[str, str]]

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_json_dict(self) -> dict:
        return {
            "source": self.path.name,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "original_file_creation_date": ORIGINAL_FILE_CREATION_DATE,
            "row_count": self.row_count,
            "rows": self.rows,
        }


def detect_encoding(raw: bytes) -> str:
    """Vrátí kódování, ve kterém jde soubor dekódovat bez chyby.

    Preferuje UTF-8 (včetně BOM). Pokud UTF-8 selže, zkusí Windows-1250.
    """
    last_error: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(
        f"Nepodařilo se detekovat kódování (zkoušeno: {', '.join(_ENCODINGS)})"
    ) from last_error


def detect_delimiter(header_line: str) -> str:
    """Odhadne oddělovač podle hlavičky (; vs ,)."""
    semi = header_line.count(";")
    comma = header_line.count(",")
    if semi == 0 and comma == 0:
        raise ValueError(f"V hlavičce není oddělovač: {header_line!r}")
    return ";" if semi >= comma else ","


def read_csv_file(path: Path | str) -> CsvLoadResult:
    """Načte jeden CSV soubor jako seznam řádků (dict podle hlavičky)."""
    path = Path(path)
    raw = path.read_bytes()
    encoding = detect_encoding(raw)
    text = raw.decode(encoding)

    # Normalizace konců řádků (CRLF z Windows exportů)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ValueError(f"Prázdný soubor: {path}")

    header_line = text.split("\n", 1)[0]
    delimiter = detect_delimiter(header_line)

    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {
            (key or "").strip(): (value if value is not None else "").strip()
            for key, value in row.items()
            if key is not None
        }
        # Přeskočit pouze řádky bez hodnoty v prvním sloupci
        first_value = next(iter(cleaned.values()), "")
        if not first_value:
            continue
        rows.append(cleaned)

    return CsvLoadResult(
        path=path,
        encoding=encoding,
        delimiter=delimiter,
        rows=rows,
    )


def load_all_csv(
    data_dir: Path | str,
    filenames: Iterable[str] = KNOWN_FILES,
) -> dict[str, CsvLoadResult]:
    """Načte všechny známé CSV z adresáře. Klíč = název souboru."""
    data_dir = Path(data_dir)
    results: dict[str, CsvLoadResult] = {}
    for name in filenames:
        path = data_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"Chybí datový soubor: {path}")
        results[name] = read_csv_file(path)
    return results


def write_json(result: CsvLoadResult, output_path: Path | str | None = None) -> Path:
    """Uloží výsledek jako UTF-8 JSON (diakritika bez escape \\uXXXX)."""
    path = Path(output_path) if output_path else result.path.with_suffix(".json")
    path.write_text(
        json.dumps(result.to_json_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def export_all_to_json(
    data_dir: Path | str,
    filenames: Iterable[str] = KNOWN_FILES,
) -> dict[str, Path]:
    """Načte CSV a uloží ke každému stejnojmenný *.json."""
    data_dir = Path(data_dir)
    written: dict[str, Path] = {}
    for name, result in load_all_csv(data_dir, filenames).items():
        out = write_json(result, data_dir / Path(name).with_suffix(".json").name)
        written[name] = out
    return written


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    for csv_name, json_path in export_all_to_json(root).items():
        result = read_csv_file(root / csv_name)
        print(
            f"{csv_name} → {json_path.name}: "
            f"{result.row_count} řádků, encoding={result.encoding}, "
            f"delimiter={result.delimiter!r}"
        )
