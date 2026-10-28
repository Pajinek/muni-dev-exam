from datetime import date

from django.contrib import admin
from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from .models import (
    ActiveEmployee,
    CatalogTraining,
    CompletedTraining,
    Department,
    Employee,
    TrainingDate,
)


def _is_training_required(catalog: CatalogTraining, employee: Employee) -> bool:
    """Povinnost podle katalogového povinne_pro (VSICHNI / UTVAR / POZICE)."""
    raw = (catalog.povinne_pro or "").strip()
    if not raw:
        return False
    upper = raw.casefold()
    if upper == "nepovinne":
        return False
    if upper == "vsichni":
        return True
    if raw.startswith("UTVAR:"):
        names = {n.strip() for n in raw[6:].split(";") if n.strip()}
        dept = employee.department
        return bool(dept and dept.nazev in names)
    if raw.startswith("POZICE:"):
        names = {n.strip() for n in raw[7:].split(";") if n.strip()}
        return employee.pozice in names
    return False


def _is_completed_valid(
    completed: CompletedTraining, catalog: CatalogTraining, today: date
) -> bool:
    months = catalog.platnost_mesicu_int
    if months is None or months == 0:
        return True
    return completed.platnost_do is not None and completed.platnost_do >= today


def _valid_training_codes(employee: Employee, today: date) -> set[str]:
    kody: set[str] = set()
    for ct in employee.completed_trainings.all():
        if not ct.kod_skoleni_id or ct.kod_skoleni is None:
            continue
        if _is_completed_valid(ct, ct.kod_skoleni, today):
            kody.add(ct.kod_skoleni_id)
    return kody


def _required_training_codes(
    employee: Employee, catalogs: list[CatalogTraining]
) -> set[str]:
    return {c.kod for c in catalogs if _is_training_required(c, employee)}


def _missing_required_pks(
    queryset: QuerySet, catalogs: list[CatalogTraining], today: date
) -> set[str]:
    missing: set[str] = set()
    for emp in queryset:
        required = _required_training_codes(emp, catalogs)
        if not required:
            continue
        if required - _valid_training_codes(emp, today):
            missing.add(emp.pk)
    return missing


class PlatneSkoleniFilter(admin.SimpleListFilter):
    """Filtr zaměstnanců podle katalogu – jen ti s dosud platným školením."""

    title = "platné školení"
    parameter_name = "platne_skoleni"

    def lookups(self, request, model_admin):
        return [(c.kod, str(c)) for c in CatalogTraining.objects.all()]

    def queryset(self, request, queryset):
        kod = self.value()
        if not kod:
            return queryset
        try:
            catalog = CatalogTraining.objects.get(pk=kod)
        except CatalogTraining.DoesNotExist:
            return queryset.none()

        months = catalog.platnost_mesicu_int
        # 0 / prázdná platnost v katalogu → školení bez expirace (stačí absolvování)
        if months is None or months == 0:
            return queryset.filter(completed_trainings__kod_skoleni_id=kod).distinct()

        today = timezone.localdate()
        return queryset.filter(
            completed_trainings__kod_skoleni_id=kod,
            completed_trainings__platnost_do__gte=today,
        ).distinct()


class ChybiPovinneSkoleniFilter(admin.SimpleListFilter):
    """Zaměstnanci, kterým podle útvaru/pozice chybí povinné platné školení."""

    title = "povinné školení"
    parameter_name = "chybi_povinne"

    def lookups(self, request, model_admin):
        return (("1", "chybí platné"),)

    def queryset(self, request, queryset):
        if self.value() != "1":
            return queryset
        catalogs = list(CatalogTraining.objects.all())
        today = timezone.localdate()
        # Prefetch už zajišťuje ActiveEmployeeAdmin.get_queryset — nepřidávat znovu.
        missing = _missing_required_pks(queryset, catalogs, today)
        return queryset.filter(pk__in=missing)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("kod", "nazev")
    search_fields = ("kod", "nazev")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id_zamestnance",
        "prijmeni",
        "jmeno",
        "email",
        "department",
        "pozice",
        "stav",
        "datum_nastupu",
        "datum_ukonceni",
    )
    list_filter = ("stav", "department", "pozice")
    search_fields = (
        "id_zamestnance",
        "jmeno",
        "prijmeni",
        "email",
        "department__nazev",
        "department__kod",
    )
    autocomplete_fields = ("department",)
    # rodné číslo je citlivý údaj – v seznamu nezobrazovat
    exclude = ()
    readonly_fields = ("id_zamestnance",)


