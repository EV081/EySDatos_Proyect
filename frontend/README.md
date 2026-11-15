# `frontend/` — interfaz web (Next.js)

Sitio **100 % estático** (`output: 'export'`): no hay código de servidor. Todo el trabajo lo hace el cliente local (`client/`); esta interfaz solo habla con él por HTTP en `127.0.0.1`. Contrato: [`docs/api/client.openapi.json`](../docs/api/client.openapi.json).

## Ejecución

Sigue la [guía de ejecución local](../docs/guia/ejecucion-local.md): incluye las variables del cliente, el login con Discord y Authenticator, `make client`, `make frontend` y la conexión de la interfaz. El directorio remoto se prepara con la [guía de EC2](../docs/guia/despliegue-ec2.md).

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
| Código de Microsoft Authenticator en cada desbloqueo con el directorio real; vencimiento de sesión | `CLIENT_SESSION_TTL`, `client/tests/test_session_mfa.py`, `directory/tests/test_session_mfa.py` |
| Candado y estado de sesión por conversación ("estableciendo sesión…", en cola) | RF9, RF14 |
| Insignia de verificado y ceremonia con la huella: código QR o 60 dígitos dictados en 12 casillas | RF6, RF7, RF9 |
| Alerta de cambio de llave y re-verificación (sin botón "continuar") | RF8 |
| Marcador "mensaje no descifrable" | RF11 |
| "Mis datos y derechos ARCO": acceso (descarga en JSON), cambio de llave, cancelación/oposición y borrado de los datos del dispositivo | Ley 29733 (ARCO) |

## Decisiones de seguridad de la interfaz

* **Nada de lo que llega de Discord se interpreta como HTML:** todo se renderiza con React como texto (no se usa `dangerouslySetInnerHTML`). La prueba e2e lo comprueba con `<img onerror=…>`.
* **CSP en producción:** el navegador solo puede conectarse a `127.0.0.1`/`localhost`. Permitimos `'unsafe-inline'` en scripts porque Next inserta el arranque en línea; la defensa de fondo es el punto anterior.
* **El token solo viaja a `127.0.0.1` o `localhost`** (se rechaza cualquier otra dirección) y vive en `sessionStorage`, no en `localStorage`.
* **Las contraseñas no se guardan:** se limpian de los campos tras usarlas.
* **Dependencias mínimas y fijadas** (`next`, `react`, `react-dom` y tipos), sin librerías de UI ni de estado. Las únicas añadidas son `qrcode-generator` (dibujar el QR) y `jsqr` (leerlo con la cámara), ambas sin dependencias propias.
* **La huella no se copia ni se pega** (RF7): la ceremonia tiene tres pestañas. *Código QR* dibuja el digest completo y lo lee con la cámara (cada uno escanea al otro; la imagen se procesa en el navegador y no se guarda). *Dictar* muestra los 12 grupos sin permitir seleccionarlos. *Escuchar* tiene 12 casillas de 5 dígitos que rechazan pegar y soltar, y mientras se escribe la huella propia no está en pantalla. Es una barrera de interfaz contra el atajo de copiar la huella propia, no un control criptográfico: la comparación la sigue haciendo el cliente local.

## Pendiente

* Selección de conversación por URL y notificaciones del navegador.
