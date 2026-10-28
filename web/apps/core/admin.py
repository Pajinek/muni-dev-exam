from django.contrib import admin

from .models import (
    CatalogTraining,
    CompletedTraining,
    Employee,
    TrainingDate,
)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        "id_zamestnance",
        "prijmeni",
        "jmeno",
        "email",
        "utvar",
        "pozice",
        "stav",
        "datum_nastupu",
        "datum_ukonceni",
    )
    list_filter = ("stav", "utvar", "pozice")
    search_fields = (
        "id_zamestnance",
        "jmeno",
        "prijmeni",
        "email",
        "utvar",
    )
    # rodné číslo je citlivý údaj – v seznamu nezobrazovat
    exclude = ()
    readonly_fields = ("id_zamestnance",)


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
    search_fields = ("id_terminu", "kod_skoleni", "misto")
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
        "poskytovatel",
        "cena_kc",
    )
    list_filter = ("kod_skoleni", "poskytovatel")
    search_fields = (
        "id_zaznamu",
        "id_zamestnance",
        "zamestnanec",
        "kod_skoleni",
    )
    readonly_fields = ("id_zaznamu",)
