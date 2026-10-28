"""Načte JSON exporty (katalog, zaměstnanci, termíny, absolvovaná školení) do DB.

Výchozí adresář: kořen repozitáře (nad web/), kde leží výstupy csv_import.py.

Příklady:
  python manage.py import_json
  python manage.py import_json --data-dir /cesta/k/json
  python manage.py import_json --clear
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.importers import import_all


def default_data_dir() -> Path:
    # web/apps/core/management/commands/this.py → repo root
    return Path(__file__).resolve().parents[5]


class Command(BaseCommand):
    help = "Importuje JSON soubory se školeními do databáze."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--data-dir",
            type=Path,
            default=None,
            help="Adresář s *.json (výchozí: kořen repozitáře).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Před importem smaže existující záznamy všech čtyř modelů.",
        )

    def handle(self, *args, **options) -> None:
        data_dir: Path = options["data_dir"] or default_data_dir()
        if not data_dir.is_dir():
            raise CommandError(f"Adresář neexistuje: {data_dir}")

        self.stdout.write(f"Import z {data_dir} …")
        try:
            stats = import_all(data_dir, clear=options["clear"])
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise CommandError(f"Import selhal: {exc}") from exc

        if stats.get("cleared"):
            self.stdout.write(self.style.WARNING("Existující data smazána (--clear)."))

        for filename, info in stats["files"].items():
            self.stdout.write(
                f"  {filename}: "
                f"{info['imported']} importováno "
                f"(+{info['created']} / ~{info['updated']}), "
                f"přeskočeno {info['skipped']}, "
                f"duplicit {info['duplicates_dropped']} "
                f"(řádků v souboru: {info['rows_in_file']})"
            )

        inconsistencies: list[str] = stats.get("inconsistencies") or []
        if inconsistencies:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"Nekonzistence dat ({len(inconsistencies)}):"))
            for msg in inconsistencies:
                self.stdout.write(self.style.ERROR(f"  {msg}"))

        self.stdout.write(self.style.SUCCESS("Hotovo."))
