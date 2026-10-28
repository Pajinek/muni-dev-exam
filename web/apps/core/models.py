import re
import unicodedata

from django.db import models


class Department(models.Model):
    """Organizační útvar."""

    kod = models.CharField(max_length=32, unique=True, blank=True)
    nazev = models.CharField(max_length=128)

    class Meta:
        ordering = ["nazev"]
        verbose_name = "útvar"
        verbose_name_plural = "útvary"

    @staticmethod
    def kod_from_nazev(nazev: str) -> str:
        """Odstraní diakritiku, převede na malá písmena, bílé znaky → _."""
        normalized = unicodedata.normalize("NFKD", nazev.strip())
        without_diacritics = "".join(
            c for c in normalized if not unicodedata.combining(c)
        )
        lower = without_diacritics.casefold()
        return re.sub(r"\s+", "_", lower)[:32]

    def save(self, *args, **kwargs):
        if not self.kod:
            self.kod = self.kod_from_nazev(self.nazev) or "utvar"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.nazev}"


class Employee(models.Model):
    """Zaměstnanec z exportu zamestnanci.csv."""

    class Status(models.TextChoices):
        ACTIVE = "aktivní", "aktivní"
        PARENTAL = "rodičovská", "rodičovská"
        TERMINATED = "ukončen", "ukončen"

    id_zamestnance = models.CharField(max_length=20, primary_key=True)
    jmeno = models.CharField(max_length=128)
    prijmeni = models.CharField(max_length=128)
    email = models.EmailField()
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    pozice = models.CharField(max_length=128)
    vedouci_email = models.EmailField(blank=True)
    datum_nastupu = models.DateField()
    datum_ukonceni = models.DateField(null=True, blank=True)
    stav = models.CharField(max_length=20, choices=Status.choices)
    rodne_cislo = models.CharField(max_length=20)
    poznamka = models.TextField(blank=True)

    class Meta:
        ordering = ["prijmeni", "jmeno"]
        verbose_name = "zaměstnanec"
        verbose_name_plural = "zaměstnanci"

    @staticmethod
    def normalize_name(value: str) -> str:
        """První písmeno velké, ostatní malá (např. LUCIE → Lucie)."""
        return value.strip().capitalize()

    def save(self, *args, **kwargs):
        self.jmeno = self.normalize_name(self.jmeno)
        self.prijmeni = self.normalize_name(self.prijmeni)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.prijmeni} {self.jmeno} ({self.id_zamestnance})"


class CatalogTraining(models.Model):
    """Druh školení z exportu katalog_skoleni.csv."""

    kod = models.CharField(max_length=32, primary_key=True)
    nazev = models.CharField(max_length=256)
    # v CSV i „2 roky“ / prázdné – ponecháno textově, číselný výklad při importu
    platnost_mesicu = models.CharField(max_length=32, blank=True)
    povinne_pro = models.CharField(max_length=256, blank=True)
    poznamka = models.TextField(blank=True)

    class Meta:
        ordering = ["kod"]
        verbose_name = "katalog školení"
        verbose_name_plural = "katalog školení"

    def __str__(self) -> str:
        return f"{self.kod} – {self.nazev}"


class TrainingDate(models.Model):
    """Termín školení z exportu terminy_skoleni.csv."""

    class Status(models.TextChoices):
        PLANNED = "plánováno", "plánováno"
        CANCELLED = "zrušeno", "zrušeno"

    id_terminu = models.CharField(max_length=20, primary_key=True)
    kod_skoleni = models.CharField(max_length=32, db_index=True)
    datum = models.DateField()
    cas = models.CharField(max_length=32)
    misto = models.CharField(max_length=128)
    kapacita = models.PositiveIntegerField()
    obsazeno = models.PositiveIntegerField(default=0)
    cena_na_osobu = models.PositiveIntegerField(null=True, blank=True)
    stav = models.CharField(max_length=20, choices=Status.choices)

    class Meta:
        ordering = ["datum", "id_terminu"]
        verbose_name = "termín školení"
        verbose_name_plural = "termíny školení"

    def __str__(self) -> str:
        return f"{self.id_terminu} {self.kod_skoleni} ({self.datum})"

    @property
    def volno(self) -> int:
        return max(0, self.kapacita - self.obsazeno)


class CompletedTraining(models.Model):
    """Absolvované školení z exportu absolvovana_skoleni.csv."""

    id_zaznamu = models.CharField(max_length=32, primary_key=True)
    id_zamestnance = models.CharField(max_length=20, db_index=True, blank=True)
    # denormalizované jméno z exportu (Příjmení Jméno)
    zamestnanec = models.CharField(max_length=128, blank=True)
    kod_skoleni = models.CharField(max_length=32, db_index=True, blank=True)
    datum_absolvovani = models.DateField(null=True, blank=True)
    platnost_do = models.DateField(null=True, blank=True)
    poskytovatel = models.CharField(max_length=128, blank=True)
    # CSV: „0,00“, „1 200,00“, záporné / „0,- Kč“ – číselný výklad při importu
    cena_kc = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    poznamka = models.TextField(blank=True)

    class Meta:
        ordering = ["-datum_absolvovani", "id_zaznamu"]
        verbose_name = "absolvované školení"
        verbose_name_plural = "absolvovaná školení"

    def __str__(self) -> str:
        return f"{self.id_zaznamu} {self.kod_skoleni} ({self.id_zamestnance})"

