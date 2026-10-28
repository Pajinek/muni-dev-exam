"""Import doménových dat z JSON exportů (výstup csv_import.py)."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from django.db import transaction

from .models import CatalogTraining, CompletedTraining, Department, Employee, TrainingDate

logger = logging.getLogger(__name__)

KNOWN_JSON = (
    "katalog_skoleni.json",
    "zamestnanci.json",
    "terminy_skoleni.json",
    "absolvovana_skoleni.json",
)

# Excel serial date (Windows / Lotus 1900 epoch, včetně bugfix "day 0")
_EXCEL_EPOCH = date(1899, 12, 30)

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d. %m. %Y",
    "%d.%m.%Y",
    "%d. %m.%Y",
    "%d.%m. %Y",
)


def load_json_rows(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"Soubor {path} nemá klíč 'rows' se seznamem.")
    return rows


def parse_date(value: str | None) -> date | None:
    """ISO, české formáty (d. m. Y) nebo Excel serial (např. 43552).

    Neplatné kalendářní dny (např. 31. 9. 2026) se oříznou na poslední
    den měsíce – typická chyba v ručních exportech.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    if re.fullmatch(r"\d{5,6}", raw):
        return _EXCEL_EPOCH + timedelta(days=int(raw))

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    match = re.fullmatch(
        r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})",
        raw,
    )
    if match:
        day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if 1 <= month <= 12:
            for try_day in range(day, 0, -1):
                try:
                    return date(year, month, try_day)
                except ValueError:
                    continue

    raise ValueError(f"Neznámý formát data: {value!r}")


def parse_czech_decimal(value: str | None) -> Decimal | None:
    """'1 200,00', '0,- Kč', 'zdarma', záporné → Decimal nebo None."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    lowered = raw.casefold()
    if lowered in {"zdarma", "cena_kc"}:
        return Decimal("0") if lowered == "zdarma" else None

    cleaned = (
        raw.replace("\xa0", " ")
        .replace("Kč", "")
        .replace("kc", "")
        .replace("KC", "")
        .strip()
    )
    # „0,-“ / „0,- “
    cleaned = re.sub(r",-\s*$", ",00", cleaned)
    cleaned = cleaned.replace(" ", "").replace(",", ".")
    if not cleaned or cleaned in {".", "-", "+"}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Neplatná cena: {value!r}") from exc


def parse_optional_int(value: str | None) -> int | None:
    """'2100', '2 100 Kč', prázdné → int nebo None."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    digits = re.sub(r"[^\d-]", "", raw.replace("\xa0", " "))
    if not digits or digits in {"-", "+"}:
        return None
    return int(digits)


def _is_junk_completed_row(row: dict[str, str]) -> bool:
    record_id = (row.get("id_zaznamu") or "").strip()
    if not record_id:
        return True
    if record_id.startswith("#"):
        return True
    # duplicitní hlavička / součovací řádek z exportu
    if record_id.casefold() in {"id_zaznamu", "celkem"}:
        return True
    return False


def row_to_catalog(row: dict[str, str]) -> CatalogTraining:
    return CatalogTraining(
        kod=row["kod"].strip().upper(),
        nazev=row.get("nazev", "").strip(),
        platnost_mesicu=(row.get("platnost_mesicu") or "").strip(),
        povinne_pro=(row.get("povinne_pro") or "").strip(),
        poznamka=(row.get("poznamka") or "").strip(),
    )


def get_or_create_department(nazev: str) -> Department | None:
    """Najde nebo vytvoří útvar podle názvu z exportu; prázdný název → None."""
    nazev = nazev.strip()
    if not nazev:
        return None
    kod = Department.kod_from_nazev(nazev) or "utvar"
    dept, _ = Department.objects.get_or_create(kod=kod, defaults={"nazev": nazev})
    return dept


def row_to_employee(row: dict[str, str]) -> Employee:
    nastup = parse_date(row.get("datum_nastupu"))
    if nastup is None:
        raise ValueError(
            f"Chybí datum_nastupu u zaměstnance {row.get('id_zamestnance')!r}"
        )
    return Employee(
        id_zamestnance=row["id_zamestnance"].strip(),
        jmeno=Employee.normalize_name(row.get("jmeno", "")),
        prijmeni=Employee.normalize_name(row.get("prijmeni", "")),
        email=row.get("email", "").strip(),
        department=get_or_create_department(row.get("utvar", "")),
        pozice=row.get("pozice", "").strip(),
        vedouci_email=(row.get("vedouci_email") or "").strip(),
        datum_nastupu=nastup,
        datum_ukonceni=parse_date(row.get("datum_ukonceni") or None),
        stav=row.get("stav", "").strip(),
        rodne_cislo=(row.get("rodne_cislo") or "").strip(),
        poznamka=(row.get("poznamka") or "").strip(),
    )


# známé překlepy / varianty v exportu → kód z katalogu
_KOD_SKOLENI_TYPOS = {
    "KYB3R": "KYBER",
    "BOZP-X": "BOZP-Z",
    "GDPR-2": "GDPR",
}


def normalize_kod_skoleni(value: str | None) -> str:
    """Normalizace kódu školení z exportu (mezery/_ → -, upper, překlepy)."""
    kod = (value or "").strip().replace(" ", "-").replace("_", "-").upper()
    return _KOD_SKOLENI_TYPOS.get(kod, kod)


