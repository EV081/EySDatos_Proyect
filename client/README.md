# `client/` — API local del cliente

Une `crypto/`, el directorio y Discord, y expone una API HTTP **solo en 127.0.0.1** para el frontend. Es el único lugar donde existen las sesiones y el texto plano. Contrato para el frontend: [`docs/api/client.openapi.json`](../docs/api/client.openapi.json).

## Ejecución

La [guía de ejecución local](../docs/guia/ejecucion-local.md) explica el `.env`, el token de registro, Authenticator y el arranque con `make client` y `make frontend`. Para preparar el directorio remoto está la [guía de EC2](../docs/guia/despliegue-ec2.md).

Pruebas: `cd client && ../.venv/bin/python -m pytest -q`.

Para una laptop conectada al directorio de EC2, copia [`.env.example.local`](../.env.example.local) a `.env` y completa sus valores según la guía. La plantilla [`.env.example`](../.env.example) corresponde al desarrollo con PostgreSQL y directorio locales.

## Lo que el frontend debe saber

* **Auth:** todas las rutas (salvo `/health`) piden `Authorization: Bearer <token>`. CORS solo admite el origen del frontend (`CLIENT_ALLOWED_ORIGIN`). El `Host` debe ser `localhost` o `127.0.0.1`.
* **Desbloqueo habitual:** `POST /identity/unlock {password, mfa_code}` exige la contraseña maestra y un código
  nuevo de Microsoft Authenticator con el directorio real. `GET /status` indica `mfa_required` y
  `session_expires_at`. El cliente firma un nonce del directorio con su identidad y EC2 verifica la firma
  y TOTP antes de abrir el historial. No necesita OAuth ni un token de registro en cada desbloqueo.
  Si el directorio no responde, permanece bloqueado; nunca continúa sin MFA. El modo `client.dev` es una
  demo offline con `FakeDirectory`, sin verificación de MFA.
* **Vencimiento:** la sesión local real dura como máximo `CLIENT_SESSION_TTL` segundos (1800 por defecto).
  Al bloquear, cerrar el cliente o vencer el plazo se descartan las llaves y las sesiones en memoria;
  el próximo desbloqueo exige un código nuevo. Cerrar solo la pestaña conserva la sesión del cliente local
  hasta bloquearla o vencer el plazo.
* **Sondeo, no push:** `GET /conversations/{id}/messages?since=<seq>` devuelve lo nuevo; cada entrada trae `seq` creciente. Sondear cada 1–2 s.
* **Estado de cada conversación (`session`):**

| Valor | Qué mostrar |
|---|---|
| `none` | Sin sesión todavía (candado abierto) |
| `handshaking` | "Estableciendo sesión…" (los mensajes quedan en cola, `queued`) |
| `active` | Candado cerrado |
| `waiting` | Contacto sin responder; se reintenta solo (15, 30, 60 min) |
| `unavailable` | Agotó los reintentos: botón **Reintentar** (`POST .../retry`) |
| `key_changed` | **Alerta de cambio de llave** (RF8): la verificación se revocó y no se envía nada hasta repetir la ceremonia. No ofrecer "continuar" |

* **Estado de cada mensaje (`status`):** `queued`, `sent`, `received`, `undecryptable` (RF11, sin `text`) y, con `dir: "sys"`, `key_changed` (alerta dentro de la conversación).
* **Verificar (RF7):** mostrar `GET /contacts/{id}/fingerprint`; el usuario compara fuera de Discord y escribe (o escanea) la huella que le dicta el otro; `POST /contacts/{id}/verify {fingerprint}` solo acepta si coincide (409 si no). Tras un cambio de llave, la huella que devuelve es la **nueva** (`key_pending: true`).
* **Quitar contacto:** `DELETE /contacts/{id}` (204) borra de este dispositivo sus sesiones, la llave fijada, la verificación, el historial y la cola; no toca el directorio. Lo que llegue por una sesión vieja se descarta; si el contacto abre una sesión nueva, reaparece **sin verificar**. Pedir confirmación en la interfaz: no se puede deshacer.
* **Errores:** siempre `{"error": <código>, "detail": <texto>}`. `423 locked` = pedir contraseña y autenticador;
  `403 mfa_required` = falta el código; `401 mfa_rejected` = factor rechazado; `502 directory_error` = no se pudo validar.
* **Derechos ARCO** (todas piden la contraseña maestra, salvo el acceso):
  * **Acceso:** `GET /privacy/my-data` → `local` (lo de este dispositivo), `directory` (el registro completo del directorio) y `directory_error` (`login_required`, `not_registered` o `unavailable` si no se pudo leer).
  * **Rectificación:** `POST /identity/rotate {password}` genera una llave nueva autorizada por la anterior; el historial se conserva. Los contactos verán la alerta de cambio de llave y deben volver a verificar.
  * **Cancelación y oposición:** `POST /identity/cancel {password, delete_local}` borra el registro del directorio y, con `delete_local: true`, también la identidad y el historial locales.
  * **Borrado local:** `POST /identity/delete-local {password}` borra `vault.json` y `store.enc` sin tocar el directorio (funciona con la identidad bloqueada).
  * Lo que toca el directorio exige haber iniciado sesión con Discord en los últimos 10 minutos; si no, responde `403 login_required`.

## Puertos que implementa Farid ([`ports.py`](ports.py))

* `DirectoryPort.register(discord_id, public_key, sign, consent_version, sign_old=None)` (guardar la versión del aviso aceptado y la fecha; `sign_old` autoriza un cambio de llave), `get_key(discord_id)`, `record(discord_id)` (acceso) y `cancel(discord_id, sign_key_change)`. Debe lanzar `DirectoryError` ante cualquier fallo, con `status=401` si falta iniciar sesión con Discord.
* `DiscordPort.send(text)` y `set_receiver(callback)`. Debe llamar al `callback` con cada texto nuevo del canal (el autor es siempre un bot y no se usa) y **no** reentregar el historial viejo salvo al reconectar. `client/fakes.py` es la implementación de referencia.

## Qué se guarda en disco (todo cifrado)

`vault.json` (identidad: Argon2id + AES-GCM) y `store.enc` (AES-256-GCM con la `store_key`): contactos y pines, historial, cola de salida y contadores. **Nunca** se guardan llaves de sesión ni llaves efímeras: al reiniciar hay que hacer un handshake nuevo; la cola de salida se conserva.

El MFA es un control del desbloqueo desde la aplicación. El formato de la bóveda sigue siendo cifrado por
contraseña: una copia de los archivos y la contraseña correcta permiten descifrarlos con otro programa.
No hemos añadido una clave de descifrado custodiada por el servidor. Tampoco se cambia el cifrado de las
exportaciones ni se envía la contraseña, la llave privada o el historial al directorio.
Si cancelas el registro conservando los archivos, se elimina el factor del servidor y deja de poder validar
el próximo desbloqueo habitual; exporta lo que necesites antes de cancelar.
