import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.core.importers import (
    import_all,
    normalize_kod_skoleni,
    parse_czech_decimal,
    parse_date,
    parse_optional_int,
    row_to_completed,
)
from apps.core.models import CatalogTraining, CompletedTraining, Employee, TrainingDate


class ParseHelpersTest(TestCase):
    def test_parse_date_formats(self):
        self.assertEqual(parse_date("2026-10-01"), date(2026, 10, 1))
        self.assertEqual(parse_date("1. 10. 2026"), date(2026, 10, 1))
        self.assertEqual(parse_date("01.10.2026"), date(2026, 10, 1))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date(None))

    def test_parse_date_excel_serial(self):
        # 43552 od Excel/Lotus epochy 1899-12-30
        self.assertEqual(parse_date("43552"), date(2019, 3, 28))

    def test_parse_date_clamps_invalid_day(self):
        self.assertEqual(parse_date("31. 9. 2026"), date(2026, 9, 30))

    def test_parse_date_unknown_raises(self):
        with self.assertRaises(ValueError):
            parse_date("not-a-date")

    def test_parse_czech_decimal(self):
        self.assertEqual(parse_czech_decimal("1 200,00"), Decimal("1200.00"))
        self.assertEqual(parse_czech_decimal("0,- Kč"), Decimal("0.00"))
        self.assertEqual(parse_czech_decimal("zdarma"), Decimal("0"))
        self.assertIsNone(parse_czech_decimal(""))
        self.assertIsNone(parse_czech_decimal("cena_kc"))

    def test_parse_optional_int(self):
        self.assertEqual(parse_optional_int("2 100 Kč"), 2100)
        self.assertIsNone(parse_optional_int(""))
        self.assertIsNone(parse_optional_int(None))

    def test_normalize_kod_skoleni_typos(self):
        self.assertEqual(normalize_kod_skoleni("kyb3r"), "KYBER")
        self.assertEqual(normalize_kod_skoleni("BOZP X"), "BOZP-Z")
        self.assertEqual(normalize_kod_skoleni("bozp_x"), "BOZP-Z")
        self.assertEqual(normalize_kod_skoleni("GDPR-2"), "GDPR")