def resolve_catalog_training(
    kod: str | None,
    *,
    required: bool = True,
) -> CatalogTraining | None:
    """Vrátí CatalogTraining podle kódu; neznámý kód → ValueError."""
    normalized = normalize_kod_skoleni(kod)
    if not normalized:
        if required:
            raise ValueError("Chybí kod_skoleni")
        return None
    try:
        return CatalogTraining.objects.get(pk=normalized)
    except CatalogTraining.DoesNotExist as exc:
        raise ValueError(f"Neznámý kod_skoleni: {normalized!r}") from exc


def row_to_training_date(row: dict[str, str]) -> TrainingDate:
    termin = parse_date(row.get("datum"))
    if termin is None:
        raise ValueError(f"Chybí datum u termínu {row.get('id_terminu')!r}")
    return TrainingDate(
        id_terminu=row["id_terminu"].strip(),
        kod_skoleni=resolve_catalog_training(row.get("kod_skoleni")),
        datum=termin,
        cas=(row.get("cas") or "").strip(),
        misto=(row.get("misto") or "").strip(),
        kapacita=int((row.get("kapacita") or "0").strip() or 0),
        obsazeno=int((row.get("obsazeno") or "0").strip() or 0),
        cena_na_osobu=parse_optional_int(row.get("cena_na_osobu")),
        stav=(row.get("stav") or "").strip(),
    )


def row_to_completed(row: dict[str, str]) -> CompletedTraining | None:
    if _is_junk_completed_row(row):
        return None
    return CompletedTraining(
        id_zaznamu=row["id_zaznamu"].strip(),
        id_zamestnance=(row.get("id_zamestnance") or "").strip(),
        zamestnanec=(row.get("zamestnanec") or "").strip(),
        kod_skoleni=resolve_catalog_training(row.get("kod_skoleni"), required=False),
        datum_absolvovani=parse_date(row.get("datum_absolvovani") or None),
        platnost_do=parse_date(row.get("platnost_do") or None),
        poskytovatel=(row.get("poskytovatel") or "").strip(),
        cena_kc=parse_czech_decimal(row.get("cena_kc")),
        poznamka=(row.get("poznamka") or "").strip(),
    )


def _upsert(
    model,
    objects: list,
    pk_field: str,
    update_fields: list[str],
) -> tuple[int, int]:
    """Vytvoří nebo aktualizuje podle PK. Vrací (created, updated)."""
    if not objects:
        return 0, 0
    existing = set(
        model.objects.filter(
            **{f"{pk_field}__in": [getattr(o, pk_field) for o in objects]}
        ).values_list(pk_field, flat=True)
    )
    to_create = [o for o in objects if getattr(o, pk_field) not in existing]
    to_update = [o for o in objects if getattr(o, pk_field) in existing]
    if to_create:
        model.objects.bulk_create(to_create, batch_size=500)
    if to_update:
        model.objects.bulk_update(to_update, update_fields, batch_size=500)
    return len(to_create), len(to_update)


ImportStats = dict[str, Any]


@transaction.atomic
def import_all(
    data_dir: Path | str,
    *,
    clear: bool = False,
) -> ImportStats:
    data_dir = Path(data_dir)
    stats: ImportStats = {"data_dir": str(data_dir), "files": {}}

    if clear:
        CompletedTraining.objects.all().delete()
        TrainingDate.objects.all().delete()
        Employee.objects.all().delete()
        Department.objects.all().delete()
        CatalogTraining.objects.all().delete()
        stats["cleared"] = True

    loaders: list[tuple[str, Callable[[dict[str, str]], Any], type, str, list[str]]] = [
        (
            "katalog_skoleni.json",
            row_to_catalog,
            CatalogTraining,
            "kod",
            ["nazev", "platnost_mesicu", "povinne_pro", "poznamka"],
        ),
        (
            "zamestnanci.json",
            row_to_employee,
            Employee,
            "id_zamestnance",
            [
                "jmeno",
                "prijmeni",
                "email",
                "department",
                "pozice",
                "vedouci_email",
                "datum_nastupu",
                "datum_ukonceni",
                "stav",
                "rodne_cislo",
                "poznamka",
            ],
        ),
        (
            "terminy_skoleni.json",
            row_to_training_date,
            TrainingDate,
            "id_terminu",
            [
                "kod_skoleni",
                "datum",
                "cas",
                "misto",
                "kapacita",
                "obsazeno",
                "cena_na_osobu",
                "stav",
            ],
        ),
        (
            "absolvovana_skoleni.json",
            row_to_completed,
            CompletedTraining,
            "id_zaznamu",
            [
                "id_zamestnance",
                "zamestnanec",
                "kod_skoleni",
                "datum_absolvovani",
                "platnost_do",
                "poskytovatel",
                "cena_kc",
                "poznamka",
            ],
        ),
    ]

    for filename, mapper, model, pk_field, update_fields in loaders:
        path = data_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Chybí soubor: {path}")
        rows = load_json_rows(path)
        by_pk: dict[str, object] = {}
        skipped = 0
        dupes = 0
        for row in rows:
            obj = mapper(row)
            if obj is None:
                skipped += 1
                logger.warning("Skipped row: %s", row)
                continue
            pk = getattr(obj, pk_field)
            if pk in by_pk:
                dupes += 1
                logger.warning("Skipped row: %s", row)
                continue
            by_pk[pk] = obj
        created, updated = _upsert(model, list(by_pk.values()), pk_field, update_fields)
        stats["files"][filename] = {
            "rows_in_file": len(rows),
            "imported": created + updated,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "duplicates_dropped": dupes,
        }

    return stats
