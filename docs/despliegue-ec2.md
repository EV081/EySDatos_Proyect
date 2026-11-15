# Desplegar el directorio en EC2 con PostgreSQL en Supabase

El directorio corre en una instancia EC2 en Virginia del Norte (`us-east-1`) y PostgreSQL está en el proyecto de Supabase elegido por el equipo. En EC2 se levanta solo el servicio `directory`; la base no se mueve a la instancia ni se levanta el servicio local `db`. El cliente y el frontend se ejecutan en las laptops: sigue la [guía de ejecución local](ejecucion-local.md).

Esta guía describe HTTPS directo con la CA del proyecto en el puerto 8443, según el Compose del repositorio. Sustituye `HOST_EC2`, `USUARIO_EC2` y las rutas de ejemplo por tus datos; no publiques credenciales ni la IP real en el repositorio. Si el servidor ya funciona, consulta primero la sección 7 para actualizarlo conservando los datos y las claves existentes.

## 1. Preparar la instancia

Necesitas una instancia Linux con Docker Engine, el complemento `docker compose`, Git y Python 3.12 con soporte para entornos virtuales. El usuario de administración debe poder ejecutar Docker y conectarse por SSH.

En el grupo de seguridad permite:

| Puerto | Uso | Origen |
|---|---|---|
| TCP 22 | SSH | IP de administración |
| TCP 8443 | Directorio HTTPS | IP de los participantes que usarán el servicio |

No abras puertos de entrada de PostgreSQL en EC2. El directorio necesita salida hacia el host de Supabase en el puerto de su conexión (5432 en los ejemplos), además de HTTPS a Discord. Si configuraste restricciones de red en Supabase, permite la IP de salida de EC2. Las reglas de entrada se configuran según el puerto y el origen, como describe [AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html).

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

El directorio necesita solo estas seis variables. Conserva los valores que ya funcionan en tu instancia; aquí se muestran ejemplos, no credenciales reales:

```dotenv
DATABASE_URL='postgresql://directory_app.PROJECT_REF:CONTRASENA_ROL_APP@POOLER_HOST:5432/postgres'
DISCORD_CLIENT_ID=ID_DE_LA_APLICACION_OAUTH
DISCORD_CLIENT_SECRET=SECRETO_DE_LA_APLICACION_OAUTH
DISCORD_REDIRECT_URI=https://HOST_EC2:8443/auth/callback
PSEUDONYM_KEY=CLAVE_BASE64URL_DE_32_BYTES
TOTP_ENCRYPTION_KEY=CLAVE_FERNET_EXISTENTE
```

`POSTGRES_PASSWORD=no-se-usa` puede eliminarse con el Compose actualizado: el directorio no arranca PostgreSQL local. No hacen falta `DATABASE_ADMIN_URL`, contraseñas de migración ni variables `BACKUP_*` para iniciar la API. Compose configura por separado el directorio de auditoría; el webhook es opcional.

Las migraciones del paso 4 y los respaldos del paso 8 usan variables adicionales **cuando se ejecutan esas tareas**. Puedes mantenerlas en archivos privados separados, o añadir las de respaldo al mismo `.env`; no se pasan automáticamente al contenedor del directorio.

