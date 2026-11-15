# `directory/` — Directorio de llaves (F1)

Asocia IDs de Discord con llaves públicas de firma Ed25519. Nunca ve llaves privadas de mensajería ni contenido. Para autenticar a los usuarios conserva un secreto TOTP cifrado y hashes de códigos de recuperación. Contrato HTTP: [`docs/api/directory.yaml`](../docs/api/directory.yaml). Implementa `client.ports.DirectoryPort` con [`client_lib`](client_lib/__init__.py).

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

1. `python -m directory.client_lib.login` abre `/auth/login` y se inicia sesión con Discord (alcance `identify`, `state` + PKCE). El access token de Discord se revoca enseguida y no se guarda. La primera vez se vincula Microsoft Authenticator por QR; después se pide el código de seis dígitos. Solo tras verificarlo se muestra el **token de registro**: dura 10 minutos, sirve para una sola publicación y está ligado a ese ID.
2. El cliente (al crear o importar la identidad) llama a `register`: pide un nonce con `POST /v1/challenge` y publica con `PUT /v1/keys/{id}` la llave y la firma `sign_registration` (prueba de posesión).

Solo el dueño modifica su registro: el ID del token tiene que ser el de la ruta. Volver a publicar la misma llave es idempotente (reimportar en otro dispositivo). Una llave distinta reemplaza a la anterior, que se guarda 90 días en `replaced_keys`; si además viene `old_signature` (`sign_key_change` con la llave anterior), se exige que valga.

**Acceso** (`GET /v1/me`, `DirectoryClient.record`): con el token de registro (sin consumirlo), la persona ve su llave, fechas, aviso aceptado, llaves reemplazadas y estado del segundo factor. No se exportan el secreto TOTP ni los hashes de recuperación. Solo el registro del dueño del token.

**Rectificación** (cambio de llave): `DirectoryClient.register(..., sign_old=...)` envía `old_signature`, así la llave vigente autoriza a la nueva (`Identity.rotate()` conserva el almacén local).

**Cancelación** (`DELETE /v1/keys/{id}`, `DirectoryClient.cancel`): token de registro, más un nonce con propósito `cancel`, más la firma `sign_key_change` de la llave vigente hacia la llave nula (32 bytes en cero, que nadie puede registrar). Borra el registro y sus llaves reemplazadas en el acto. Pendiente: cuando `crypto/` tenga `sign_cancellation` con un contexto propio, se reemplaza.

## Decisiones de seguridad

| Medida | Dónde |
|---|---|
| Esquema mínimo: ID, llave, fechas y versión del aviso; sin IP ni perfil (C-05, C-14) | `migrations/001_init.sql`, `tests/test_esquema.py` |
| Prueba de posesión + OAuth2, nonces y tokens de un solo uso, solo el dueño (C-06) | `app/main.py`, `tests/test_registro.py`, `tests/test_acceso_ajeno.py` |
| Rol `directory_app` sin DDL, sin superusuario, solo DML; consultas siempre parametrizadas en `app/repo.py` (C-08) | `migrations/apply.py`, `tests/test_esquema.py` |
| *Rate-limit* por IP en memoria, más estricto en las consultas (anti-enumeración) | `app/ratelimit.py` |
| Errores genéricos: no distinguen ID inexistente, firma mala o token ajeno | `app/errors.py` |
| Solo se guardan hashes SHA-256 de `state`, tokens y nonces | `app/repo.py` |
| Purga: llaves reemplazadas a 90 días y estado efímero vencido (C-10; la tarea programada es parte de F4/F5) | `Repo.purge()` |

## Microsoft Authenticator

Configura `TOTP_ENCRYPTION_KEY` antes de arrancar. Es una clave Fernet independiente de la base;
el servicio falla al arrancar si falta o no es válida. No requiere credenciales de Microsoft ni pagos.
Consulta [la guía de activación en EC2](../docs/autenticacion-microsoft.md).

El QR se genera en el servidor sin enviar el secreto a terceros. En Microsoft Authenticator se agrega
como **Otra cuenta (Google, Facebook, etc.)**. TOTP usa seis dígitos y pasos de 30 segundos, con tolerancia
de un paso por desfase de reloj. Un código aceptado no se admite otra vez, incluso desde otra sesión.
El servidor debe tener sincronizada la hora.

Cada sesión de segundo factor dura cinco minutos. Cinco fallos bloquean la cuenta cinco minutos;
el contador se guarda en Postgres y no se reinicia al volver a pasar por Discord.
La cookie es HttpOnly, SameSite=strict y Secure con HTTPS; el formulario lleva protección CSRF.
La autenticación inicial vincula el primer factor después de demostrar control de Discord: hasta que
se confirme el primer QR, la cuenta aún no tiene un segundo factor previamente establecido.

Al vincular se muestran diez códigos de recuperación una sola vez. Usar uno obliga a escanear y confirmar
un nuevo QR antes de emitir un token; invalida el autenticador y todos los códigos de recuperación anteriores.
La cancelación del registro también borra el factor y sus sesiones. Los registros de autenticación pendientes
sin confirmar se purgan después de un día; las sesiones vencidas se borran con la tarea de mantenimiento.
Además de proteger la emisión del token, `POST /v1/sessions/challenge` y `POST /v1/sessions/verify`
validan cada desbloqueo habitual con un nonce de un solo uso, una firma de la llave registrada y TOTP.
Comparten el contador de intentos y el último paso aceptado con el flujo OAuth: no se puede reutilizar
un código en el otro flujo. La firma lleva un contexto propio (`directory session unlock`), por lo que
no autoriza registrar, cambiar ni cancelar llaves. No se genera un token de sesión que pueda reutilizarse.
La migración `004_session_mfa.sql` amplía los propósitos permitidos para los nonces.
La contraseña maestra y el descifrado de la identidad siguen siendo locales; el MFA no cambia el cifrado
de los archivos ni impide descifrar una copia robada si también se conoce su contraseña.

## TLS 1.3 (F2)

`python -m directory.serve` sirve en `https://localhost:8443` con el certificado de la CA propia y solo acepta TLS 1.3. `DirectoryClient` solo confía en `ca.pem` (más `crl.pem`, si se configura `DIRECTORY_CRL_FILE`) y no tiene opción para saltarse la verificación. Ver [ops/certs/README.md](../ops/certs/README.md).

## Registros de auditoría y alertas (F5)

Los eventos van en JSON, uno por línea, a `AUDIT_LOG_DIR/audit.jsonl`. Las alertas van a `alerts.jsonl` y, opcionalmente, a `ALERT_WEBHOOK_URL`. Ambos rotan a diario y se conservan **90 días** ([app/audit.py](app/audit.py)).

| Evento | Nivel | Campos |
|---|---|---|
| `login`, `registro`, `renovacion`, `cancelacion` | info | `id` seudonimizado; `aviso` (versión aceptada) |
| `cambio_de_llave` | warning | `id` seudonimizado |
| `firma_invalida` | warning | `id` seudonimizado |
| `mfa_rechazado` | warning | sin identificadores ni códigos |
| `mfa_recuperacion` | info | `id` seudonimizado; nunca el código |
| `sesion_local` | info | `id` seudonimizado; nunca contraseña, código ni firma |
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
