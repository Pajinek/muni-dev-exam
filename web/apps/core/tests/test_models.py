from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core.models import (
    ActiveEmployee,
    CatalogTraining,
    CompletedTraining,
    Department,
    Employee,
    TrainingDate,
)


class DepartmentModelTest(TestCase):
    def test_kod_from_nazev_strips_diacritics(self):
        self.assertEqual(Department.kod_from_nazev("Útvar BOZP"), "utvar_bozp")
        self.assertEqual(Department.kod_from_nazev("  IT  "), "it")

    def test_save_fills_kod_when_blank(self):
        dept = Department.objects.create(nazev="Ekonomický úsek")
        self.assertEqual(dept.kod, "ekonomicky_usek")


class EmployeeModelTest(TestCase):
    def test_normalize_name_and_email(self):
        self.assertEqual(Employee.normalize_name("LUCIE"), "Lucie")
        self.assertEqual(Employee.normalize_email("a @ b.cz"), "a@b.cz")

    def test_save_normalizes_fields(self):
        emp = Employee.objects.create(
            id_zamestnance="E0001",
            jmeno="JAN",
            prijmeni="NOVÁK",
            email="jan @firma.cz",
            pozice="analytik",
            vedouci_email="ved @firma.cz",
            datum_nastupu=date(2020, 1, 1),
            stav=Employee.Status.ACTIVE,
            rodne_cislo="900101/0001",
        )
        self.assertEqual(emp.jmeno, "Jan")
        self.assertEqual(emp.prijmeni, "Novák")
        self.assertEqual(emp.email, "jan@firma.cz")
        self.assertEqual(emp.vedouci_email, "ved@firma.cz")


class ActiveEmployeeManagerTest(TestCase):
    def setUp(self):
        Employee.objects.create(
            id_zamestnance="E-ACT",
            jmeno="Aktivni",
            prijmeni="Zam",
            email="a@ex.cz",
            pozice="x",
            datum_nastupu=date(2020, 1, 1),
            stav=Employee.Status.ACTIVE,
            rodne_cislo="1",
        )
        Employee.objects.create(
            id_zamestnance="E-END",
            jmeno="Ukonceny",
            prijmeni="Zam",
            email="u@ex.cz",
            pozice="x",
            datum_nastupu=date(2020, 1, 1),
            stav=Employee.Status.TERMINATED,
            rodne_cislo="2",
        )

    def test_only_active(self):
        pks = set(ActiveEmployee.objects.values_list("pk", flat=True))
        self.assertEqual(pks, {"E-ACT"})


class CatalogTrainingModelTest(TestCase):
    def test_parse_platnost_mesicu(self):
        self.assertEqual(CatalogTraining.parse_platnost_mesicu("24"), 24)
        self.assertEqual(CatalogTraining.parse_platnost_mesicu("2 roky"), 24)
        self.assertEqual(CatalogTraining.parse_platnost_mesicu("1 rok"), 12)
        self.assertIsNone(CatalogTraining.parse_platnost_mesicu(""))
        self.assertIsNone(CatalogTraining.parse_platnost_mesicu("neurčito"))

    def test_platnost_mesicu_int_property(self):
        cat = CatalogTraining(kod="BOZP", nazev="BOZP", platnost_mesicu="2 roky")
        self.assertEqual(cat.platnost_mesicu_int, 24)


class TrainingDateModelTest(TestCase):
    def test_volno(self):
        cat = CatalogTraining.objects.create(kod="GDPR", nazev="GDPR")
        td = TrainingDate(
            id_terminu="T1",
            kod_skoleni=cat,
            datum=date(2026, 11, 1),
            cas="9:00",
            misto="A",
            kapacita=10,
            obsazeno=3,
            stav=TrainingDate.Status.PLANNED,
        )
        self.assertEqual(td.volno, 7)
        td.obsazeno = 15
        self.assertEqual(td.volno, 0)


class CompletedTrainingModelTest(TestCase):
    def setUp(self):
        self.cat = CatalogTraining.objects.create(
            kod="BOZP-Z", nazev="BOZP", platnost_mesicu="24"
        )
        self.emp = Employee.objects.create(
            id_zamestnance="E1",
            jmeno="A",
            prijmeni="B",
            email="a@b.cz",
            pozice="x",
            datum_nastupu=date(2020, 1, 1),
            stav=Employee.Status.ACTIVE,
            rodne_cislo="1",
        )

    def test_delka_platnosti_and_match(self):
        ct = CompletedTraining(
            id_zaznamu="Z1",
            id_zamestnance=self.emp,
            kod_skoleni=self.cat,
            datum_absolvovani=date(2024, 10, 1),
            platnost_do=date(2026, 10, 1),
            cena_kc=Decimal("0"),
        )
        self.assertEqual(ct.delka_platnosti, 24)
        self.assertTrue(ct.platnost_odpovida)

    def test_delka_platnosti_none_without_dates(self):
        ct = CompletedTraining(
            id_zaznamu="Z2",
            id_zamestnance=self.emp,
            kod_skoleni=self.cat,
        )
        self.assertIsNone(ct.delka_platnosti)
        self.assertFalse(ct.platnost_odpovida)

    def test_platnost_odpovida_false_on_mismatch(self):
        ct = CompletedTraining(
            id_zaznamu="Z3",
            id_zamestnance=self.emp,
            kod_skoleni=self.cat,
            datum_absolvovani=date(2024, 10, 1),
            platnost_do=date(2025, 10, 1),
        )
        self.assertEqual(ct.delka_platnosti, 12)
        self.assertFalse(ct.platnost_odpovida)