Copia el host y la referencia reales desde **Connect** en tu proyecto Supabase. Los ejemplos usan **Session pooler**, puerto 5432, para una conexión persistente desde EC2 con IPv4. Para el rol de aplicación, el usuario es `directory_app.PROJECT_REF`; la contraseña es la del rol, no la del usuario `postgres`. La alternativa es conexión directa si EC2 tiene conectividad hacia la dirección que ofrece Supabase; conserva el formato correspondiente del panel. No uses el pooler de transacciones de 6543 para estas instrucciones. Véase la [guía de conexiones de Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

`DATABASE_URL` es la conexión del servicio con el rol de permisos mínimos. La conexión administrativa solo se configura en el paso 4 si necesitas aplicar migraciones. No utilices el usuario administrador para ejecutar la aplicación. No necesitas una clave `anon` ni `service_role`: este backend usa PostgreSQL mediante psycopg, no la API HTTP de Supabase.

Si vas a usar la verificación TLS explícita de la base, descarga el certificado raíz indicado para tu conexión en Supabase y guárdalo como `ops/certs/supabase-ca.pem` en EC2. Es distinto de `ca.pem`, que verifica el HTTPS del directorio. `sslmode=verify-full` y `sslrootcert` verifican el servidor de la base. Para exigir la verificación del certificado de la base, añade a `DATABASE_URL` los parámetros `sslmode=verify-full&sslrootcert=/app/ops/certs/supabase-ca.pem` y copia ese certificado a EC2. El montaje de `ops/certs` lo hace visible al contenedor. La ruta de una conexión ejecutada en el host es distinta: `ops/certs/supabase-ca.pem`. Estos parámetros son una configuración TLS explícita; no añaden otras credenciales al `.env` de arranque.

Sustituye todos los ejemplos por los valores de tu proyecto. Conserva las credenciales existentes. Si generas contraseñas nuevas para los roles del proyecto, `openssl rand -hex 24` evita caracteres que requieren escape en URLs. Si tu contraseña existente contiene caracteres especiales, codifica esos caracteres en la URL, como explica [Supabase](https://supabase.com/docs/guides/database/postgres/roles#special-symbols-in-passwords).

No necesitas `POSTGRES_PASSWORD` ni `db:5432` en este despliegue; esas opciones corresponden a PostgreSQL local para desarrollo y pruebas.

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

Desde la computadora responsable, copia el certificado de servidor y su llave. Ajusta la ruta remota al clon que acabas de preparar:

```bash
scp -i /ruta/clave-ec2.pem ops/certs/server.pem USUARIO_EC2@HOST_EC2:~/EySDatos_Proyect/ops/certs/server.pem
scp -i /ruta/clave-ec2.pem ops/certs/private/server.key USUARIO_EC2@HOST_EC2:~/e2ee-server.key
```

Si configuraste `sslrootcert` para Supabase, copia también su certificado público a `ops/certs/supabase-ca.pem` en EC2 y dale permisos de lectura (`chmod 644`). No copies `private/ca.key` al servidor. En EC2, permite que el UID 10001 de la imagen lea la llave montada:

```bash
chmod 644 ops/certs/server.pem
sudo install -d -o 10001 -g 10001 -m 750 ops/certs/private
sudo install -o 10001 -g 10001 -m 600 ~/e2ee-server.key ops/certs/private/server.key
rm ~/e2ee-server.key
```

Entrega `ca.pem` y `crl.pem` vigentes a las laptops por un canal confiable. El navegador también debe confiar en esa CA para abrir el login OAuth. Renueva la CRL antes de los 30 días; `pki issue` regenera certificado y CRL. El certificado de servidor vence a los 90 días. Tras renovar, copia los archivos actualizados y reinicia el directorio.

## 4. Aplicar las migraciones en Supabase

Usa el proyecto y los datos que ya tienes en Supabase. No crees otro PostgreSQL en EC2. Antes de aplicar cambios al esquema, conserva el respaldo correspondiente del proyecto y la clave de cifrado TOTP vigente.

Si el esquema ya está actualizado y solo vas a recrear el contenedor, puedes pasar al paso 5. Cuando haya migraciones nuevas, prepara un archivo privado `.env.migraciones` en el equipo que las ejecutará:

```dotenv
DATABASE_ADMIN_URL='postgresql://postgres.PROJECT_REF:CONTRASENA_ADMIN@POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=ops/certs/supabase-ca.pem'
DIRECTORY_APP_PASSWORD=CONTRASENA_ROL_APP_EXISTENTE
# Solo para crear o habilitar el rol de copias:
DIRECTORY_BACKUP_PASSWORD=CONTRASENA_ROL_RESPALDO
```

La URL administrativa debe apuntar al proyecto correcto de Supabase; este archivo no es necesario para que la API funcione. Con el certificado disponible:

```bash
chmod 600 .env.migraciones
set -a
. ./.env.migraciones
set +a
.venv/bin/python -m directory.migrations.apply
```

El script se conecta con `DATABASE_ADMIN_URL`, prepara los roles `directory_owner`, `directory_app` y `directory_backup`, y aplica las migraciones al esquema `directory`, incluidas `003_mfa.sql` y `004_session_mfa.sql`. Supabase conserva los datos; no se usa el volumen local `directory-db`. Mantén las mismas contraseñas de los roles al actualizar.

Si aparece `permission denied for database postgres` al crear el esquema o usar el rol propietario, abre **SQL Editor** de Supabase como `postgres`, comprueba que el rol `directory_owner` ya existe y ejecuta:

```sql
GRANT directory_owner TO postgres;
GRANT CREATE ON DATABASE postgres TO directory_owner;
```

Después repite la migración. El permiso `CREATE` se concede al rol propietario de migraciones, no a `directory_app`. Supabase documenta este caso en su [guía de permisos de migración](https://supabase.com/kb/troubleshooting/resolving-permission-denied-for-database-postgres-during-migrations-78f33a). Si las migraciones ya están aplicadas, no vuelvas a crear tablas ni a vincular factores manualmente: conserva el esquema y las claves existentes.

## 5. Levantar el directorio

```bash
docker compose --profile deploy up -d --build directory
docker compose --profile deploy ps
docker compose --profile deploy logs --tail=50 directory
```

El servicio escucha por HTTPS en 8443 y se conecta a la URL de Supabase de `DATABASE_URL`. Los registros se guardan en `directory-logs`. Con el perfil `deploy` se arranca solo el directorio; el servicio `db` queda reservado al perfil local. Confirma que `docker compose --profile deploy ps` no muestre una base local iniciada por este despliegue.

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

Antes de actualizar, conserva el respaldo de la base de Supabase y los secretos vigentes, especialmente `TOTP_ENCRYPTION_KEY`. Con los cambios ya publicados en la rama que usa el servidor, ejecuta en EC2:

```bash
git pull --ff-only
docker compose --profile deploy up -d --build directory
```

Si la actualización añade migraciones, instala las dependencias de `directory/requirements.txt` en el entorno del host y aplica primero el paso 4 con `.env.migraciones`. No cargues variables administrativas en el `.env` del servicio por el simple hecho de actualizar código.

Repite la comprobación HTTPS y el desbloqueo con Authenticator. No vuelvas a vincular el celular ni regeneres claves solo por actualizar código. Una actualización del cliente o del frontend se aplica también en cada laptop reiniciando `make client` y volviendo a ejecutar `make frontend`; actualizar EC2 por sí solo no cambia la interfaz local.

## 8. Activar el respaldo diario de Supabase en S3

**Estado:** el volcado cifrado y la restauración están implementados y tienen un [ensayo local registrado](../ops/reports/f4-simulacro.txt). La integración S3 del repositorio tiene pruebas simuladas; el bucket y la tarea de EC2 deben crearse y comprobarse en la cuenta AWS Academy. Agregar solo una variable no programa un respaldo.

### 8.1 Crear el bucket y comprobar el rol

En la consola de S3 de tu cuenta de AWS Academy:

1. Crea un bucket de propósito general en `us-east-1`, con nombre único (por ejemplo, uno propio que empiece por `eysd-backups-`).
2. Conserva activados los cuatro bloqueos de acceso público y desactivadas las ACL.
3. Deja el versionado desactivado. El trabajo de este proyecto elimina las copias antiguas; no debe dejar versiones ocultas al borrar.
4. Usa cifrado de S3 con claves administradas por S3 (SSE-S3). Además, cada copia ya se cifra con AES-256-GCM antes de salir de EC2.

El bloqueo público y los permisos se comprueban antes de subir datos ([referencia de AWS](https://docs.aws.amazon.com/cli/latest/reference/s3api/get-public-access-block.html)).

En EC2 necesitas AWS CLI v2 reciente y un perfil de instancia permitido por el laboratorio con acceso al bucket. Comprueba desde EC2:

```bash
aws --version
aws sts get-caller-identity
```

Los permisos necesarios son `s3:GetBucketPublicAccessBlock`, `s3:GetBucketVersioning` y `s3:ListBucket` sobre ese bucket; `s3:PutObject`, `s3:GetObject` y `s3:DeleteObject` sobre su prefijo `directory/`. Usa el rol de la instancia que permita AWS Academy, sin guardar `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY` en el `.env`. Que puedas crear un bucket desde la consola no demuestra por sí solo que el rol de EC2 pueda escribir en él.

### 8.2 Configurar la tarea

Prepara AWS CLI y `pg_dump`/`pg_restore` de una versión compatible con PostgreSQL de Supabase **en EC2**, donde se ejecutará el trabajo. La imagen del directorio no contiene las herramientas de operaciones ni programa esta tarea. Si hasta ahora solo usabas el contenedor, prepara también el entorno Python del host, reutilizándolo si ya existe:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r directory/requirements.txt
pg_dump --version
pg_restore --version
```

Instala AWS CLI v2 desde la [guía oficial para Linux](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) si `aws --version` no funciona. Las herramientas de PostgreSQL deben corresponder a una versión compatible con la del proyecto Supabase.

Habilita el rol `directory_backup` con su contraseña de lectura mediante el paso 4 o con la administración del proyecto. Agrega estas variables al `.env` de EC2, o guárdalas en `.env.backup` si prefieres separarlas:

```dotenv
BACKUP_DATABASE_URL='postgresql://directory_backup.PROJECT_REF:CONTRASENA_ROL_RESPALDO@POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=/RUTA/AL/REPO/ops/certs/supabase-ca.pem'
BACKUP_KEY=CLAVE_BASE64URL_DE_32_BYTES
BACKUP_DIR=/var/tmp/eysd-backups
BACKUP_S3_BUCKET=NOMBRE_DEL_BUCKET_NUEVO
BACKUP_S3_PREFIX=directory
AWS_REGION=us-east-1
```

`BACKUP_DATABASE_URL` usa el rol de lectura, no el administrador. Genera `BACKUP_KEY` una sola vez con `openssl rand -base64 32 | tr '+/' '-_'` y guarda una copia protegida fuera de EC2 y del bucket. No uses `TOTP_ENCRYPTION_KEY` como `BACKUP_KEY`: tienen funciones diferentes y se respaldan por separado. Ajusta la ruta absoluta al certificado y protege el archivo privado con permisos 600.

`BACKUP_DIR` es un área de archivos **ya cifrados** mientras se suben a S3; no es el destino remoto. El código comprueba bloqueo público, ausencia de versionado, tamaño y SHA-256 del objeto subido mediante [PutObject](https://docs.aws.amazon.com/cli/latest/reference/s3api/put-object.html) y [HeadObject](https://docs.aws.amazon.com/cli/latest/reference/s3api/head-object.html). Solo después de verificar la copia nueva elimina los archivos del proyecto de más de 30 días bajo ese prefijo; no toca otros objetos. Una regla de ciclo de vida de S3 puede complementar la limpieza, pero su [eliminación es asíncrona](https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html) y no sustituye la comprobación del trabajo.

### 8.3 Ejecutar y comprobar la primera copia

Desde la raíz del clon en EC2:

```bash
make backup-remote
```

Si elegiste un archivo separado:

```bash
make backup-remote ENV_FILE=.env.backup
```

Debe terminar con código 0 y mostrar `copia remota verificada (SHA-256)`. Un error de permisos o una subida incompleta hace fallar la tarea y conserva las copias anteriores. Revisa en S3 que aparezca `directory/directory-FECHA.dump.enc`. El trabajo no guarda un volcado legible en el bucket.

### 8.4 Programarlo diariamente

En EC2, con el usuario que puede ejecutar AWS CLI y leer la configuración:

```bash
crontab -e
```

Agrega esta línea, reemplazando la ruta absoluta del clon. Usa la variante que corresponda a tu archivo de configuración:

```cron
0 3 * * * cd /RUTA/AL/REPO && /usr/bin/make backup-remote >> /var/tmp/eysd-backup.log 2>&1
```

```cron
0 3 * * * cd /RUTA/AL/REPO && /usr/bin/make backup-remote ENV_FILE=.env.backup >> /var/tmp/eysd-backup.log 2>&1
```

Es a las 03:00 según la zona horaria del servidor, no necesariamente Lima. Comprueba `crontab -l`, que el servicio cron esté activo, y que se genere una copia nueva tras la siguiente ejecución. Si cron no encuentra `aws` o `pg_dump`, configura su `PATH` con las rutas de instalación reales. Revisa el resultado y los errores; una EC2 apagada o un rol sin sesión válida no ejecutará la copia diaria. Esta línea programa F4; la purga y auditoría de F5 pertenecen a `ops.scheduled` y requieren configurar también el acceso a los registros del contenedor.

### 8.5 Comprobar la recuperación

La verificación SHA-256 prueba la transferencia, no reemplaza una restauración. Descarga una copia cifrada desde S3 y ensaya recuperarla en un PostgreSQL **aislado** con los roles del proyecto y una clave `BACKUP_KEY` válida. No apuntes `make restore` a la base real para hacer un ensayo: reemplaza su esquema.

`make verify-backup` necesita crear y borrar una base temporal; no se debe ejecutar contra Supabase sin un entorno y permisos adecuados. Conserva evidencia del ensayo con conteos y tiempos, sin IDs, códigos ni secretos. Para recuperar el funcionamiento del MFA también necesitas la `TOTP_ENCRYPTION_KEY` original, custodiada por separado del bucket.

Antes de marcar F4 como desplegada deben existir el bucket privado, una copia remota verificada, la programación diaria y una restauración ensayada. Los respaldos administrados por Supabase, si están configurados, son un mecanismo diferente del respaldo cifrado de este proyecto.
