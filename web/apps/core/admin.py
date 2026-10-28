from datetime import date

from django.contrib import admin
from django.db.models import (
    BooleanField,
    Case,
    OuterRef,
    Prefetch,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    ActiveEmployee,
    AvailableTrainingDate,
    CatalogTraining,
    CompletedTraining,
    Department,
    Employee,
    MissingRequiredTraining,
    TrainingDate,
)

# Snapshot exportu CSV (README) — referenční datum dat v administraci
EXPORT_DATE = date(2026, 10, 1)
EXPORT_DATE_LABEL = EXPORT_DATE.strftime("%-d. %-m. %Y")

admin.site.site_header = f"Evidence školení — data z exportu {EXPORT_DATE_LABEL}"
admin.site.site_title = "Evidence školení"
admin.site.index_title = f"Přehled (export {EXPORT_DATE_LABEL})"


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


def _is_training_eligible(catalog: CatalogTraining, employee: Employee) -> bool:
    """Zda se zaměstnanec smí na daný druh školení přihlásit."""
    raw = (catalog.povinne_pro or "").strip()
    if not raw:
        return True
    upper = raw.casefold()
    if upper in ("nepovinne", "vsichni"):
        return True
    if raw.startswith("UTVAR:"):
        names = {n.strip() for n in raw[6:].split(";") if n.strip()}
        dept = employee.department
        return bool(dept and dept.nazev in names)
    if raw.startswith("POZICE:"):
        names = {n.strip() for n in raw[7:].split(";") if n.strip()}
        return employee.pozice in names
    return False


def _open_training_dates_for(employee: Employee, today: date) -> list[TrainingDate]:
    """Plánované budoucí termíny s volnou kapacitou, na které se může přihlásit."""
    dates = (
        TrainingDate.objects.filter(
            stav=TrainingDate.Status.PLANNED,
            datum__gte=today,
        )
        .select_related("kod_skoleni")
        .order_by("kod_skoleni__kod", "datum", "cas", "id_terminu")
    )
    return [
        td
        for td in dates
        if td.volno > 0 and td.kod_skoleni is not None and _is_training_eligible(td.kod_skoleni, employee)
    ]


def _is_completed_valid(completed: CompletedTraining, catalog: CatalogTraining, today: date) -> bool:
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


def _required_training_codes(employee: Employee, catalogs: list[CatalogTraining]) -> set[str]:
    return {c.kod for c in catalogs if _is_training_required(c, employee)}


def _missing_required_pks(queryset: QuerySet, catalogs: list[CatalogTraining], today: date) -> set[str]:
    missing: set[str] = set()
    for emp in queryset:
        required = _required_training_codes(emp, catalogs)
        if not required:
            continue
        if required - _valid_training_codes(emp, today):
            missing.add(emp.pk)
    return missing


def _missing_required_catalogs(
    employee: Employee, catalogs: list[CatalogTraining], today: date
) -> list[CatalogTraining]:
    missing = _required_training_codes(employee, catalogs) - _valid_training_codes(employee, today)
    return [c for c in catalogs if c.kod in missing]


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


