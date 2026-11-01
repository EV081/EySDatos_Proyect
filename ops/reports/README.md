# Análisis de código: antes y después (F6, C-20)

Se generan con `python -m ops.scan <etiqueta>`. En CI (`.github/workflows/ci.yml`) cada herramienta corre en cada push y **rompe el build** ante cualquier hallazgo nuevo.

| Herramienta | Versión | Antes | Después |
|---|---|---|---|
| Bandit | 1.9.4 | 5 (todos de severidad baja) | 0 |
| Semgrep (`p/python`, `p/secrets`, `p/typescript`, `p/react`) | 1.182.1 | 4 | 0 |
| pip-audit, 4 componentes Python, con SBOM CycloneDX | 2.10.1 | 0 | 0 |
| npm audit, frontend, con SBOM CycloneDX | npm 11.4.1 | 0 | 0 |
| gitleaks (historial de git + árbol de archivos) | 8.30.1 | 0 + 2 | 0 + 0 |
| Pruebas de acceso ajeno por endpoint (`directory/tests/test_acceso_ajeno.py`) | — | ✔ | ✔ |

Reportes completos: [`antes/`](antes/) y [`despues/`](despues/). Los SBOM son `sbom-*.cdx.json`.

## Clasificación de cada hallazgo

| # | Herramienta | Dónde | Veredicto | Acción |
|---|---|---|---|---|
| 1 | gitleaks (árbol) | `ops/certs/private/ca.key`, `server.key` | **Defecto real de configuración.** Las llaves están ignoradas por git (el historial da 0), pero la exclusión de `.gitleaks.toml` estaba anclada con `^` y gitleaks informa rutas con el prefijo `/src/`, así que no excluía nada. Si alguien quitaba la regla de `.gitignore`, nada lo habría advertido de forma clara | Expresiones corregidas a `(^|/)…`. Prueba de control: una llave plantada en otra carpeta **sí** se detecta |
| 2–5 | Semgrep `react-insecure-request` | `frontend/e2e/smoke.mjs:62-63` | Falso positivo: `fetch` a servicios de la prueba e2e en `127.0.0.1` (la API del cliente solo escucha en localhost por diseño) | `// nosemgrep` con la justificación en la línea |
| 6 | Bandit B105 | `directory/app/oauth.py` (`TOKEN_URL`) | Falso positivo: es la URL del endpoint de tokens de Discord | `# nosec B105` con la justificación |
| 7 | Bandit B105 | `directory/app/oauth.py` (`"access_token"`) | Falso positivo: es el nombre de un campo del protocolo OAuth2 | `# nosec B105` |
| 8 | Bandit B105 | `client/dev.py` (`"dev-token"`) | Aceptado: token fijo solo del entorno de desarrollo en memoria (`python -m client.dev`), que escucha en 127.0.0.1; el arranque real genera uno aleatorio por ejecución | `# nosec B105` con la justificación |
| 9–10 | Bandit B404 | `ops/backup/backup.py`, `ops/scan.py` | Aceptado: `subprocess` con argumentos en lista, sin `shell=True` y con ejecutables fijos (`pg_dump`, `pg_restore`, `docker`, `npm`); las contraseñas van por `PGPASSWORD`, no en la línea de comandos | `# nosec B404` con la justificación |

Cada `nosec` y `nosemgrep` es puntual (una línea y una regla), así que cualquier código nuevo con el mismo problema sigue apareciendo.