class ImportAllTest(TestCase):
    def _write_json(self, directory: Path, name: str, rows: list[dict]) -> None:
        path = directory / name
        path.write_text(
            json.dumps({"rows": rows}, ensure_ascii=False),
            encoding="utf-8",
        )

    def _minimal_dataset(self, directory: Path) -> None:
        self._write_json(
            directory,
            "katalog_skoleni.json",
            [
                {
                    "kod": "bozp-z",
                    "nazev": "BOZP",
                    "platnost_mesicu": "24",
                    "povinne_pro": "VSICHNI",
                    "poznamka": "",
                }
            ],
        )
        self._write_json(
            directory,
            "zamestnanci.json",
            [
                {
                    "id_zamestnance": "E0100",
                    "jmeno": "JAN",
                    "prijmeni": "NOVÁK",
                    "email": "jan @ex.cz",
                    "utvar": "IT",
                    "pozice": "vývojář",
                    "vedouci_email": "",
                    "datum_nastupu": "1. 1. 2020",
                    "datum_ukonceni": "",
                    "stav": "aktivní",
                    "rodne_cislo": "900101/0001",
                    "poznamka": "",
                }
            ],
        )
        self._write_json(
            directory,
            "terminy_skoleni.json",
            [
                {
                    "id_terminu": "T100",
                    "kod_skoleni": "BOZP-Z",
                    "datum": "2026-11-15",
                    "cas": "9:00",
                    "misto": "Aula",
                    "kapacita": "20",
                    "obsazeno": "5",
                    "cena_na_osobu": "1 500 Kč",
                    "stav": "plánováno",
                }
            ],
        )
        self._write_json(
            directory,
            "absolvovana_skoleni.json",
            [
                {
                    "id_zaznamu": "Z100",
                    "id_zamestnance": "E0100",
                    "zamestnanec": "Novák Jan",
                    "kod_skoleni": "BOZP-Z",
                    "datum_absolvovani": "1. 10. 2024",
                    "platnost_do": "1. 10. 2026",
                    "poskytovatel": "ACME",
                    "cena_kc": "1 200,00",
                    "poznamka": "",
                },
                {
                    "id_zaznamu": "#comment",
                    "id_zamestnance": "E0100",
                    "kod_skoleni": "BOZP-Z",
                },
                {
                    "id_zaznamu": "Z100",
                    "id_zamestnance": "E0100",
                    "zamestnanec": "dup",
                    "kod_skoleni": "BOZP-Z",
                    "datum_absolvovani": "1. 10. 2024",
                    "platnost_do": "1. 10. 2026",
                    "poskytovatel": "",
                    "cena_kc": "0",
                    "poznamka": "",
                },
            ],
        )

    def test_import_all_creates_records(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            self._minimal_dataset(tmp)
            CatalogTraining.objects.create(kod="KYBER", nazev="Kyber")
            # KYB3R → KYBER (překlep v exportu)
            abs_path = tmp / "absolvovana_skoleni.json"
            abs_data = json.loads(abs_path.read_text(encoding="utf-8"))
            abs_data["rows"].append(
                {
                    "id_zaznamu": "Z101",
                    "id_zamestnance": "E0100",
                    "zamestnanec": "Novák Jan",
                    "kod_skoleni": "KYB3R",
                    "datum_absolvovani": "1. 10. 2025",
                    "platnost_do": "1. 10. 2026",
                    "poskytovatel": "ACME",
                    "cena_kc": "0",
                    "poznamka": "",
                }
            )
            abs_path.write_text(json.dumps(abs_data, ensure_ascii=False), encoding="utf-8")

            stats = import_all(tmp)
            self.assertEqual(CatalogTraining.objects.count(), 2)
            emp = Employee.objects.get(pk="E0100")
            self.assertEqual(emp.jmeno, "Jan")
            self.assertEqual(emp.email, "jan@ex.cz")
            self.assertIsNotNone(emp.department)
            self.assertEqual(emp.department.nazev, "IT")

            td = TrainingDate.objects.get(pk="T100")
            self.assertEqual(td.kod_skoleni_id, "BOZP-Z")
            self.assertEqual(td.cena_na_osobu, 1500)
            self.assertEqual(td.volno, 15)

            completed = CompletedTraining.objects.get(pk="Z100")
            self.assertEqual(completed.kod_skoleni_id, "BOZP-Z")
            self.assertEqual(completed.cena_kc, Decimal("1200.00"))
            self.assertEqual(CompletedTraining.objects.get(pk="Z101").kod_skoleni_id, "KYBER")

            abs_stats = stats["files"]["absolvovana_skoleni.json"]
            self.assertEqual(abs_stats["skipped"], 1)
            self.assertEqual(abs_stats["duplicates_dropped"], 1)
            self.assertEqual(abs_stats["imported"], 2)

    def test_import_all_clear(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            self._minimal_dataset(tmp)
            import_all(tmp)
            self.assertTrue(Employee.objects.filter(pk="E0100").exists())
            import_all(tmp, clear=True)
            self.assertEqual(Employee.objects.count(), 1)
            self.assertEqual(TrainingDate.objects.count(), 1)

    def test_import_json_command(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            self._minimal_dataset(tmp)
            call_command("import_json", data_dir=tmp)
            self.assertTrue(Employee.objects.filter(pk="E0100").exists())

    def test_import_json_missing_dir(self):
        with self.assertRaises(CommandError):
            call_command("import_json", data_dir=Path("/nonexistent/path/xyz"))

    def test_junk_completed_row(self):
        self.assertIsNone(row_to_completed({"id_zaznamu": ""}))
        self.assertIsNone(row_to_completed({"id_zaznamu": "#x"}))
        self.assertIsNone(row_to_completed({"id_zaznamu": "celkem"}))