class AbsolvovanaSkoleniInline(admin.TabularInline):
    """Read-only inline: všechna absolvovaná školení zaměstnance s flagem platnosti."""

    model = CompletedTraining
    fk_name = "id_zamestnance"
    extra = 0
    can_delete = False
    show_change_link = False
    verbose_name = "absolvované školení"
    verbose_name_plural = "absolvovaná školení"
    fields = (
        "kod_skoleni",
        "datum_absolvovani",
        "platnost_do",
        "je_platne",
        "poskytovatel",
    )
    readonly_fields = fields
    ordering = ()

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return True

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def get_queryset(self, request):
        today = timezone.localdate()
        # Platná (aktivní) první; logika shodná s _is_completed_valid.
        return (
            super()
            .get_queryset(request)
            .select_related("kod_skoleni")
            .annotate(
                _platne=Case(
                    When(kod_skoleni__isnull=True, then=Value(False)),
                    When(
                        Q(kod_skoleni__platnost_mesicu="") | Q(kod_skoleni__platnost_mesicu="0"),
                        then=Value(True),
                    ),
                    When(platnost_do__gte=today, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                )
            )
            .order_by("-_platne", "kod_skoleni__kod", "-datum_absolvovani")
        )

    @admin.display(boolean=True, description="platná")
    def je_platne(self, obj: CompletedTraining) -> bool:
        if obj.kod_skoleni is None:
            return False
        return _is_completed_valid(obj, obj.kod_skoleni, timezone.localdate())


class ChybejiciSkoleniInline(admin.TabularInline):
    """Read-only inline: required trainings that are missing or no longer valid."""

    model = MissingRequiredTraining
    fk_name = "employee"
    extra = 0
    can_delete = False
    show_change_link = False
    verbose_name = "missing required training"
    verbose_name_plural = "missing required trainings"
    fields = ("code", "name", "validity_months", "required_for", "ended_on")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return True

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def get_queryset(self, request):
        latest_end = (
            CompletedTraining.objects.filter(
                id_zamestnance_id=OuterRef("employee_id"),
                kod_skoleni_id=OuterRef("catalog_id"),
            )
            .order_by("-platnost_do", "-datum_absolvovani")
            .values("platnost_do")[:1]
        )
        return super().get_queryset(request).select_related("catalog").annotate(_ended_on=Subquery(latest_end))

    @admin.display(description="code")
    def code(self, obj: MissingRequiredTraining) -> str:
        return obj.catalog.kod

    @admin.display(description="name")
    def name(self, obj: MissingRequiredTraining) -> str:
        return obj.catalog.nazev

    @admin.display(description="validity (months)")
    def validity_months(self, obj: MissingRequiredTraining) -> str:
        return obj.catalog.platnost_mesicu or "—"

    @admin.display(description="required for")
    def required_for(self, obj: MissingRequiredTraining) -> str:
        return obj.catalog.povinne_pro or "—"

    @admin.display(description="ended on")
    def ended_on(self, obj: MissingRequiredTraining) -> str:
        ended = getattr(obj, "_ended_on", None)
        if ended is None:
            return "—"
        text = ended.isoformat()
        # Po datu exportu nemáme potvrzení, zda školení nebylo obnoveno.
        if EXPORT_DATE < ended <= timezone.localdate():
            return format_html(
                '{} (<span title="Nejsou k dispozici data kvůli stáří exportu '
                '(export {})." style="cursor:help">?</span>)',
                text,
                EXPORT_DATE_LABEL,
            )
        return text


class AvailableTrainingDateInline(admin.TabularInline):
    """Read-only inline: upcoming TrainingDate slots the employee can join."""

    model = AvailableTrainingDate
    fk_name = "employee"
    extra = 0
    can_delete = False
    show_change_link = False
    verbose_name = "available training date"
    verbose_name_plural = "available training dates"
    fields = (
        "id_terminu",
        "catalog_code",
        "catalog_name",
        "datum",
        "cas",
        "misto",
        "volno",
        "is_required",
    )
    readonly_fields = fields
    ordering = ()

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return True

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def get_queryset(self, request):
        self._missing_codes = None
        # Pořadí při syncu (pk rostoucí = pořadí bulk_create: code, date, time).
        return (
            super()
            .get_queryset(request)
            .select_related(
                "employee",
                "employee__department",
                "training_date",
                "training_date__kod_skoleni",
            )
            .order_by("pk")
        )

    @admin.display(description="id")
    def id_terminu(self, obj: AvailableTrainingDate) -> str:
        pk = obj.training_date_id
        if not pk:
            return "—"
        url = reverse("admin:core_trainingdate_change", args=[pk])
        return format_html('<a href="{}">{}</a>', url, pk)

    @admin.display(description="code")
    def catalog_code(self, obj: AvailableTrainingDate) -> str:
        return obj.training_date.kod_skoleni_id or "—"

    @admin.display(description="name")
    def catalog_name(self, obj: AvailableTrainingDate) -> str:
        catalog = obj.training_date.kod_skoleni
        return catalog.nazev if catalog else "—"

    @admin.display(description="date")
    def datum(self, obj: AvailableTrainingDate) -> str:
        return obj.training_date.datum.isoformat()

    @admin.display(description="time")
    def cas(self, obj: AvailableTrainingDate) -> str:
        return obj.training_date.cas

    @admin.display(description="place")
    def misto(self, obj: AvailableTrainingDate) -> str:
        return obj.training_date.misto

    @admin.display(description="free seats")
    def volno(self, obj: AvailableTrainingDate) -> int:
        return obj.training_date.volno

    @admin.display(boolean=True, description="required")
    def is_required(self, obj: AvailableTrainingDate) -> bool:
        """True jen pokud školení chybí v missing required (např. E0104: POZ-OCH)."""
        kod = obj.training_date.kod_skoleni_id
        if not kod:
            return False
        missing = getattr(self, "_missing_codes", None)
        if missing is None:
            missing = set(
                MissingRequiredTraining.objects.filter(employee_id=obj.employee_id).values_list("catalog_id", flat=True)
            )
            self._missing_codes = missing
        return kod in missing


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
    fields = (
        "odkaz_zamestnanec",
        ("jmeno", "prijmeni"),
        ("email", "vedouci_email"),
        ("department", "pozice"),
    )
    readonly_fields = (
        "odkaz_zamestnanec",
        "jmeno",
        "prijmeni",
        "email",
        "vedouci_email",
        "department",
        "pozice",
    )
    autocomplete_fields = ()
    inlines = (
        ChybejiciSkoleniInline,
        AbsolvovanaSkoleniInline,
        AvailableTrainingDateInline,
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

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if object_id:
            self._sync_missing_required_trainings(object_id)
            self._sync_available_training_dates(object_id)
        return super().changeform_view(request, object_id, form_url, extra_context)

    def _load_active_employee(self, employee_id: str) -> ActiveEmployee | None:
        try:
            return (
                ActiveEmployee.objects.select_related("department")
                .prefetch_related(
                    Prefetch(
                        "completed_trainings",
                        queryset=CompletedTraining.objects.select_related("kod_skoleni"),
                    )
                )
                .get(pk=employee_id)
            )
        except ActiveEmployee.DoesNotExist:
            return None

    def _sync_missing_required_trainings(self, employee_id: str) -> None:
        """Obnoví řádky MissingRequiredTraining podle aktuální povinnosti a platnosti."""
        employee = self._load_active_employee(employee_id)
        if employee is None:
            return

        catalogs = getattr(self, "_catalogs", None)
        if catalogs is None:
            catalogs = list(CatalogTraining.objects.all())
        missing = _missing_required_catalogs(employee, catalogs, timezone.localdate())
        MissingRequiredTraining.objects.filter(employee_id=employee_id).delete()
        MissingRequiredTraining.objects.bulk_create(
            [MissingRequiredTraining(employee_id=employee_id, catalog=c) for c in missing]
        )

    def _sync_available_training_dates(self, employee_id: str) -> None:
        """Obnoví řádky AvailableTrainingDate (otevřené termíny pro přihlášení)."""
        employee = self._load_active_employee(employee_id)
        if employee is None:
            return

        open_dates = _open_training_dates_for(employee, timezone.localdate())
        missing_codes = set(
            MissingRequiredTraining.objects.filter(employee_id=employee_id).values_list("catalog_id", flat=True)
        )
        open_dates.sort(
            key=lambda td: (
                0 if td.kod_skoleni_id in missing_codes else 1,
                td.kod_skoleni_id or "",
                td.datum,
                td.cas or "",
                td.id_terminu,
            )
        )
        AvailableTrainingDate.objects.filter(employee_id=employee_id).delete()
        AvailableTrainingDate.objects.bulk_create(
            [AvailableTrainingDate(employee_id=employee_id, training_date=td) for td in open_dates]
        )

    def save_formset(self, request, form, formset, change):
        # Inliny jsou jen zobrazení – neukládat ruční změny.
        if formset.model in (
            MissingRequiredTraining,
            CompletedTraining,
            AvailableTrainingDate,
        ):
            return
        super().save_formset(request, form, formset, change)

    @admin.display(description="zaměstnanec")
    def odkaz_zamestnanec(self, obj: ActiveEmployee) -> str:
        if not obj or not obj.pk:
            return "—"
        url = reverse("admin:core_employee_change", args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj)

    @admin.display(description="platná školení")
    def platna_skoleni(self, obj: ActiveEmployee) -> str:
        return ",".join(sorted(_valid_training_codes(obj, timezone.localdate())))

    @admin.display(boolean=True, description="školení")
    def kontrola_skoleni(self, obj: ActiveEmployee) -> bool:
        catalogs = getattr(self, "_catalogs", None)
        if catalogs is None:
            catalogs = list(CatalogTraining.objects.all())
        # False = chybí povinné platné školení
        return not bool(_missing_required_catalogs(obj, catalogs, timezone.localdate()))


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
