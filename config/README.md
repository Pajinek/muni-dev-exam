# Production config

Apache vhost and Varhoo Manage deploy payload for **muni-exam.brno.pavelstudenik.cz**.

| | Value |
| --- | --- |
| Public URL | http://muni-exam.brno.pavelstudenik.cz |
| Deploy host | `s5.varhoo.cz` |
| Container | `muni_exam.prod` |
| Backend | `127.0.0.1:8010` → container `:80` |
| Image | `registry.slavicin.unart.cz/pajinek/muni-dev-exam:latest` |
| Settings | `muni_exam.settings.production` |
| Database | `postgresql.prod` linked as `postgresql.docker` |
| Static files | `/var/www/muni_exam/static` → `/app/muni_exam/static` |
| Media | `/var/www/muni_exam/storage` → `/app/muni_exam/storage` |
| Secrets | `/var/opt/secrets/muni_exam` |

## Files

| File | Role |
| --- | --- |
| [`8010-muni-exam.conf`](8010-muni-exam.conf) | Apache `:80` vhost → uWSGI on `:8010` |
| [`8010-muni-exam-le-ssl.conf`](8010-muni-exam-le-ssl.conf) | Apache `:443` vhost: TLS → uWSGI on `:8010` |
| [`deployment.json`](deployment.json) | `vhm-deploy` file used by the GitLab deploy component |

## Host prep (once)

On `s5.varhoo.cz`:

```bash
mkdir -p /var/www/muni_exam/static /var/www/muni_exam/storage
a2enmod proxy proxy_http alias headers rewrite ssl
```

Create PostgreSQL role/DB (linked container `postgresql.prod`):

```sql
CREATE DATABASE muni_exam;
CREATE USER muni_exam WITH PASSWORD '<password>';
GRANT ALL PRIVILEGES ON DATABASE muni_exam TO muni_exam;
```

Create `/var/opt/secrets/muni_exam` (not in git):

```
SECRET_KEY=<production secret>
ALLOWED_HOSTS=muni-exam.brno.pavelstudenik.cz
CSRF_TRUSTED_ORIGINS=http://muni-exam.brno.pavelstudenik.cz
```

Optional TLS (if enabling the SSL vhost later):

```bash
certbot --apache -d muni-exam.brno.pavelstudenik.cz
```

Cert paths expected by the SSL vhost: `/etc/letsencrypt/live/muni-exam.brno.pavelstudenik.cz/`.

After the first deploy, load sample data inside the container:

```bash
docker exec -it muni_exam.prod python manage.py import_json --data-dir imports/
docker exec -it muni_exam.prod python manage.py createsuperuser
```

## Docker (VHM)

[`deployment.json`](deployment.json) is the `vhm-deploy` file. The GitLab `deploy` job tags `:latest`, then runs `vhm-deploy`, which waits for `vh::docker::deploy`, `vh::configuration::deploy` (Apache confs from `files`), and `systemctl reload apache2`.

```json
{
  "hostname": "s5.varhoo.cz",
  "command": "vh::docker::deploy",
  "title": "CI deploy muni-exam",
  "params": {
    "registry": "registry.slavicin.unart.cz/pajinek/muni-dev-exam:latest",
    "name": "muni_exam.prod",
    "p": "127.0.0.1:8010:80",
    "link": "postgresql.prod:postgresql.docker",
    "env-file": "/var/opt/secrets/muni_exam",
    "e": "DJANGO_SETTINGS_MODULE=muni_exam.settings.production"
  }
}
```

The link alias `postgresql.docker` must match `DATABASES["default"]["HOST"]` in `muni_exam/settings/production.py`. Entrypoint runs `migrate` and `collectstatic` into `/app/muni_exam/static` (host bind for Apache `/static/`).

## GitLab CI

`.gitlab-ci.yml` includes `$CI_SERVER_FQDN/varhoo/vh-manage/deploy@main`. That component's `deploy` job:

1. Retags the commit image as `:latest` and pushes it.
2. Installs `vhm-deploy` and runs it on `config/deployment.json`.

Runs automatically on the default branch after `test` and `pylint`; manually on other branches. CI/CD variable: `VHM_SERVICE_TOKEN` (masked). This project must be allowed to use the vh-manage CI job token.
