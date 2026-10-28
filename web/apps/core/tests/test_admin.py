from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.core.admin import (
    _is_completed_valid,
    _is_training_eligible,
    _is_training_required,
    _missing_required_catalogs,
    _open_training_dates_for,
    _required_training_codes,
    _valid_training_codes,
)
from apps.core.models import (
    CatalogTraining,
    CompletedTraining,
    Department,
    Employee,
    TrainingDate,
)


class TrainingRulesTest(TestCase):
    def setUp(self):
        self.dept_it = Department.objects.create(kod="it", nazev="IT")
        self.dept_hr = Department.objects.create(kod="hr", nazev="HR")
        self.emp = Employee.objects.create(
            id_zamestnance="E0104",
            jmeno="Eva",
            prijmeni="Test",
            email="eva@ex.cz",
            department=self.dept_it,
            pozice="vývojář",
            datum_nastupu=date(2020, 1, 1),
            stav=Employee.Status.ACTIVE,
            rodne_cislo="1",
        )
        self.cat_all = CatalogTraining.objects.create(
            kod="BOZP-Z", nazev="BOZP", platnost_mesicu="24", povinne_pro="VSICHNI"
        )
        self.cat_utvar = CatalogTraining.objects.create(
            kod="KYBER",
            nazev="Kyber",
            platnost_mesicu="12",
            povinne_pro="UTVAR:IT;Finance",
        )
        self.cat_pozice = CatalogTraining.objects.create(
            kod="POZ-OCH",
            nazev="Ochranka",
            platnost_mesicu="12",
            povinne_pro="POZICE:strážný",
        )
        self.cat_optional = CatalogTraining.objects.create(
            kod="SOFT", nazev="Soft skills", platnost_mesicu="0", povinne_pro="nepovinne"
        )

    def test_is_training_required(self):
        self.assertTrue(_is_training_required(self.cat_all, self.emp))
        self.assertTrue(_is_training_required(self.cat_utvar, self.emp))
        self.assertFalse(_is_training_required(self.cat_pozice, self.emp))
        self.assertFalse(_is_training_required(self.cat_optional, self.emp))

        self.emp.department = self.dept_hr
        self.assertFalse(_is_training_required(self.cat_utvar, self.emp))

    def test_is_training_eligible(self):
        self.assertTrue(_is_training_eligible(self.cat_all, self.emp))
        self.assertTrue(_is_training_eligible(self.cat_optional, self.emp))
        self.assertTrue(_is_training_eligible(self.cat_utvar, self.emp))
        self.assertFalse(_is_training_eligible(self.cat_pozice, self.emp))

    def test_completed_valid_and_missing(self):
        today = timezone.localdate()
        CompletedTraining.objects.create(
            id_zaznamu="Z1",
            id_zamestnance=self.emp,
            kod_skoleni=self.cat_all,
            datum_absolvovani=today - timedelta(days=30),
            platnost_do=today + timedelta(days=30),
        )
        emp = Employee.objects.prefetch_related("completed_trainings__kod_skoleni").get(pk=self.emp.pk)
        valid = _valid_training_codes(emp, today)
        self.assertEqual(valid, {"BOZP-Z"})

        catalogs = list(CatalogTraining.objects.all())
        required = _required_training_codes(emp, catalogs)
        self.assertEqual(required, {"BOZP-Z", "KYBER"})

        missing = _missing_required_catalogs(emp, catalogs, today)
        self.assertEqual({c.kod for c in missing}, {"KYBER"})

    def test_is_completed_valid_zero_months(self):
        ct = CompletedTraining(
            id_zaznamu="Z2",
            id_zamestnance=self.emp,
            kod_skoleni=self.cat_optional,
            platnost_do=None,
        )
        self.assertTrue(_is_completed_valid(ct, self.cat_optional, timezone.localdate()))

    def test_open_training_dates_for(self):
        today = timezone.localdate()
        open_td = TrainingDate.objects.create(
            id_terminu="T-OPEN",
            kod_skoleni=self.cat_all,
            datum=today + timedelta(days=7),
            cas="9:00",
            misto="A",
            kapacita=10,
            obsazeno=2,
            stav=TrainingDate.Status.PLANNED,
        )
        TrainingDate.objects.create(
            id_terminu="T-FULL",
            kod_skoleni=self.cat_all,
            datum=today + timedelta(days=8),
            cas="10:00",
            misto="A",
            kapacita=5,
            obsazeno=5,
            stav=TrainingDate.Status.PLANNED,
        )
        TrainingDate.objects.create(
            id_terminu="T-OTHER",
            kod_skoleni=self.cat_pozice,
            datum=today + timedelta(days=9),
            cas="11:00",
            misto="B",
            kapacita=10,
            obsazeno=0,
            stav=TrainingDate.Status.PLANNED,
        )
        TrainingDate.objects.create(
            id_terminu="T-PAST",
            kod_skoleni=self.cat_all,
            datum=today - timedelta(days=1),
            cas="9:00",
            misto="A",
            kapacita=10,
            obsazeno=0,
            stav=TrainingDate.Status.PLANNED,
        )

        open_dates = _open_training_dates_for(self.emp, today)
        self.assertEqual([td.pk for td in open_dates], [open_td.pk])
