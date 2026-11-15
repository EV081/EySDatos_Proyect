# Desplegar desde cero: EC2, Supabase y respaldo en S3

Aquí empezamos con una cuenta de AWS Academy y el laboratorio iniciado. Primero creamos EC2 y Supabase; después instalamos el directorio y las copias de seguridad. El directorio funciona en EC2, Virginia del Norte (`us-east-1`); PostgreSQL se aloja en Supabase y las copias cifradas en S3. El cliente y el frontend corren en las laptops según la [guía local](ejecucion-local.md).

Los comandos del servidor usan Ubuntu 22.04 o 24.04 **x86_64**, usuario `ubuntu` y clon en `/home/ubuntu/EySDatos_Proyect`. Sustituye `HOST_EC2`, referencias, contraseñas y nombres de bucket por los valores propios. En tu computadora necesitas Git, OpenSSH y el entorno Python del paso 1 de la guía local para emitir los certificados. Sigue los pasos en orden para una instalación nueva.

## 1. Crear EC2 e instalar las herramientas

En la consola AWS, selecciona `us-east-1` y crea una instancia con Ubuntu Server 22.04/24.04, arquitectura x86_64, almacenamiento suficiente para Docker y acceso a Internet. Descarga la llave SSH `.pem`. Asocia a EC2 un rol permitido por AWS Academy para que pueda usar el bucket de respaldos; si el laboratorio ofrece `LabInstanceProfile`, revisa sus permisos en el paso 8. Conviene mantener la misma dirección pública: si cambia, también habrá que cambiar el certificado, la dirección de retorno de Discord y la configuración de cada laptop.

En el grupo de seguridad configura:

| Puerto | Uso | Origen |
|---|---|---|
| TCP 22 | SSH | IP de administración |
| TCP 8443 | Directorio HTTPS | IP de los participantes |

EC2 debe poder conectarse a Supabase por el puerto 5432 y usar HTTPS para Discord, S3 y las descargas de instalación. No abras PostgreSQL como puerto de entrada en EC2. Si Supabase tiene restricciones de red, autoriza la IP de salida de EC2. Consulta las [reglas de grupos de seguridad de AWS](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules-reference.html).

Desde tu computadora, protege la llave y conéctate:

```bash
chmod 400 /ruta/clave-ec2.pem
ssh -i /ruta/clave-ec2.pem ubuntu@HOST_EC2
```

En EC2 instala las herramientas básicas:

```bash
sudo apt update
sudo apt install -y git make curl ca-certificates openssl unzip cron postgresql-common
```

