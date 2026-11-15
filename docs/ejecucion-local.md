# Ejecutar la aplicación en tu computadora

Cada persona ejecuta su cliente y su frontend en su computadora. El directorio está en EC2, Virginia del Norte (`us-east-1`), y PostgreSQL está en Supabase. Para preparar ese servidor está la [guía de EC2](despliegue-ec2.md).

Los comandos siguientes se ejecutan desde la raíz del repositorio en Linux, macOS o WSL. Necesitas Git, Make, Python 3.12 y Node.js con npm (Next.js exige Node 20.9 o posterior). Instala también Microsoft Authenticator u otra app compatible con TOTP en tu celular.

## 1. Preparar el proyecto

Si todavía no tienes el repositorio:

```bash
git clone https://github.com/EV081/EySDatos_Proyect.git
cd EySDatos_Proyect
```

Crea el entorno e instala las dependencias de Python:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Si ya tienes `.venv`, reutilízalo. `make frontend` instalará y compilará las dependencias de la interfaz.

## 2. Preparar Discord y los certificados

Cada participante necesita su propio bot, agregado al mismo servidor y canal privado del proyecto. Obtén su token en Discord Developer Portal y copia el ID del canal `#e2ee-relay`. El bot necesita ver el canal, enviar mensajes y leer el historial. Tu ID personal de Discord es distinto del ID del bot: usarás el personal al crear tu identidad.

Pide al responsable del directorio estos datos:

- URL HTTPS del directorio desplegado, incluido su puerto, normalmente `https://HOST_EC2:8443`.
- `ca.pem` y `crl.pem` vigentes. Colócalos en `ops/certs/`.

Importa `ca.pem` como autoridad de confianza para sitios web en el navegador que usarás para iniciar sesión con Discord. La librería de Python usa los archivos indicados en el `.env`; el navegador configura su confianza por separado. El nombre o IP de la URL debe figurar en el certificado del servidor. No necesitas la llave privada de la CA ni la del servidor.

## 3. Configurar tu `.env`

El archivo `.env` va en la raíz del repositorio. Conserva el que ya tengas y ajusta los valores; no copies el `.env` de EC2. Para usar el servidor remoto basta esta configuración local:

```dotenv
DIRECTORY_URL=https://HOST_EC2:8443
DIRECTORY_CA_FILE=ops/certs/ca.pem
DIRECTORY_CRL_FILE=ops/certs/crl.pem
DIRECTORY_AUTH_TOKEN_FILE=./data/directory-token

DISCORD_TOKEN=TOKEN_DE_TU_BOT
DISCORD_CHANNEL_ID=ID_DEL_CANAL_PRIVADO

CLIENT_API_TOKEN=TOKEN_LOCAL_LARGO_Y_ALEATORIO
CLIENT_DATA_DIR=./data
CLIENT_SESSION_TTL=1800
CLIENT_ALLOWED_ORIGIN=http://127.0.0.1:5173
```

Sustituye todos los ejemplos por tus valores. Para generar `CLIENT_API_TOKEN`, ejecuta `openssl rand -hex 32` y copia el resultado a tu `.env`. Protege el archivo:

```bash
chmod 600 .env
```

No necesitas credenciales de PostgreSQL, `DISCORD_CLIENT_SECRET` ni `TOTP_ENCRYPTION_KEY` en la laptop para conectarte al directorio remoto. No definas `DIRECTORY_AUTH_TOKEN` si usarás el archivo: esa variable tiene prioridad sobre el token guardado.

## 4. Iniciar sesión con Discord y vincular Authenticator

Este paso se usa antes de crear o importar una identidad y cuando necesites un token nuevo para operaciones sobre tu registro. Carga el `.env` en esta terminal; `make client` carga su propio entorno y no lo configura para los demás comandos:

```bash
set -a
. ./.env
set +a
.venv/bin/python -m directory.client_lib.login
```

1. Se abre el navegador en `/auth/login`. Si no se abre, visita la URL que imprime el comando.
2. Autoriza tu cuenta personal de Discord.
3. La primera vez, en Authenticator elige agregar otra cuenta y escanea el QR. Si ya está vinculado, escribe un código nuevo de seis dígitos.
4. Guarda los diez códigos de recuperación fuera del dispositivo; solo se muestran una vez al vincular el factor.
5. Copia el **token de registro** de la página y pégalo una sola vez en la terminal. Al pegarlo no se muestran caracteres. Presiona Enter.

