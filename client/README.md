# `client/` — API local del cliente

Une `crypto/`, el directorio y Discord, y expone una API HTTP **solo en 127.0.0.1** para el frontend. Es el único lugar donde existen las sesiones y el texto plano. Contrato para el frontend: [`docs/api/client.openapi.json`](../docs/api/client.openapi.json).

## Cómo correrlo

```bash
# Desarrollo (sin Discord ni directorio reales): Alice en :8001, Bob en :8002, token "dev-token"
.venv/bin/python -m client.dev

# Real (necesita directory/ y discord_adapter/ de Farid)
export DIRECTORY_URL=https://localhost:8443 DIRECTORY_CA_FILE=ops/certs/ca.pem
export DISCORD_TOKEN=... DISCORD_CHANNEL_ID=... CLIENT_API_TOKEN=... CLIENT_DATA_DIR=./data
.venv/bin/uvicorn client.main:app --host 127.0.0.1 --port 8001
```

Pruebas: `cd client && ../.venv/bin/python -m pytest -q`.

## Lo que el frontend debe saber

* **Auth:** todas las rutas (salvo `/health`) piden `Authorization: Bearer <token>`. CORS solo admite el origen del frontend (`CLIENT_ALLOWED_ORIGIN`). El `Host` debe ser `localhost` o `127.0.0.1`.
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
* **Errores:** siempre `{"error": <código>, "detail": <texto>}`. `423 locked` = pedir la contraseña maestra.

## Puertos que implementa Farid ([`ports.py`](ports.py))

* `DirectoryPort.register(discord_id, public_key, sign, consent_version)` (guardar la versión del aviso aceptado y la fecha) y `get_key(discord_id)`. Debe lanzar `DirectoryError` ante cualquier fallo.
* `DiscordPort.send(text)` y `set_receiver(callback)`. Debe llamar al `callback` con cada texto nuevo del canal (el autor es siempre un bot y no se usa) y **no** reentregar el historial viejo salvo al reconectar. `client/fakes.py` es la implementación de referencia.

## Qué se guarda en disco (todo cifrado)

`vault.json` (identidad: Argon2id + AES-GCM) y `store.enc` (AES-256-GCM con la `store_key`): contactos y pines, historial, cola de salida y contadores. **Nunca** se guardan llaves de sesión ni llaves efímeras: al reiniciar hay que hacer un handshake nuevo; la cola de salida se conserva.