Instala Docker Engine y Compose desde el [repositorio oficial de Docker](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$(dpkg --print-architecture)" "$VERSION_CODENAME" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
exit
```

Vuelve a entrar por SSH para aplicar el grupo Docker. Los comandos siguientes se ejecutan en EC2:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Instala las herramientas cliente PostgreSQL 17 desde [PGDG](https://www.postgresql.org/download/linux/ubuntu/), compatibles con el despliegue probado en este proyecto. En Supabase comprueba la versión de PostgreSQL: si usas una versión mayor, instala un cliente compatible antes de generar copias.

```bash
sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh
sudo apt update
sudo apt install -y postgresql-client-17
pg_dump --version
pg_restore --version
```

Esto instala clientes de PostgreSQL; la base de producción seguirá en Supabase. Prepara Python 3.12 con [uv](https://docs.astral.sh/uv/getting-started/installation/), descarga el proyecto e instala dependencias:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
"$HOME/.local/bin/uv" python install 3.12
git clone https://github.com/EV081/EySDatos_Proyect.git
cd EySDatos_Proyect
"$HOME/.local/bin/uv" venv --python 3.12 --seed .venv
"$HOME/.local/bin/uv" pip install --python .venv/bin/python -r directory/requirements.txt
mkdir -p ops/certs/private
```

Desde este punto trabaja en `/home/ubuntu/EySDatos_Proyect`, salvo cuando se indique expresamente la computadora responsable.

## 2. Crear Supabase, la aplicación OAuth y el `.env`

En Supabase crea una organización/proyecto, elige y registra su región y guarda su contraseña administrativa. La región de Supabase se registra por separado de EC2. En **Connect**, copia el host y referencia del **Session pooler**, puerto 5432: permite conexión desde EC2 con IPv4. El administrador usa `postgres.PROJECT_REF`; nuestros roles usarán `directory_app.PROJECT_REF` y `directory_backup.PROJECT_REF`. No uses el pooler de transacciones de 6543 para esta guía. Consulta las [conexiones de Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

En los ajustes SSL de la base, descarga el certificado raíz de Supabase. Cópialo desde tu computadora a EC2:

```bash
scp -i /ruta/clave-ec2.pem /ruta/certificado-descargado.crt ubuntu@HOST_EC2:~/EySDatos_Proyect/ops/certs/supabase-ca.pem
```

Este certificado público verifica PostgreSQL y es distinto de la CA HTTPS del directorio. En EC2:

```bash
chmod 644 ops/certs/supabase-ca.pem
openssl rand -hex 24
openssl rand -hex 24
openssl rand -base64 32 | tr '+/' '-_'
openssl rand -base64 32 | tr '+/' '-_'
```

Guarda los cuatro resultados por separado: contraseña de `directory_app`, contraseña de `directory_backup`, `PSEUDONYM_KEY` y `TOTP_ENCRYPTION_KEY`, respectivamente. Guarda una copia protegida de las claves fuera de EC2; no se regeneran en cada arranque.

En [Discord Developer Portal](https://discord.com/developers/applications), crea la aplicación OAuth del directorio. Copia el **Application ID** y el **Client Secret**; en **OAuth2 > Redirects** registra exactamente `https://HOST_EC2:8443/auth/callback`. Cada participante creará su propio bot según la guía local. El directorio usa OAuth con alcance `identify`; Authenticator usa TOTP y no requiere una API key de Microsoft.

En EC2 crea `.env` con `nano .env` y completa las seis variables de la API:

```dotenv
DATABASE_URL='postgresql://directory_app.PROJECT_REF:CONTRASENA_ROL_APP@POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=/app/ops/certs/supabase-ca.pem'
DISCORD_CLIENT_ID=ID_DE_LA_APLICACION_OAUTH
DISCORD_CLIENT_SECRET=SECRETO_DE_LA_APLICACION_OAUTH
DISCORD_REDIRECT_URI=https://HOST_EC2:8443/auth/callback
PSEUDONYM_KEY=CLAVE_BASE64URL_DE_32_BYTES
TOTP_ENCRYPTION_KEY=OTRA_CLAVE_BASE64URL_DE_32_BYTES
```

La aplicación usa el usuario de base de datos con los permisos necesarios para la app, que se creará en el paso 4; no la conexión administrativa. El certificado se verá dentro del contenedor en `/app/ops/certs/`. No necesitas `POSTGRES_PASSWORD`, claves `anon` ni `service_role` para esta arquitectura. Más adelante agregamos las variables para preparar las tablas y hacer las copias.

```bash
chmod 600 .env
```

Las contraseñas hexadecimales generadas evitan escapes en las URLs. Si usas otras contraseñas con símbolos, [codifícalos en la URL](https://supabase.com/docs/guides/database/postgres/roles#special-symbols-in-passwords). El reloj de EC2 y el celular deben estar sincronizados para validar TOTP.

## 3. Emitir y copiar los certificados HTTPS

En la **computadora responsable**, prepara el clon y `.venv` siguiendo el paso 1 de la guía local. Desde su raíz ejecuta:

```bash
export DIRECTORY_EXTRA_HOSTS=HOST_EC2
read -r -s -p 'Contraseña nueva de la CA (mínimo 12 caracteres): ' CA_KEY_PASSWORD
echo
export CA_KEY_PASSWORD
.venv/bin/python -m ops.certs.pki init
scp -i /ruta/clave-ec2.pem ops/certs/server.pem ubuntu@HOST_EC2:~/EySDatos_Proyect/ops/certs/server.pem
scp -i /ruta/clave-ec2.pem ops/certs/private/server.key ubuntu@HOST_EC2:~/e2ee-server.key
```

`init` crea la CA, el certificado de servidor y la CRL. La llave privada `ops/certs/private/ca.key` permanece cifrada en la computadora responsable: no se copia a EC2. En **EC2**, permite que el UID 10001 del servicio lea su llave:

```bash
chmod 644 ops/certs/server.pem
sudo install -d -o 10001 -g 10001 -m 750 ops/certs/private
sudo install -o 10001 -g 10001 -m 600 ~/e2ee-server.key ops/certs/private/server.key
rm ~/e2ee-server.key
```

Entrega `ops/certs/ca.pem` y `ops/certs/crl.pem` a los participantes por un canal confiable. Importan la CA en su navegador y colocan ambos archivos en su clon local. El nombre o IP usado en `HOST_EC2` debe coincidir con el certificado.

El certificado vence a los 90 días y la CRL a los 30. Para su mantenimiento, `pki issue` en la computadora responsable emite un certificado y renueva la CRL; distribuye los archivos públicos actualizados y copia el nuevo certificado/llave a EC2 antes de reiniciar el servicio. Conserva la CA y su contraseña para poder renovarlos.

## 4. Crear los roles y aplicar las migraciones en Supabase

En EC2 crea `.env.migraciones` con la conexión administrativa de Supabase y las dos contraseñas generadas en el paso 2:

```dotenv
DATABASE_ADMIN_URL='postgresql://postgres.PROJECT_REF:CONTRASENA_ADMIN@POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=/home/ubuntu/EySDatos_Proyect/ops/certs/supabase-ca.pem'
DIRECTORY_APP_PASSWORD=CONTRASENA_ROL_APP
DIRECTORY_BACKUP_PASSWORD=CONTRASENA_ROL_RESPALDO
```

Ejecuta este bloque entre paréntesis. Así, al terminar, las variables del administrador dejan de estar cargadas en esa terminal:

```bash
chmod 600 .env.migraciones
(
set -e
set -a
. ./.env.migraciones
set +a
.venv/bin/python -m directory.migrations.apply
)
```

El script crea `directory_owner`, `directory_app` y `directory_backup`, y aplica `001_init.sql`, `002_backup_role.sql`, `003_mfa.sql` y `004_session_mfa.sql` al esquema `directory`. La contraseña de aplicación debe coincidir con `DATABASE_URL`; la de respaldo se usará en el paso 8.

Si Supabase devuelve `permission denied for database postgres` al crear el esquema, abre **SQL Editor** como `postgres` y, con `directory_owner` ya creado por el script, ejecuta:

```sql
GRANT directory_owner TO postgres;
GRANT CREATE ON DATABASE postgres TO directory_owner;
```

Repite el bloque de migraciones. El permiso pertenece al propietario de migraciones, no al rol de aplicación. Véase la [guía de permisos de Supabase](https://supabase.com/kb/troubleshooting/resolving-permission-denied-for-database-postgres-during-migrations-78f33a).

## 5. Construir y arrancar el directorio por primera vez

En EC2, desde la carpeta principal del proyecto:

```bash
docker compose --profile deploy up -d --build directory
docker compose --profile deploy ps
docker compose --profile deploy logs --tail=50 directory
```

El servicio escucha por HTTPS en 8443, usa Supabase y guarda auditoría en el volumen `directory-logs`. Este despliegue inicia solo `directory`; `db` está reservado al desarrollo local. Los errores de conexión deben resolverse antes del primer login: revisa host/rol/contraseña de Supabase, certificado raíz y permisos del esquema.

## 6. Comprobar HTTPS y completar el primer login

En una **laptop**, sigue los pasos 1 a 3 de la guía local: instala dependencias, recibe `ca.pem` y `crl.pem`, e indica la URL remota en su `.env`. Comprueba:

```bash
set -a
. ./.env
set +a
curl --cacert "$DIRECTORY_CA_FILE" --crlfile "$DIRECTORY_CRL_FILE" --tlsv1.3 --tls-max 1.3 --include "$DIRECTORY_URL/health"
```

La respuesta esperada es `204 No Content`. Continúa con [Discord y Authenticator](ejecucion-local.md#4-iniciar-sesión-con-discord-y-vincular-authenticator), guarda los códigos de recuperación y el token de registro. Arranca `make client` y `make frontend` en dos terminales, crea tu identidad y comprueba el bloqueo/desbloqueo con un código nuevo de Authenticator. Un código usado debe rechazarse.

## 7. Guardar la configuración de recuperación

Guarda fuera de EC2 una copia protegida de `TOTP_ENCRYPTION_KEY`, `PSEUDONYM_KEY`, las credenciales necesarias y la CA con su contraseña. Guarda también `BACKUP_KEY` cuando la generes en el paso 8, separada del bucket. Cambiar `TOTP_ENCRYPTION_KEY` sin recifrar la base impide validar los factores ya vinculados. La copia de PostgreSQL no incluye esa clave ni las identidades e historiales locales de las laptops.

El directorio ya puede atender solicitudes; completa el respaldo diario y su prueba de recuperación para terminar la instalación.

## 8. Activar el respaldo diario de Supabase en S3

**Prueba del proyecto:** ya subimos una copia cifrada al bucket `proyecto-eticayseguridad`, comprobamos que llegó sin cambios y la recuperamos en una base de prueba separada. Se recuperaron 2 registros y se pudo descifrar el secreto de 1 autenticador ([evidencia](../ops/reports/f4-s3-smoke.txt)). Cron está configurado y activo; falta comprobar su primera ejecución automática. Los pasos siguientes permiten repetir la instalación con un bucket nuevo.

### 8.1 Crear el bucket y comprobar el rol

En la consola de S3 de tu cuenta de AWS Academy:

1. Crea un bucket de propósito general en `us-east-1`, con nombre único (por ejemplo, uno propio que empiece por `eysd-backups-`).
2. Conserva activados los cuatro bloqueos de acceso público y desactivadas las ACL.
3. Deja el versionado desactivado. El trabajo de este proyecto elimina las copias antiguas; no debe dejar versiones ocultas al borrar.
4. Usa cifrado de S3 con claves administradas por S3 (SSE-S3). Además, cada copia ya se cifra con AES-256-GCM antes de salir de EC2.

El bloqueo público y los permisos se comprueban antes de subir datos ([referencia de AWS](https://docs.aws.amazon.com/cli/latest/reference/s3api/get-public-access-block.html)).

En EC2 instala AWS CLI v2:

```bash
cd /tmp
curl -fSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip
unzip -q awscliv2.zip
sudo ./aws/install
cd /home/ubuntu/EySDatos_Proyect
aws --version
pg_dump --version
pg_restore --version
.venv/bin/python --version
```

Estos comandos son para la instancia **x86_64** del paso 1; la [instalación oficial de AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) incluye el paquete alternativo para ARM. El rol de EC2 se comprueba a continuación; no se necesitan claves AWS estáticas en el `.env`.

En la consola EC2, selecciona la instancia y abre **Actions > Security > Modify IAM role** para asociar el perfil permitido por AWS Academy. Comprueba desde EC2:

```bash
aws sts get-caller-identity
aws s3api get-public-access-block --bucket NOMBRE_DEL_BUCKET_NUEVO
aws s3api get-bucket-versioning --bucket NOMBRE_DEL_BUCKET_NUEVO
```

El primer comando debe mostrar la cuenta o rol que usa EC2. El segundo debe mostrar los cuatro bloqueos en `true`. El tercero no debe mostrar `Status`: el versionado debe estar desactivado. Si aparecen `false`, activa los cuatro bloqueos en **S3 > bucket > Permissions > Block public access** antes de seguir.

Los permisos necesarios son `s3:GetBucketPublicAccessBlock`, `s3:GetBucketVersioning` y `s3:ListBucket` sobre ese bucket; `s3:PutObject`, `s3:GetObject` y `s3:DeleteObject` sobre su prefijo `directory/`. Usa el rol de la instancia que permita AWS Academy, sin guardar `AWS_ACCESS_KEY_ID` ni `AWS_SECRET_ACCESS_KEY` en el `.env`. Que puedas crear un bucket desde la consola no demuestra por sí solo que el rol de EC2 pueda escribir en él.

### 8.2 Configurar la tarea

El entorno Python 3.12 y las herramientas `pg_dump`/`pg_restore` ya se instalaron en el paso 1. La tarea se ejecuta directamente en EC2, fuera del contenedor del directorio.

El usuario `directory_backup`, que solo puede leer la base, se habilitó en el paso 4. Usa su contraseña para agregar estas variables al `.env` de EC2, o guárdalas en `.env.backup` si prefieres separarlas:

```dotenv
BACKUP_DATABASE_URL='postgresql://directory_backup.PROJECT_REF:CONTRASENA_ROL_RESPALDO@POOLER_HOST:5432/postgres?sslmode=verify-full&sslrootcert=/home/ubuntu/EySDatos_Proyect/ops/certs/supabase-ca.pem'
BACKUP_KEY=CLAVE_BASE64URL_DE_32_BYTES
BACKUP_DIR=/var/tmp/eysd-backups
BACKUP_S3_BUCKET=NOMBRE_DEL_BUCKET_NUEVO
BACKUP_S3_PREFIX=directory
AWS_REGION=us-east-1
```

`BACKUP_DATABASE_URL` usa el usuario de base de datos que solo puede leer, no el administrador. Genera `BACKUP_KEY` una sola vez con `openssl rand -base64 32 | tr '+/' '-_'` y guarda una copia protegida fuera de EC2 y del bucket. No uses `TOTP_ENCRYPTION_KEY` como `BACKUP_KEY`: tienen funciones diferentes y se respaldan por separado. Ajusta la ruta absoluta al certificado y ejecuta `chmod 600 .env` (o `chmod 600 .env.backup` si elegiste el archivo separado).

`BACKUP_DIR` guarda las copias **ya cifradas** en EC2 mientras se suben. La copia externa queda en S3. El programa comprueba que el bucket bloquee el acceso público y no tenga versionado. Después sube la copia con [PutObject](https://docs.aws.amazon.com/cli/latest/reference/s3api/put-object.html) y revisa su tamaño y SHA-256 con [HeadObject](https://docs.aws.amazon.com/cli/latest/reference/s3api/head-object.html). Solo si todo coincide borra las copias de más de 30 días dentro de la carpeta `directory/` del bucket. Conserva los demás archivos.

### 8.3 Ejecutar y comprobar la primera copia

Desde la carpeta principal del proyecto en EC2:

```bash
make backup-remote
```

Si elegiste un archivo separado:

```bash
make backup-remote ENV_FILE=.env.backup
```

Debe terminar con código 0 y mostrar `copia remota verificada (SHA-256)`. Un error de permisos o una subida incompleta hace fallar la tarea y conserva las copias anteriores. Revisa en S3 que aparezca `directory/directory-FECHA.dump.enc`. El trabajo no guarda un volcado legible en el bucket.

### 8.4 Programarlo diariamente

En EC2, activa cron y abre la programación del usuario `ubuntu`, que puede ejecutar AWS CLI y leer la configuración:

```bash
sudo systemctl enable --now cron
crontab -e
```

Agrega esta línea, reemplazando la ruta completa de la carpeta del proyecto. Usa la variante que corresponda a tu archivo de configuración:

```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 3 * * * cd /home/ubuntu/EySDatos_Proyect && /usr/bin/flock -n /var/tmp/eysd-backup.lock /usr/bin/make backup-remote >> /var/tmp/eysd-backup.log 2>&1
```

```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 3 * * * cd /home/ubuntu/EySDatos_Proyect && /usr/bin/flock -n /var/tmp/eysd-backup.lock /usr/bin/make backup-remote ENV_FILE=.env.backup >> /var/tmp/eysd-backup.log 2>&1
```

Después de guardar el crontab, comprueba:

```bash
crontab -l
sudo systemctl is-active cron
timedatectl
```

Tras las próximas 03:00 del servidor revisa `tail -n 30 /var/tmp/eysd-backup.log`: debe aparecer una nueva copia remota verificada. Un log vacío antes del primer horario no acredita un fallo ni una ejecución.

`flock` evita que se hagan dos copias al mismo tiempo; usa solo una de las variantes anteriores. Es a las 03:00 según la zona horaria del servidor, no necesariamente Lima. Comprueba `crontab -l`, que el servicio cron esté activo, y que se genere una copia nueva tras la siguiente ejecución. Si cron no encuentra `aws` o `pg_dump`, configura su `PATH` con las rutas de instalación reales. Revisa el resultado y los errores; una EC2 apagada o un rol sin sesión válida no ejecutará la copia diaria. Esta línea programa F4; la purga y auditoría de F5 pertenecen a `ops.scheduled` y requieren configurar también el acceso a los registros del contenedor.

### 8.5 Comprobar la recuperación

Comparar SHA-256 permite comprobar que el archivo llegó sin cambios. También necesitamos restaurarlo para saber si sirve para recuperar la base. Descarga una copia cifrada desde S3 y ensaya recuperarla en un PostgreSQL **aislado** con los roles del proyecto y una clave `BACKUP_KEY` válida. No apuntes `make restore` a la base real para hacer un ensayo: reemplaza su esquema.

El bloque usa `.env`; si guardaste las variables de respaldo en `.env.backup`, cárgalo con `set -a; . ./.env.backup; set +a` dentro del bloque después de cargar `.env`.

Desde la carpeta principal del repositorio en EC2 usa el siguiente bloque, reemplazando `directory-FECHA.dump.enc` por el nombre exacto de la copia creada en el paso 8.3 y `NOMBRE_DEL_BUCKET_NUEVO` por tu bucket. Descarga el archivo conservando su nombre (el cifrado también comprueba ese nombre), crea un PostgreSQL 17 temporal en `127.0.0.1:55433`, restaura allí y valida que los factores MFA se puedan descifrar con la clave original, sin mostrarlos. El bloque usa una conexión de prueba en la misma EC2. No cambia el `.env` ni la base de Supabase. El puerto y el nombre de contenedor deben estar libres.

```bash
(
set -e
export RESTORE_TEST_PASSWORD="$(openssl rand -hex 24)"
export RESTORE_TEST_ARCHIVE=directory-FECHA.dump.enc
aws s3 cp "s3://NOMBRE_DEL_BUCKET_NUEVO/directory/$RESTORE_TEST_ARCHIVE" "/var/tmp/$RESTORE_TEST_ARCHIVE" --region us-east-1
POSTGRES_PASSWORD="$RESTORE_TEST_PASSWORD" docker run -d \
  --name eysd-restore-test \
  -e POSTGRES_PASSWORD -e POSTGRES_DB=restore_check \
  -p 127.0.0.1:55433:5432 postgres:17
timeout 60 sh -c 'until docker exec eysd-restore-test pg_isready -U postgres -d restore_check >/dev/null 2>&1; do sleep 1; done'
set -a
. ./.env
set +a
export DATABASE_ADMIN_URL="postgresql://postgres:$RESTORE_TEST_PASSWORD@127.0.0.1:55433/restore_check?sslmode=disable"
export DIRECTORY_APP_PASSWORD="$(openssl rand -hex 24)"
.venv/bin/python -m directory.migrations.apply
.venv/bin/python -m ops.backup.backup restore "/var/tmp/$RESTORE_TEST_ARCHIVE"
.venv/bin/python - <<'PY'
import os
import psycopg
from directory.app.mfa import Authenticator
with psycopg.connect(os.environ['DATABASE_ADMIN_URL']) as conn:
    keys = conn.execute('SELECT count(*) FROM directory.keys').fetchone()[0]
    factors = conn.execute('SELECT encrypted_secret FROM directory.mfa_accounts').fetchall()
    auth = Authenticator(os.environ['TOTP_ENCRYPTION_KEY'].encode())
    for (encrypted_secret,) in factors:
        auth.secret(encrypted_secret)
    print(f'Registros restaurados: {keys}')
    print(f'Factores MFA recuperados y descifrables: {len(factors)}')
PY
docker rm -fv eysd-restore-test >/dev/null
)
```

Si termina correctamente, elimina únicamente el contenedor y el volumen temporales que acaba de crear. Si falla un paso, el bloque se detiene y deja el contenedor para diagnosticarlo; después de revisarlo se limpia con `docker rm -fv eysd-restore-test` antes de repetir el ensayo. La consulta muestra conteos, nunca IDs ni secretos. Conserva la salida como evidencia de recuperación.

`make verify-backup` necesita crear y borrar una base temporal; no se debe ejecutar contra Supabase sin un entorno y permisos adecuados. Conserva evidencia del ensayo con conteos y tiempos, sin IDs, códigos ni secretos. Para que el autenticador vuelva a funcionar también necesitas la `TOTP_ENCRYPTION_KEY` original, guardada en un lugar seguro separado del bucket.

Antes de marcar F4 como desplegada deben existir el bucket privado, una copia remota verificada, la programación diaria y una restauración ensayada. Los respaldos administrados por Supabase, si están configurados, son un mecanismo diferente del respaldo cifrado de este proyecto.
