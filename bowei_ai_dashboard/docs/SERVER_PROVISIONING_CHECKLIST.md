# Server Provisioning Checklist

This checklist is for the production-ready Linux host that will run Bowei AI Dashboard in same-origin deployment mode.

## 1. Recommended server profile

- OS: Ubuntu 22.04 LTS or 24.04 LTS
- Minimum: 2 vCPU / 4 GB RAM
- Recommended: 2 vCPU / 8 GB RAM or higher
- Disk: 40 GB minimum, 80 GB+ recommended

## 2. Required system packages

Install the following before deployment:

- Python 3.11+
- Node.js 20+
- Nginx
- Git
- sqlite3
- systemd

## 3. Directory layout

Recommended paths:

- Backend: `/opt/bowei_ai_dashboard`
- Frontend dist: `/opt/bowei_frontend/dist`
- Environment file: `/etc/bowei-ai-dashboard.env`
- Nginx logs: `/var/log/nginx/`

## 4. Port plan

- 80 and 443 exposed to the public
- 8008 bound to `127.0.0.1` only
- Do not expose the FastAPI port directly to the internet

## 5. HTTPS requirements

- Use a valid TLS certificate on Nginx
- Keep `SESSION_COOKIE_SECURE=true` in production
- Do not run the production site over plain HTTP

## 6. Backup guidance

- Store database backups in a dedicated backups directory on the server
- Use the backup and restore SOP in `docs/DB_BACKUP_RESTORE_SOP.md`
- Do not co-locate backups with runtime temp files

## 7. SQLite deployment note

- SQLite is acceptable for internal trial and small-scope trial usage
- Do not run multiple write-heavy instances against the same SQLite database
- Do not treat SQLite as the final multi-node production database plan

## 8. Minimum software layout

- Backend virtual environment under `/opt/bowei_ai_dashboard/.venv`
- Frontend build output published to `/opt/bowei_frontend/dist`
- Nginx config should reverse proxy `/api/*` to `127.0.0.1:8008`

## 9. Before you start

- Verify the backend repository is clean
- Verify the frontend repository is clean
- Verify the frontend build succeeds
- Verify the backend regression and isolated write tests pass
- Verify production secrets are present in the environment file, not in git