El comando guarda el token en `data/directory-token`. Dura diez minutos y permite una sola publicación; crea o importa la identidad antes de que venza. No confundas este token con `CLIENT_API_TOKEN` ni con el token del bot.

## 5. Levantar cliente y frontend

En una terminal, desde la raíz:

```bash
make client
```

Déjala abierta. La API local escucha en `http://127.0.0.1:8001`.

En otra terminal, también desde la raíz:

```bash
make frontend
```

Abre `http://127.0.0.1:5173`. Si la pantalla pide conexión, indica:

| Campo | Valor |
|---|---|
| Dirección del cliente | `http://127.0.0.1:8001` |
| Token | El `CLIENT_API_TOKEN` de tu `.env` |

La dirección del cliente siempre es local; la dirección de EC2 se configura como `DIRECTORY_URL`, no en este formulario. No hace falta ejecutar `make directory` ni levantar PostgreSQL en tu laptop.

## 6. Crear la identidad y conversar

1. En «Crear identidad», escribe tu **ID personal de Discord**.
2. Elige una contraseña maestra, repítela y acepta el aviso de privacidad. La aplicación exige declarar mayoría de edad.
3. Crea la identidad. El cliente genera la llave y la publica utilizando el token del paso 4. Si ya tienes una exportación, elige importar en lugar de crear otra identidad.
4. Agrega el ID personal de la otra persona. Ella debe usar su propio cliente, su bot y el mismo canal privado.
5. Ambos deben tener abierta la aplicación para completar el handshake. Compara la huella fuera de Discord, mediante QR o lectura de los dígitos, y verifica al contacto.

En la app verás el texto descifrado; en Discord aparecerán los mensajes del protocolo y el texto cifrado.

## 7. Entrar las siguientes veces y recuperar el acceso

Si la identidad ya existe, ejecuta `make client` y `make frontend` y desbloquea con la contraseña maestra y un código **nuevo** de Authenticator. No necesitas repetir OAuth2 ni obtener otro token de registro para cada desbloqueo.

La sesión local vence a los 30 minutos por defecto. Bloquearla o reiniciar el cliente exige validar de nuevo; cerrar solo la pestaña no detiene el cliente. Si EC2 no responde, no se habilita el historial. Para detener los procesos, usa `Ctrl+C` en ambas terminales.

Si pierdes el autenticador, repite el inicio de sesión del paso 4 e introduce un código de recuperación en el formulario de MFA. Vincula el nuevo autenticador y guarda los nuevos códigos: los anteriores quedan invalidados. Sin autenticador ni códigos no hay restablecimiento automático. Estos códigos no recuperan la contraseña maestra.

Antes de cancelar tu registro, exporta lo que necesites: la cancelación elimina el factor del servidor y no podrás validar el próximo desbloqueo habitual de los archivos que conserves. El MFA actual no cambia el cifrado de los archivos: una copia de la bóveda y la contraseña correcta permiten abrirla con otro programa.

## Problemas habituales

| Problema | Qué revisar |
|---|---|
| No conecta el frontend | `make client` debe seguir activo; comprueba dirección, puerto y `CLIENT_API_TOKEN` |
| Error CORS | Usa `127.0.0.1:5173`, igual que `CLIENT_ALLOWED_ORIGIN`; no alternes con `localhost` |
| Error de certificado | Host del certificado, `ca.pem` y `crl.pem` vigentes; instala la CA también en el navegador |
| No permite crear o importar | Obtén un token de registro nuevo y completa la operación antes de diez minutos |
| Rechaza el TOTP | Espera al siguiente código y comprueba la hora del celular; no reutilices uno ya aceptado. Tras cinco fallos, espera cinco minutos |
| No llegan mensajes | Cada participante usa su bot, el mismo canal y ambos clientes están desbloqueados |
| Cambiaste el aviso, Python o el frontend | Reinicia `make client` y vuelve a ejecutar `make frontend` |
