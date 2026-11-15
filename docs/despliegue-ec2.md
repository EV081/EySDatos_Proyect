# Desplegar el directorio y PostgreSQL en EC2

El proyecto usa una instancia en Virginia del Norte (`us-east-1`). PostgreSQL corre en el servicio `db` de Docker Compose y el directorio en el servicio `directory`, dentro de esa misma instancia. El cliente y el frontend se ejecutan en las laptops: sigue la [guía de ejecución local](ejecucion-local.md).

Esta guía describe HTTPS directo con la CA del proyecto en el puerto 8443, según el Compose del repositorio. Sustituye `HOST_EC2`, `USUARIO_EC2` y las rutas de ejemplo por tus datos; no publiques credenciales ni la IP real en el repositorio. Si el servidor ya funciona, consulta primero la sección 7 para actualizarlo conservando los datos y las claves existentes.

## 1. Preparar la instancia

Necesitas una instancia Linux con Docker Engine, el complemento `docker compose`, Git y Python 3.12 con soporte para entornos virtuales. El usuario de administración debe poder ejecutar Docker y conectarse por SSH.

En el grupo de seguridad permite:

| Puerto | Uso | Origen |
|---|---|---|
| TCP 22 | SSH | IP de administración |
| TCP 8443 | Directorio HTTPS | IP de los participantes que usarán el servicio |

El Compose publica PostgreSQL solo en `127.0.0.1:55432` del servidor. No abras 5432 ni 55432 hacia Internet. Las reglas de entrada se configuran según el puerto y el origen, como describe [AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html).

Conéctate desde tu computadora:

```bash
ssh -i /ruta/clave-ec2.pem USUARIO_EC2@HOST_EC2
```

En EC2, prepara el repositorio y el entorno para aplicar las migraciones:

```bash
git clone https://github.com/EV081/EySDatos_Proyect.git
cd EySDatos_Proyect
python3 -m venv .venv
.venv/bin/python -m pip install -r directory/requirements.txt
```

Si ya existe el clon, usa ese directorio en los pasos siguientes.

## 2. Configurar el `.env` de EC2

Crea `.env` en la raíz del repositorio del servidor. Es distinto del `.env` de las laptops:

```dotenv
POSTGRES_PASSWORD=CONTRASENA_POSTGRES
DIRECTORY_APP_PASSWORD=CONTRASENA_ROL_APP
DIRECTORY_BACKUP_PASSWORD=CONTRASENA_ROL_RESPALDO

DATABASE_ADMIN_URL=postgresql://postgres:CONTRASENA_POSTGRES@127.0.0.1:55432/directory
DATABASE_URL=postgresql://directory_app:CONTRASENA_ROL_APP@db:5432/directory

DISCORD_CLIENT_ID=ID_DE_LA_APLICACION_OAUTH
DISCORD_CLIENT_SECRET=SECRETO_DE_LA_APLICACION_OAUTH
DISCORD_REDIRECT_URI=https://HOST_EC2:8443/auth/callback

PSEUDONYM_KEY=CLAVE_BASE64URL_DE_32_BYTES
TOTP_ENCRYPTION_KEY=CLAVE_FERNET_EXISTENTE_O_NUEVA
AUDIT_LOG_DIR=logs
ALERT_WEBHOOK_URL=
```

