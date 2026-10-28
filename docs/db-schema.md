# Schéma databáze

Zdroj: Django modely v `web/apps/core/models.py`.

![Schéma DB](db-schema.svg)

```mermaid
erDiagram
    Department ||--o{ Employee : "employees"
    CatalogTraining ||--o{ TrainingDate : "training_dates"
    CatalogTraining ||--o{ CompletedTraining : "completed_trainings"
    Employee ||--o{ CompletedTraining : "completed_trainings"

    Department {
        int id PK
        string kod UK "max 32, auto z názvu"
        string nazev "max 128"
    }

    Employee {
        string id_zamestnance PK "max 20"
        string jmeno
        string prijmeni
        string email
        int department_id FK "SET NULL"
        string pozice
        string vedouci_email
        date datum_nastupu
        date datum_ukonceni "nullable"
        string stav "aktivní|rodičovská|ukončen"
        string rodne_cislo
        text poznamka
    }

    CatalogTraining {
        string kod PK "max 32"
        string nazev
        string platnost_mesicu "text, např. 24 / 2 roky"
        string povinne_pro
        text poznamka
    }

    TrainingDate {
        string id_terminu PK "max 20"
        string kod_skoleni_id FK "CASCADE"
        date datum
        string cas
        string misto
        int kapacita
        int obsazeno "default 0"
        int cena_na_osobu "nullable"
        string stav "plánováno|zrušeno"
    }

    CompletedTraining {
        string id_zaznamu PK "max 32"
        string id_zamestnance_id FK "CASCADE, nullable"
        string zamestnanec "denormalizované jméno"
        string kod_skoleni_id FK "CASCADE, nullable"
        date datum_absolvovani "nullable"
        date platnost_do "nullable"
        string poskytovatel
        decimal cena_kc "10,2 nullable"
        text poznamka
    }
```

## Tabulky a vazby

| Model (tabulka) | PK | Vztahy |
|-----------------|----|--------|
| **Department** (`core_department`) | `id` (auto) | ← `Employee.department` |
| **Employee** (`core_employee`) | `id_zamestnance` | → Department (`SET NULL`); ← CompletedTraining |
| **CatalogTraining** (`core_catalogtraining`) | `kod` | ← TrainingDate, CompletedTraining |
| **TrainingDate** (`core_trainingdate`) | `id_terminu` | → CatalogTraining (`CASCADE`) |
| **CompletedTraining** (`core_completedtraining`) | `id_zaznamu` | → Employee (`CASCADE`, nullable), → CatalogTraining (`CASCADE`, nullable) |

`ActiveEmployee` je jen **proxy** nad `Employee` (filtr `stav=aktivní`) — žádná nová tabulka.

## Poznámky k návrhu

- Útvar se při ukládání dopočítá z názvu (`kod_from_nazev`), pokud `kod` chybí.
- U zaměstnance se při `save` normalizuje jméno/příjmení a e-maily.
- `CompletedTraining.zamestnanec` drží denormalizované jméno z CSV; FK na zaměstnance může být prázdná (neznámá ID typu `E900x`).
- `platnost_mesicu` v katalogu je text; numerický výklad je v property `platnost_mesicu_int`.
