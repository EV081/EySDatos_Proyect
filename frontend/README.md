# `frontend/` — interfaz web (Next.js)

Sitio **100 % estático** (`output: 'export'`): no hay código de servidor. Todo el trabajo lo hace el cliente local (`client/`); esta interfaz solo habla con él por HTTP en `127.0.0.1`. Contrato: [`docs/api/client.openapi.json`](../docs/api/client.openapi.json).

## Cómo correrlo

```bash
# 1) backend de desarrollo (Alice :8001, Bob :8002, token "dev-token"; directorio y canal en memoria)
.venv/bin/python -m client.dev

# 2a) desarrollo con recarga en caliente
cd frontend && npm install && npm run dev            # http://127.0.0.1:5173
# 2b) o sitio exportado
npm run build && npm start                           # http://127.0.0.1:5173
```

Abre dos pestañas, una por usuario (el token y la dirección se pasan una sola vez por la URL y se borran de ella):

* Alice: `http://127.0.0.1:5173/?api=http://127.0.0.1:8001&token=dev-token`
* Bob: `http://127.0.0.1:5173/?api=http://127.0.0.1:8002&token=dev-token`

Con el backend real (Farid), el `api` es el puerto del cliente de cada persona y el `token` es `CLIENT_API_TOKEN`. Si se abre sin parámetros, pide la dirección y el token.

### Contra Discord y el directorio reales

Cada persona corre **su propio** `client/` en su laptop (nunca en un servidor: tiene las llaves privadas y el texto plano) y abre el frontend contra él:

```bash
# .env propio: DISCORD_TOKEN (de SU bot), DISCORD_CHANNEL_ID, DIRECTORY_URL, DIRECTORY_CA_FILE, CLIENT_API_TOKEN
make directory                                   # solo si el directorio corre en esta laptop (otra terminal)
python -m directory.client_lib.login             # una vez: token de registro con OAuth2 de Discord
make client                                      # API local en 127.0.0.1:8001 (CLIENT_PORT=8002 para otra)
make frontend                                    # http://127.0.0.1:5173
# abrir: http://127.0.0.1:5173/?api=http://127.0.0.1:8001&token=<CLIENT_API_TOKEN>
```

El frontend no cambia con Discord: sigue mostrando el texto plano que le entrega el cliente. En `#e2ee-relay` solo se ven `hs1`, `hs2`, `hs3` (llaves públicas y firmas) y luego `E2EE1:…` ilegible (AES-256-GCM en base64url). La dirección del cliente solo puede ser `127.0.0.1`/`localhost` (ver `lib/conn.ts`), aunque el directorio esté desplegado en otro servidor ([despliegue](../docs/despliegue-directorio.md)).

## Pruebas

```bash
npm run typecheck      # TypeScript
npm test               # 28 pruebas unitarias (lib/): formato, huella y QR, estados, errores, cliente HTTP
npm run build && npm run e2e   # 19 comprobaciones en Chromium real contra client.dev
```

La prueba `e2e` levanta el backend, sirve el sitio y maneja dos pestañas por el protocolo de depuración de Chromium (sin dependencias): crea las identidades, intercambia mensajes con handshake automático, verifica la huella, comprueba que un mensaje con HTML se muestra como texto y que el bloqueo exige la contraseña. Deja capturas en `$SHOTS_DIR` (por defecto la carpeta temporal).

## Qué cubre

| Elemento | Requerimiento |
|---|---|
| Registro, importación y desbloqueo de la identidad; exportación cifrada | RF1, RF12 |
| Candado y estado de sesión por conversación ("estableciendo sesión…", en cola) | RF9, RF14 |
| Insignia de verificado y ceremonia con la huella: código QR o 60 dígitos dictados en 12 casillas | RF6, RF7, RF9 |
| Alerta de cambio de llave y re-verificación (sin botón "continuar") | RF8 |
| Marcador "mensaje no descifrable" | RF11 |

## Decisiones de seguridad de la interfaz

* **Nada de lo que llega de Discord se interpreta como HTML:** todo se renderiza con React como texto (no se usa `dangerouslySetInnerHTML`). La prueba e2e lo comprueba con `<img onerror=…>`.
* **CSP en producción:** el navegador solo puede conectarse a `127.0.0.1`/`localhost`. Se permite `'unsafe-inline'` en scripts porque Next inserta el arranque en línea; la defensa de fondo es el punto anterior.
* **El token solo viaja a `127.0.0.1` o `localhost`** (se rechaza cualquier otra dirección) y vive en `sessionStorage`, no en `localStorage`.
* **Las contraseñas no se guardan:** se limpian de los campos tras usarlas.
* **Dependencias mínimas y fijadas** (`next`, `react`, `react-dom` y tipos), sin librerías de UI ni de estado. Las únicas añadidas son `qrcode-generator` (dibujar el QR) y `jsqr` (leerlo con la cámara), ambas sin dependencias propias.
* **La huella no se copia ni se pega** (RF7): la ceremonia tiene tres pestañas. *Código QR* dibuja el digest completo y lo lee con la cámara (cada uno escanea al otro; la imagen se procesa en el navegador y no se guarda). *Dictar* muestra los 12 grupos sin permitir seleccionarlos. *Escuchar* tiene 12 casillas de 5 dígitos que rechazan pegar y soltar, y mientras se escribe la huella propia no está en pantalla. Es una barrera de interfaz contra el atajo de copiar la huella propia, no un control criptográfico: la comparación la sigue haciendo el cliente local.

## Pendiente

* Selección de conversación por URL y notificaciones del navegador.