Sustituye todos los ejemplos antes de continuar. Para contraseñas nuevas puedes generar valores hexadecimales con `openssl rand -hex 24`; así no necesitas escapar caracteres especiales en las URLs. Usa valores diferentes para los tres roles. `DATABASE_URL` utiliza `db:5432` porque la consume el contenedor del directorio; `DATABASE_ADMIN_URL` usa `127.0.0.1:55432` porque las migraciones se ejecutan desde el host. Es la distinción entre puerto interno y publicado de [Docker Compose](https://docs.docker.com/compose/how-tos/networking/).

Solo en una instalación nueva, genera `PSEUDONYM_KEY` y `TOTP_ENCRYPTION_KEY` ejecutando dos veces este comando y asignando un resultado distinto a cada variable:

```bash
openssl rand -base64 32 | tr '+/' '-_'
```

**Si ya tienes Authenticator vinculado, conserva `TOTP_ENCRYPTION_KEY`.** Generar otra clave no recifra los secretos guardados y dejaría de poder validarlos. Conserva su respaldo protegido fuera de la instancia y separado del volcado de PostgreSQL. No necesita una API key de Microsoft.

```bash
chmod 600 .env
```

En Discord Developer Portal, configura para la aplicación OAuth la misma URI de redirección que pusiste en `DISCORD_REDIRECT_URI`, incluido HTTPS, host, puerto y `/auth/callback`. La instancia necesita salida HTTPS a Discord y su reloj debe estar sincronizado para verificar TOTP.

## 3. Preparar los certificados desde la computadora responsable

La llave privada de la CA se conserva en la computadora responsable. En esa computadora, desde la raíz del proyecto, configura el host público y la contraseña de la CA:

```bash
export DIRECTORY_EXTRA_HOSTS=HOST_EC2
read -r -s -p 'Contraseña de la CA (mínimo 12 caracteres): ' CA_KEY_PASSWORD
echo
export CA_KEY_PASSWORD
```

Si es una CA nueva, ejecuta:

```bash
.venv/bin/python -m ops.certs.pki init
```

Si la CA ya existe y necesitas emitir o renovar el certificado para ese host, usa en cambio:

```bash
.venv/bin/python -m ops.certs.pki issue
```

Crea en EC2 la carpeta de destino desde la raíz del clon:

```bash
mkdir -p ops/certs/private
```

Desde la computadora responsable, copia solo el certificado de servidor y su llave. Ajusta la ruta remota al clon que acabas de preparar:

```bash
scp -i /ruta/clave-ec2.pem ops/certs/server.pem USUARIO_EC2@HOST_EC2:~/EySDatos_Proyect/ops/certs/server.pem
scp -i /ruta/clave-ec2.pem ops/certs/private/server.key USUARIO_EC2@HOST_EC2:~/e2ee-server.key
```

No copies `private/ca.key` al servidor. En EC2, permite que el UID 10001 de la imagen lea la llave montada:

```bash
chmod 644 ops/certs/server.pem
sudo install -d -o 10001 -g 10001 -m 750 ops/certs/private
sudo install -o 10001 -g 10001 -m 600 ~/e2ee-server.key ops/certs/private/server.key
rm ~/e2ee-server.key
```

Entrega `ca.pem` y `crl.pem` vigentes a las laptops por un canal confiable. El navegador también debe confiar en esa CA para abrir el login OAuth. Renueva la CRL antes de los 30 días; `pki issue` regenera certificado y CRL. El certificado de servidor vence a los 90 días. Tras renovar, copia los archivos actualizados y reinicia el directorio.

## 4. Levantar PostgreSQL y aplicar el esquema

En EC2, desde la raíz del clon y con el `.env` completo:

```bash
docker compose up -d db
docker compose ps db
```

Espera a que `db` figure como `healthy`. Carga el entorno y ejecuta las migraciones:

```bash
set -a
. ./.env
set +a
.venv/bin/python -m directory.migrations.apply
```

El comando crea los roles, el esquema y las tablas, incluidas `003_mfa.sql` y `004_session_mfa.sql`. Se puede volver a ejecutar con las mismas credenciales para aplicar el esquema de esta versión. Los datos de PostgreSQL se guardan en el volumen `directory-db`.

En una base existente, conserva las contraseñas vigentes. Cambiar `POSTGRES_PASSWORD` en el `.env` no cambia la contraseña dentro de un volumen ya inicializado. No uses `docker compose down -v` para actualizar: elimina los volúmenes y los datos.

## 5. Levantar el directorio

```bash
docker compose --profile deploy up -d --build directory
docker compose --profile deploy ps
docker compose --profile deploy logs --tail=50 directory
```

El servicio escucha por HTTPS en 8443 y se conecta a `db:5432`. Los registros se guardan en `directory-logs`. El Compose no declara dependencia de arranque entre ambos servicios; por eso primero se espera a que PostgreSQL esté listo.

## 6. Comprobar desde una laptop

Con la URL real configurada en el `.env` local y `ca.pem` y `crl.pem` vigentes:

```bash
set -a
. ./.env
set +a
curl --cacert "$DIRECTORY_CA_FILE" --crlfile "$DIRECTORY_CRL_FILE" --tlsv1.3 --tls-max 1.3 --include "$DIRECTORY_URL/health"
```

La respuesta esperada es `204 No Content`. Después sigue la [guía local](ejecucion-local.md#4-iniciar-sesión-con-discord-y-vincular-authenticator): completa Discord y Authenticator, guarda el token y crea o importa la identidad. Bloquea y desbloquea con un código nuevo; un código ya usado debe rechazarse.

## 7. Actualizar un despliegue existente

Antes de actualizar, conserva una copia de la base y los secretos vigentes, especialmente `TOTP_ENCRYPTION_KEY`. Con los cambios ya publicados en la rama que usa el servidor, ejecuta en EC2:

```bash
git pull --ff-only
.venv/bin/python -m pip install -r directory/requirements.txt
set -a
. ./.env
set +a
.venv/bin/python -m directory.migrations.apply
docker compose --profile deploy up -d --build directory
```

Repite la comprobación HTTPS y el desbloqueo con Authenticator. No vuelvas a vincular el celular ni regeneres claves solo por actualizar código. Una actualización del cliente o del frontend se aplica también en cada laptop reiniciando `make client` y volviendo a ejecutar `make frontend`; actualizar EC2 por sí solo no cambia la interfaz local.

## 8. Respaldo y recuperación

Para operar las copias desde un equipo que ejecute las herramientas de PostgreSQL 17, configura `BACKUP_DATABASE_URL`, `BACKUP_KEY` y `BACKUP_DIR` como indica `.env.example`. Si se ejecutan desde EC2, la URL usa `127.0.0.1:55432` y el destino debe ser externo a la instancia. La tarea disponible es `make daily`; `make verify-backup` comprueba la restauración.

Una carpeta fuera del repositorio pero dentro del mismo disco de EC2 no es un respaldo externo. El destino efectivo de las copias todavía debe quedar documentado. La restauración requiere tanto el volcado como la misma `TOTP_ENCRYPTION_KEY`; conserva también la clave de los respaldos por separado.
