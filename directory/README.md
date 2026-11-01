# `directory/` — Directorio de llaves (F1)

Asocia IDs de Discord con llaves públicas de firma Ed25519. Es un tablón pasivo: nunca ve material secreto ni contenido. Contrato HTTP: [`docs/api/directory.yaml`](../docs/api/directory.yaml). Implementa `client.ports.DirectoryPort` con [`client_lib`](client_lib/__init__.py).

## Cómo correrlo

```bash
cp .env.example .env              # completar contraseñas, PSEUDONYM_KEY y la app OAuth2 de Discord
docker compose up -d db           # Postgres 17 en 127.0.0.1:55432
set -a; . ./.env; set +a
.venv/Scripts/python -m directory.migrations.apply      # roles y esquema (idempotente)
.venv/Scripts/python -m ops.certs.pki init               # una vez: CA propia y certificado (F2)
.venv/Scripts/python -m directory.serve                  # https://localhost:8443, solo TLS 1.3
```

`directory.serve` arranca sin el registro de acceso de uvicorn, que escribiría la IP y la ruta con el ID de Discord en claro (C-05, C-09). Si se usa `uvicorn` a mano, `--no-access-log` es obligatorio.

Pruebas (necesitan el Postgres de Compose; crean y borran la base `directory_test`): `cd directory && ../.venv/Scripts/python -m pytest -q`.

## Publicar una llave

1. `python -m directory.client_lib.login` abre `/auth/login` y se inicia sesión con Discord (alcance `identify`, `state` + PKCE). La página de vuelta muestra un **token de registro**: dura 10 minutos, sirve para una sola publicación y está ligado a ese ID. El access token de Discord se revoca enseguida y no se guarda.
2. El cliente (al crear o importar la identidad) llama a `register`: pide un nonce con `POST /v1/challenge` y publica con `PUT /v1/keys/{id}` la llave y la firma `sign_registration` (prueba de posesión).

Solo el dueño modifica su registro: el ID del token tiene que ser el de la ruta. Volver a publicar la misma llave es idempotente (reimportar en otro dispositivo). Una llave distinta reemplaza a la anterior, que se guarda 90 días en `replaced_keys`; si además viene `old_signature` (`sign_key_change` con la llave anterior), se exige que valga.

**Cancelación** (`DELETE /v1/keys/{id}`, `DirectoryClient.cancel`): token de registro, más un nonce con propósito `cancel`, más la firma `sign_key_change` de la llave vigente hacia la llave nula (32 bytes en cero, que nadie puede registrar). Borra el registro y sus llaves reemplazadas en el acto. Pendiente: cuando `crypto/` tenga `sign_cancellation` con un contexto propio, se reemplaza.

## Decisiones de seguridad

| Medida | Dónde |
|---|---|
| Esquema mínimo: ID, llave, fechas y versión del aviso; sin IP ni perfil (C-05, C-14) | `migrations/001_init.sql`, `tests/test_esquema.py` |
| Prueba de posesión + OAuth2, nonces y tokens de un solo uso, solo el dueño (C-06) | `app/main.py`, `tests/test_registro.py`, `tests/test_acceso_ajeno.py` |
| Rol `directory_app` sin DDL, sin superusuario, solo DML en 5 tablas; consultas siempre parametrizadas en `app/repo.py` (C-08) | `migrations/apply.py`, `tests/test_esquema.py` |
| *Rate-limit* por IP en memoria, más estricto en las consultas (anti-enumeración) | `app/ratelimit.py` |
| Errores genéricos: no distinguen ID inexistente, firma mala o token ajeno | `app/errors.py` |
| Solo se guardan hashes SHA-256 de `state`, tokens y nonces | `app/repo.py` |
| Purga: llaves reemplazadas a 90 días y estado efímero vencido (C-10; la tarea programada es parte de F4/F5) | `Repo.purge()` |

## TLS 1.3 (F2)

`python -m directory.serve` sirve en `https://localhost:8443` con el certificado de la CA propia y solo acepta TLS 1.3. `DirectoryClient` solo confía en `ca.pem` (más `crl.pem`, si se configura `DIRECTORY_CRL_FILE`) y no tiene opción para saltarse la verificación. Ver [ops/certs/README.md](../ops/certs/README.md).

## Registros de auditoría y alertas (F5)

Los eventos van en JSON, uno por línea, a `AUDIT_LOG_DIR/audit.jsonl`. Las alertas van a `alerts.jsonl` y, opcionalmente, a `ALERT_WEBHOOK_URL`. Ambos rotan a diario y se conservan **90 días** ([app/audit.py](app/audit.py)).

| Evento | Nivel | Campos |
|---|---|---|
| `login`, `registro`, `renovacion`, `cancelacion` | info | `id` seudonimizado; `aviso` (versión aceptada) |
| `cambio_de_llave` | warning | `id` seudonimizado |
| `firma_invalida` | warning | `id` seudonimizado |
| `acceso_ajeno` | warning | `id` (quien intenta) y `objetivo`, seudonimizados |
| `limite` | warning | `grupo` de rutas (sin IP) |
| `mantenimiento` | info/error | resultado de la tarea diaria |

| Alerta | Regla |
|---|---|
| Intento de modificar el registro de otra persona | 1 `acceso_ajeno` |
| Pruebas de posesión inválidas repetidas | 5 `firma_invalida` en 10 min |
| Posible enumeración | 3 `limite` en 5 min, o 20 consultas de IDs no registrados en 10 min |
| Cambio de llave / posible toma de cuentas | cada `cambio_de_llave`; 3 en una hora |

**Sin datos personales ni secretos (C-09):** los IDs se seudonimizan con HMAC (`PSEUDONYM_KEY`, que se rota cada 90 días; tras rotarla, los registros viejos ya no se pueden vincular con los nuevos). Nunca se registran IPs, llaves, tokens ni mensajes. Un filtro de redacción borra además cualquier cosa con forma de ID, secreto o mensaje `E2EE1:`. `test_C09_registros_reales_sin_datos_personales_ni_secretos` recorre todos los flujos y revisa el archivo real. Las consultas de IDs inexistentes solo se cuentan para las alertas; no se registran.

**Tarea diaria:** `python -m ops.scheduled daily --env .env` hace la copia de seguridad, purga la base (llaves reemplazadas de más de 90 días y estado efímero) y borra los registros de más de 90 días. Ver [ops/backup/README.md](../ops/backup/README.md) para programarla.
