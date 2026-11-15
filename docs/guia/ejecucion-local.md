# Ejecutar la aplicación en tu computadora

Cada persona ejecuta su cliente y su frontend en su computadora. El directorio está en EC2, Virginia del Norte (`us-east-1`), y PostgreSQL está en Supabase. Para preparar ese servidor está la [guía de EC2](despliegue-ec2.md).

Esta guía parte de una computadora sin el proyecto instalado. Necesitas un directorio en EC2 ya preparado según la guía de EC2. Los comandos usan Bash en Ubuntu 22.04/24.04 o WSL Ubuntu; en macOS instala Git, Make y OpenSSL antes de continuar. En Windows usa WSL para seguir los mismos comandos. Instala Microsoft Authenticator u otra app compatible con TOTP en tu celular.

## 1. Instalar herramientas y descargar el proyecto

En Ubuntu o WSL Ubuntu:

```bash
sudo apt update
sudo apt install -y git make curl ca-certificates openssl xz-utils
```

Instala una versión con soporte a largo plazo (LTS) de Node.js desde la [página oficial](https://nodejs.org/en/download), seleccionando tu sistema y arquitectura, y sigue las instrucciones de instalación que muestra. Incluye npm. El frontend necesita Node 20.9 o posterior; elige una LTS vigente. Abre otra terminal después de instalarlo y comprueba:

```bash
git --version
make --version
node --version
npm --version
```

Instala [uv](https://docs.astral.sh/uv/getting-started/installation/) y Python 3.12. Esto permite usar Ubuntu 22.04 sin cambiar su Python del sistema:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
"$HOME/.local/bin/uv" python install 3.12
```

Descarga el repositorio y crea el entorno con Python 3.12:

```bash
git clone https://github.com/EV081/EySDatos_Proyect.git
cd EySDatos_Proyect
"$HOME/.local/bin/uv" venv --python 3.12 --seed .venv
"$HOME/.local/bin/uv" pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python --version
```

Desde este punto, ejecuta todos los comandos desde la raíz de `EySDatos_Proyect`. `make frontend` instalará y compilará las dependencias de la interfaz.

## 2. Preparar Discord y los certificados

1. Crea o usa un servidor de Discord y un canal de texto privado para los participantes, por ejemplo `#e2ee-relay`.
2. En [Discord Developer Portal](https://discord.com/developers/applications), crea una aplicación para tu bot. En **Bot**, genera su token y activa **Message Content Intent**. Cada participante usa un bot distinto.
3. En **OAuth2 > URL Generator**, selecciona el alcance `bot` y los permisos **View Channels**, **Send Messages** y **Read Message History**. Abre la URL e invita tu bot al servidor. En los permisos del canal privado, da acceso a los dos bots.
4. Activa el modo desarrollador en Discord, copia el ID del canal y tu ID personal con el menú contextual. El ID personal es distinto del ID del bot: usarás el personal al crear tu identidad.

El token del bot se obtiene de tu aplicación; la aplicación OAuth del directorio se configura en el servidor según la guía de EC2.

Pide al responsable del directorio estos datos:

- URL HTTPS del directorio desplegado, incluido su puerto, normalmente `https://HOST_EC2:8443`.
- `ca.pem` y `crl.pem` vigentes. Colócalos en `ops/certs/`.

Importa `ca.pem` como autoridad de confianza para sitios web en el navegador que usarás para iniciar sesión con Discord. El cliente Python revisa los certificados con los archivos del `.env`. El navegador necesita que también instales la CA en su propia configuración. El certificado del servidor debe incluir el nombre o la IP de la URL. No necesitas la llave privada de la CA ni la del servidor.

## 3. Configurar tu `.env`

Desde la carpeta principal del repositorio, copia la [plantilla para laptop](../../.env.example.local) a `.env` y ábrela con tu editor:

```bash
cp .env.example.local .env
chmod 600 .env
nano .env
```

Completa estos valores:

| Variable | Qué poner |
|---|---|
| `DIRECTORY_URL` | URL HTTPS del directorio, por ejemplo `https://HOST_EC2:8443` |
| `DISCORD_TOKEN` | Token de tu bot |
| `DISCORD_CHANNEL_ID` | ID del canal privado compartido |
| `CLIENT_API_TOKEN` | Una cadena aleatoria generada con `openssl rand -hex 32` |

La plantilla incluye las rutas de los certificados públicos y del token de registro, la carpeta de datos, el vencimiento de 1800 segundos y el origen del frontend. Puedes conservar esos valores si sigues esta guía. Cada participante tiene su propio `.env`.

No necesitas credenciales de PostgreSQL, `DISCORD_CLIENT_SECRET` ni `TOTP_ENCRYPTION_KEY` en la laptop para conectarte al directorio en EC2. No definas `DIRECTORY_AUTH_TOKEN` si usarás el archivo: esa variable tiene prioridad sobre el token guardado.

## 4. Iniciar sesión con Discord y vincular Authenticator

Haz este paso antes de crear o importar tu identidad. También sirve para obtener otro token cuando necesites cambiar tu registro. Carga el `.env` en esta terminal; `make client` carga su propio entorno y no lo configura para los demás comandos:

```bash
set -a
. ./.env
set +a
.venv/bin/python -m directory.client_lib.login
```

1. Se abre el navegador en `/auth/login`. Si no se abre, visita la URL que imprime el comando.
2. Autoriza tu cuenta personal de Discord.
3. La primera vez, en Authenticator elige agregar otra cuenta y escanea el QR. Si ya está vinculado, escribe un código nuevo de seis dígitos.
4. Guarda los diez códigos de recuperación en un lugar seguro fuera de la computadora; solo se muestran una vez al vincular el factor.
5. Copia el **token de registro** de la página y pégalo una sola vez en la terminal. Al pegarlo no se muestran caracteres. Presiona Enter.

El comando guarda el token en `data/directory-token`. Dura diez minutos y permite una sola publicación; crea o importa la identidad antes de que venza. Este token es distinto de `CLIENT_API_TOKEN` y del token del bot.

## 5. Levantar cliente y frontend

En una terminal, desde la raíz:

```bash
make client
```

Déjala abierta. El cliente recibe las peticiones del frontend en `http://127.0.0.1:8001`.

En otra terminal, también desde la raíz:

```bash
make frontend
```

Abre `http://127.0.0.1:5173`. Si la pantalla pide conexión, indica:

| Campo | Valor |
|---|---|
| Dirección del cliente | `http://127.0.0.1:8001` |
| Token | El `CLIENT_API_TOKEN` de tu `.env` |

La dirección del cliente siempre apunta a tu computadora; la dirección de EC2 se configura como `DIRECTORY_URL`, no en este formulario. No hace falta ejecutar `make directory` ni levantar PostgreSQL en tu laptop.

## 6. Crear la identidad y conversar

1. En «Crear identidad», escribe tu **ID personal de Discord**.
2. Elige una contraseña maestra, repítela y acepta el aviso de privacidad. La aplicación exige declarar mayoría de edad.
3. Crea la identidad. El cliente genera la llave y la publica utilizando el token del paso 4. Si ya tienes una exportación, elige importar en lugar de crear otra identidad.
4. Agrega el ID personal de la otra persona. Ella debe usar su propio cliente, su bot y el mismo canal privado.
5. Ambos deben tener abierta la aplicación para completar el handshake. Compara la huella fuera de Discord, mediante QR o lectura de los dígitos, y verifica al contacto.

En la app verás el texto descifrado; en Discord aparecerán los mensajes del protocolo y el texto cifrado.

## 7. Entrar las siguientes veces y recuperar el acceso

Si la identidad ya existe, ejecuta `make client` y `make frontend` y desbloquea con la contraseña maestra y un código **nuevo** de Authenticator. No necesitas repetir OAuth2 ni obtener otro token de registro para cada desbloqueo.

La aplicación se bloquea a los 30 minutos por defecto. Bloquearla o reiniciar el cliente exige validar de nuevo; cerrar solo la pestaña no detiene el cliente. Si EC2 no responde, no se habilita el historial. Para detener los procesos, usa `Ctrl+C` en ambas terminales.

Si pierdes el autenticador, repite el inicio de sesión del paso 4 e introduce un código de recuperación en el formulario del segundo factor. Vincula el nuevo autenticador y guarda los nuevos códigos: los anteriores quedan invalidados. Si pierdes tanto el autenticador como los códigos, la app no puede recuperar automáticamente ese acceso. Estos códigos no recuperan la contraseña maestra.

Antes de cancelar tu registro, exporta lo que necesites: la cancelación elimina el factor del servidor y no podrás validar el próximo desbloqueo habitual de los archivos que conserves. El segundo factor no cambia el cifrado de los archivos: una copia de la bóveda y la contraseña correcta permiten abrirla con otro programa.

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
