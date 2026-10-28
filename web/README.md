# muni_exam

Webová aplikace pro evidenci školení zaměstnanců (praktický úkol výběrového řízení).

Django project based on [Varhoo/django-template](https://github.com/Varhoo/django-template).

Author: Pavel Studenik (pavelstudenik@gmail.com)

Stack: Django, Django REST framework, Docker (uWSGI), Ansible, GitLab CI.

## Purpose

Aplikace pracuje s fiktivními exporty školení (stav k **1. 10. 2026**). Cíl: přehled o proškolení zaměstnanců, blížícím se konci platnosti a kapacitě termínů.

Zdrojová CSV a JSON jsou v kořeni repozitáře (`../`). Převod CSV → JSON: `python3 ../csv_import.py` (viz [root README](../README.md)).

### Doménové modely (`apps/core`)

| Model | Zdroj | Popis |
|-------|--------|--------|
| `Employee` | `zamestnanci` | zaměstnanec, útvar, stav, nástup/ukončení |
| `CatalogTraining` | `katalog_skoleni` | druh školení, platnost, povinnost |
| `TrainingDate` | `terminy_skoleni` | termín, kapacita, obsazenost |
| `CompletedTraining` | `absolvovana_skoleni` | absolvované školení, platnost do |

Data jsou dostupná v Django adminu (`/admin/`). Domovská stránka je zatím šablonový placeholder.

## Quick start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_json --data-dir imports/   # načte imports/*.json do DB
python manage.py createsuperuser   # volitelné, pro /admin/
python manage.py runserver
```

### Import JSON

```bash
python manage.py import_json --data-dir imports/
python manage.py import_json --data-dir imports/ --clear   # smaže existující data a načte znovu
python manage.py import_json --data-dir /cesta/k/json
```

Doporučený zdroj je `web/imports/` (relativně z `web/`: `--data-dir imports/`). Bez `--data-dir` se bere kořen repozitáře (nad `web/`). Očekávané soubory: `katalog_skoleni.json`, `zamestnanci.json`, `terminy_skoleni.json`, `absolvovana_skoleni.json`.

Při importu se hlásí `přeskočeno` (neplatné řádky) a `duplicit` (opakované PK — zůstane první výskyt). U přiložených dat mají duplicity jen `absolvovana_skoleni.json` (15 duplicit + 3 přeskočené z 2868 řádků → 2850 importováno). Podrobnosti viz [root README](../README.md#duplicitní-a-přeskočené-záznamy).

Or with Docker Compose:

```bash
docker compose up --build
```

App listens on port **8000**. Settings default to `muni_exam.settings` (development → `settings/basic.py`, SQLite).

## Project layout

| Path | Purpose |
|------|---------|
| `apps/core/` | Doménové modely, admin, views |
| `muni_exam/settings/` | `basic.py` (dev), `production.py` |
| `muni_exam/templates/` | HTML šablony |
| `bin/` | Entrypoint a `generate_secret_key.py` |
| `ansible/` | Deploy playbooks a role |
| `config/hosts.ini.example` | Šablona inventáře pro Ansible |

## SECRET_KEY

Vygenerovat nový klíč:

```bash
python bin/generate_secret_key.py
```

Hodnotu uložte do `muni_exam/settings/basic.py` (nebo do produkčních secrets). Produkční klíče necommitujte.

## Database

Vývoj: SQLite (`db.sqlite3`). PostgreSQL (např. produkce):

```bash
docker run -e POSTGRES_PASSWORD=<password> --name postgresql.prod \
  -v /var/lib/postgresql/data:/var/lib/postgresql/data \
  -it -p 127.0.0.1:5432:5432 postgres
```

```sql
CREATE DATABASE <db>;
CREATE USER <user> WITH PASSWORD '<password>';
GRANT ALL PRIVILEGES ON DATABASE <db> TO <user>;
```

## Docker image

```bash
docker build -t muni_exam .
```

Image spustí migrace, `collectstatic` a uWSGI (`bin/docker-entrypoint.sh`). Produkční settings se použijí, pokud existuje `settings/production.py`.

## Code quality

```bash
make check
```

Spustí black, isort, pylint a obnoví `requirements.txt` přes `pip-compile`.

| Target | Action |
|--------|--------|
| `make upgrade` | Upgrade pinned závislostí |
| `make translate` | Aktualizace a kompilace gettext zpráv |
| `make deploy` | Ansible release proti `config/hosts.ini` |

Jednorázově:

```bash
pre-commit install
```

## Deploy

Produkce (preferované): GitLab CI + VHM. Konfigurace a postup jsou v [`../config/README.md`](../config/README.md). Veřejná URL: **http://muni-exam.brno.pavelstudenik.cz**.

Ansible alternativa (stejné hodnoty jako `../config/deployment.json`):

1. Zkopírujte `config/hosts.ini.example` → `config/hosts.ini` (`s5.varhoo.cz`).
2. Ověřte `ansible/group_vars/all.yml` (domain, registry, port `8010`, cesty).
3. Doplňte produkční secrets na hostu (`/var/opt/secrets/muni_exam`: `SECRET_KEY`, `ALLOWED_HOSTS`, …).
4. Release:

```bash
ansible-playbook -i config/hosts.ini ansible/release.yaml
```

Nebo: `make deploy`.

## CI

Pipeline žije v kořeni repozitáře (`../.gitlab-ci.yml`), build kontext je tento adresář `web/`:

1. **lint** — black + isort (+ smoke `csv_import.py` v kořeni)
2. **build** — Docker image do GitLab registry
3. **test** — `manage.py test` a pylint
4. **deploy** — retag `:latest` + `vhm-deploy` (`../config/deployment.json`)