@admin.register(ActiveEmployee)
class ActiveEmployeeAdmin(EmployeeAdmin):
    list_display = (
        "id_zamestnance",
        "prijmeni",
        "jmeno",
        "department",
        "pozice",
        "platna_skoleni",
        "kontrola_skoleni",
        "datum_nastupu",
        "datum_ukonceni",
    )
    list_filter = (
        "department",
        "pozice",
        PlatneSkoleniFilter,
        ChybiPovinneSkoleniFilter,
    )

    def get_queryset(self, request):
        self._catalogs = list(CatalogTraining.objects.all())
        return (
            super()
            .get_queryset(request)
            .select_related("department")
            .prefetch_related(
                Prefetch(
                    "completed_trainings",
                    queryset=CompletedTraining.objects.select_related("kod_skoleni"),
                )
            )
        )

    @admin.display(description="platná školení")
    def platna_skoleni(self, obj: ActiveEmployee) -> str:
        return ",".join(sorted(_valid_training_codes(obj, timezone.localdate())))

    @admin.display(boolean=True, description="školení")
    def kontrola_skoleni(self, obj: ActiveEmployee) -> bool:
        catalogs = getattr(self, "_catalogs", None)
        if catalogs is None:
            catalogs = list(CatalogTraining.objects.all())
        required = _required_training_codes(obj, catalogs)
        if not required:
            return True
        # False = chybí povinné platné školení
        return not bool(required - _valid_training_codes(obj, timezone.localdate()))


@admin.register(CatalogTraining)
class CatalogTrainingAdmin(admin.ModelAdmin):
    list_display = ("kod", "nazev", "platnost_mesicu", "povinne_pro")
    search_fields = ("kod", "nazev", "povinne_pro")
    readonly_fields = ("kod",)


@admin.register(TrainingDate)
class TrainingDateAdmin(admin.ModelAdmin):
    list_display = (
        "id_terminu",
        "kod_skoleni",
        "datum",
        "cas",
        "misto",
        "kapacita",
        "obsazeno",
        "cena_na_osobu",
        "stav",
    )
    list_filter = ("stav", "kod_skoleni", "misto")
    search_fields = ("id_terminu", "kod_skoleni__kod", "kod_skoleni__nazev", "misto")
    autocomplete_fields = ("kod_skoleni",)
    readonly_fields = ("id_terminu",)


@admin.register(CompletedTraining)
class CompletedTrainingAdmin(admin.ModelAdmin):
    list_display = (
        "id_zaznamu",
        "id_zamestnance",
        "zamestnanec",
        "kod_skoleni",
        "datum_absolvovani",
        "platnost_do",
        "delka_platnosti",
        "platnost_odpovida_icon",
        "poskytovatel",
        "cena_kc",
    )
    list_filter = ("kod_skoleni", "poskytovatel")
    search_fields = (
        "id_zaznamu",
        "id_zamestnance__id_zamestnance",
        "id_zamestnance__jmeno",
        "id_zamestnance__prijmeni",
        "zamestnanec",
        "kod_skoleni__kod",
        "kod_skoleni__nazev",
    )
    autocomplete_fields = ("id_zamestnance", "kod_skoleni")
    readonly_fields = ("id_zaznamu", "delka_platnosti", "platnost_odpovida_icon")

    @admin.display(boolean=True, description="platnost odpovídá")
    def platnost_odpovida_icon(self, obj: CompletedTraining) -> bool:
        return obj.platnost_odpovida
