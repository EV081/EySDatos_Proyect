# API de `crypto/`

Librería pura de Python 3.12: sin red, sin Discord, sin disco. El cliente local (`client/`) la usa; el directorio (`directory/`) y el adaptador de Discord (`discord_adapter/`) **no** la importan, salvo `verify_registration`/`verify_key_change` y `Pseudonymizer`/`mask_id` en el directorio, que solo verifican firmas con llaves públicas y protegen los IDs de los registros.

```python
from crypto import (Identity, Initiator, Responder, SidCache, Session, fingerprint,
                    encode, decode, Hs1, Hs2, Hs3, Msg,
                    sign_registration, verify_registration, sign_key_change, verify_key_change)
```

Todos los errores heredan de `CryptoError`. Los ids son los identificadores de Discord (cadenas de dígitos). Las llaves públicas son `bytes` de 32 bytes. Los parámetros `clock` (opcional) son un `callable` que devuelve segundos, para poder probar el tiempo.

## Identidad (RF1, RF12, RS1, RS2)

| Función | Qué hace |
|---|---|
| `Identity.create()` | Genera una identidad Ed25519 y una `store_key` aleatoria (RF1, RS11) |
| `identity.public_key` | 32 bytes; es lo que se publica en el directorio |
| `identity.store_key` | 32 bytes; el cliente cifra con ella el historial y la cola de salida |
| `identity.to_vault(password, kdf=KdfParams())` | Bóveda JSON (`bytes`): Argon2id + salt único + AES-256-GCM. **Es también el archivo de exportación** (RF12): puede usar otra contraseña |
| `Identity.from_vault(blob, password)` | Abre la bóveda; `VaultError` si la contraseña es incorrecta o está corrupta |
| `identity.sign(context, message)` | Firma con separación de dominio; no hay forma de firmar sin contexto |
| `verify(public_key, context, message, sig)` | `SignatureError` si no vale |

## Directorio (prueba de posesión y cambio de llave)

| Función | Quién la usa |
|---|---|
| `sign_registration(identity, discord_id, nonce)` | Cliente: responde al `challenge` del directorio |
| `verify_registration(public_key, discord_id, nonce, sig)` | Directorio: comprueba la posesión antes de guardar la llave |
| `sign_key_change(old_identity, discord_id, new_public_key, nonce)` | Cliente: la llave anterior autoriza la nueva |
| `verify_key_change(old_public_key, discord_id, new_public_key, nonce, sig)` | Directorio |

## Handshake (RF4, RF13, RS12, RS13)

El cliente primero obtiene la llave pública del otro extremo del directorio, la compara con su *pin* si el contacto está verificado y **recién entonces** crea el objeto.

```python
# Iniciador (Alice)
init = Initiator(identity, my_id, peer_id, peer_public_key)
hs1 = init.start()                    # -> Hs1; publicar encode(hs1) en Discord
hs3, session = init.finish(hs2)       # <- Hs2 recibido; publicar encode(hs3)

# Respondedor (Bob): una instancia por cada hs1 recibido
seen = SidCache()                     # compartido por todos los hs1 de este cliente
resp = Responder(identity, my_id, peer_id, peer_public_key, seen)
hs2 = resp.respond(hs1)               # -> Hs2
session = resp.finish(hs3)            # <- Hs3 recibido
```

* Cualquier fallo lanza `HandshakeError` (o `ReplayError` para un `hs1` repetido). **Ante un error, el cliente muestra la alerta y no ofrece "continuar".**
* Un `hs2`/`hs3` inválido se rechaza pero no cancela el intento; solo lo cierran el éxito o los 300 s (`HANDSHAKE_TTL`). Tras caducar, el cliente crea un `Initiator` nuevo (reintentos de 15, 30, 60 min).
* La llave efímera del iniciador se destruye al terminar o caducar; el respondedor la destruye apenas hace el ECDH. Nunca se guarda en disco.

## Sesión (RF3, RF5, RF11, RS4, RS5, RS9, RS14)

| Método | Qué hace |
|---|---|
| `session.encrypt(plaintext) -> Msg` | AES-256-GCM, contador por dirección, nonce de 96 bits. Máximo `MAX_PLAINTEXT` = 900 bytes; el cliente parte los textos largos (`WireError`) |
| `session.decrypt(msg) -> bytes` | `DecryptError` (mensaje no descifrable, RF11), `ReplayError` (repetido o fuera de ventana) |
| `session.needs_rotation()` | `True` a los 100 mensajes o 8 h: **iniciar un nuevo handshake**, seguir usando esta sesión hasta que la nueva esté activa |
| `session.expired()` | Umbral duro (2×): la sesión deja de funcionar y levanta `SessionExpired` |
| `session.destroy()` | Borra las llaves de la sesión (al activarse la nueva, tras una breve gracia) |
| `session.sid`, `session.peer_id` | Para elegir la sesión de un mensaje entrante |

## Formato en Discord (`wire`)

`encode(obj) -> str` produce `E2EE1:<base64url(JSON)>` (≤ 2000 caracteres); `decode(text)` devuelve `Hs1`, `Hs2`, `Hs3` o `Msg`, o lanza `WireError`. **Nada decodificado es confiable todavía**: el autor que muestra Discord es siempre un bot; el cliente debe ignorar los mensajes cuyo `receiver` no sea su id y dejar que el handshake o el AES-GCM autentiquen el resto.

## Huella de verificación (RF6, RS8)

`fingerprint(pk_a, pk_b) -> "48291 37502 ..."` (60 dígitos en 12 grupos de 5, igual en ambos extremos). `crypto.fingerprint.qr_payload(pk_a, pk_b)` devuelve los 32 bytes completos para el QR.

## Seudonimización y enmascarado (registros y diagnóstico)

| Función | Qué hace |
|---|---|
| `Pseudonymizer(key)` / `Pseudonymizer.from_env("PSEUDONYM_KEY")` | HMAC-SHA256 con clave secreta (mínimo 32 bytes, base64url en la variable de entorno). Falla si la clave falta o es débil |
| `pseudonymizer.pseudonym(discord_id)` | 16 caracteres hex estables mientras no cambie la clave. **Úsese para los IDs en los registros de auditoría**; nunca un SHA-256 sin clave |
| `mask_id(discord_id)` | `1234…5678`, para mensajes de diagnóstico. No sirve para almacenar |
| `generate_key()` | Clave nueva (rotarla cada 90 días, el plazo de retención de los registros) |

## Qué **no** hace esta librería

* No consulta el directorio ni compara *pins*: lo hace `client/` (RF7, RF8).
* No guarda nada en disco: la bóveda, la cola y el historial los persiste `client/` (la `store_key` es para eso).
* No puede borrar la memoria con garantías: Python no permite zeroizar objetos inmutables; las llaves de sesión se guardan en `bytearray` y se ponen a cero al destruirlas, como mejor esfuerzo (RS3).

## Pruebas

```bash
cd crypto && ../.venv/bin/python -m pytest -q      # 126 pruebas
```

Los nombres de los tests llevan el requerimiento que cubren (`test_RS5_etiqueta_gcm_invalida_se_rechaza`) para armar la tabla de trazabilidad.
