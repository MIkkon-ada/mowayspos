# L4 Server Validation Checklist

Use this checklist on a real Linux server when validating same-origin deployment.

## 1. Repository checks

- `git status --short` is empty in the backend repository
- `git status --short` is empty in the frontend repository
- Confirm the expected baseline commits exist

## 2. Frontend dist checks

- `/opt/bowei_frontend/dist/index.html` exists
- `/opt/bowei_frontend/dist/assets/` exists
- JS and CSS assets include content hashes

## 3. Environment file checks

- Confirm `/etc/bowei-ai-dashboard.env` exists
- Confirm it contains only variable names and secret values are not leaked in logs
- Confirm production settings are present

## 4. systemd checks

- `systemd-analyze verify /etc/systemd/system/bowei.service`
- `systemctl status bowei --no-pager`
- Confirm backend listens on `127.0.0.1:8008`
- Confirm the service uses `--workers 2`

## 5. Nginx checks

- `nginx -t`
- Confirm `/opt/bowei_frontend/dist` is the document root
- Confirm `/api/` is proxied to `127.0.0.1:8008`
- Confirm SPA fallback is enabled for `/login`, `/projects`, `/project/*`, `/admin/*`

## 6. API checks

- `GET /api/health` returns 200
- `GET /api/health` returns `status=ok`
- `GET /api/health` returns `database=ok`
- `/api/*` routes are not swallowed by SPA fallback

## 7. Browser checks

- `GET /`
- `GET /login`
- `GET /projects`
- `GET /project/2`
- `GET /project/2/tasks`
- `GET /admin/projects`
- Refresh deep links and confirm no 404

## 8. Login / session checks

- `POST /api/auth/login` returns 200
- Cookie name is `bowei_session`
- `HttpOnly` is set
- `SameSite=lax`
- `Secure` is set when using HTTPS production deployment
- `GET /api/auth/me` returns 200 after login
- `POST /api/auth/logout` returns 200
- `GET /api/auth/me` returns 401 after logout

## 9. Database checks

- Record `bowei_ai_dashboard.db` mtime before and after validation
- Confirm only expected session writes occurred
- Do not run destructive write tests against the production database

## 10. Failure handling

- If Nginx fails, classify as Nginx configuration issue
- If backend fails to start, classify as service or environment issue
- If login fails, classify as cookie / environment / backend session issue
- If refresh on deep links fails, classify as SPA fallback issue
- If API routes are swallowed, classify as Nginx routing issue
