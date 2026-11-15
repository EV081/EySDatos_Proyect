# Activar Microsoft Authenticator en el directorio

Para registrar o modificar llaves: Discord → Microsoft Authenticator → token de registro.
Para desbloquear habitualmente: contraseña maestra → código de Authenticator → conversaciones.
Se usa TOTP estándar;
no requiere API key, suscripción de Microsoft, correo ni SMS. También funciona con otras apps TOTP.
Microsoft explica cómo añadir cuentas externas en
[su documentación](https://support.microsoft.com/en-us/authenticator/how-to-add-your-accounts-to-microsoft-authenticator).

## Actualizar EC2

1. Lleva el código actualizado al servidor e instala `directory/requirements.txt` en su entorno virtual
   (o reconstruye la imagen Docker).
2. Genera una clave **una sola vez** en el servidor:

   ```bash
   openssl rand -base64 32 | tr '+/' '-_'
   ```

3. Guarda el resultado como `TOTP_ENCRYPTION_KEY` en el entorno del directorio. No lo subas al repositorio.
   Conserva una copia protegida fuera del servidor y separada de los respaldos de Postgres. Reutiliza la
   misma clave en cada despliegue; una rotación requiere recifrar los secretos con la clave anterior.
4. Con las variables de administración de la base cargadas, aplica el esquema:

   ```bash
   .venv/bin/python -m directory.migrations.apply
   ```

   Esto incluye `003_mfa.sql` y `004_session_mfa.sql`, es idempotente y no borra las llaves públicas existentes.
5. Reinicia el directorio con HTTPS y el entorno actualizado. En Compose, `TOTP_ENCRYPTION_KEY` ya
   se pasa al contenedor y es obligatoria. Mantén desactivados los registros de acceso también en el
   proxy inverso: las URLs de OAuth y los cuerpos de formularios contienen información sensible.
6. Comprueba que la hora del servidor esté sincronizada y que siga ejecutándose la purga diaria.

Los tokens de registro emitidos antes de la actualización vencen en diez minutos. Si quieres invalidarlos
inmediatamente durante el despliegue, con el servicio detenido elimina las filas de `directory.auth_tokens`
usando una conexión administrativa. Esto obliga a obtener un nuevo token con el segundo factor.

## Si ya tienes MFA del directorio desplegado en EC2 con Supabase

No generes otra `TOTP_ENCRYPTION_KEY` ni vuelvas a vincular tu celular. Conserva la clave existente.

1. Lleva el código actualizado a EC2. Como ya aplicaste `003_mfa.sql`, muestra únicamente la nueva migración:

   ```bash
   {
     printf 'BEGIN;\nSET LOCAL ROLE directory_owner;\nSET LOCAL search_path = directory;\n'
     cat directory/migrations/004_session_mfa.sql
     printf '\nCOMMIT;\n'
   }
   ```

2. Copia la salida completa y ejecútala en **SQL Editor** de tu proyecto Supabase con el rol `postgres`.
   Así no necesitas `DATABASE_ADMIN_URL` ni un entorno `.venv` en EC2.
3. Actualiza y recrea el directorio:

   ```bash
   docker compose --profile deploy up -d --build directory
   ```

4. Actualiza también el código de tu computadora. Reinicia `make client` y reconstruye el frontend con
   `make frontend`. El código de EC2 por sí solo no añade el campo del autenticador al frontend anterior.
5. Bloquea la identidad: al desbloquearla verás los campos de contraseña maestra y código de Authenticator.
   No hace falta volver a obtener un token del directorio ni pasar por Discord para cada desbloqueo.

## Vincular tu celular por primera vez

1. Ejecuta `python -m directory.client_lib.login` o abre `/auth/login` en el directorio por HTTPS.
2. Autoriza tu cuenta de Discord.
3. En Microsoft Authenticator pulsa **+ → Otra cuenta (Google, Facebook, etc.)** y escanea el QR.
   Si no puedes escanearlo, abre «Introducir la clave manualmente» e introdúcela en la app.
4. Escribe el código de seis dígitos de la app y confirma.
5. Guarda los diez códigos de recuperación fuera del dispositivo. Solo se muestran esta vez.
6. Copia el token de registro y continúa en el cliente como antes.

Las siguientes veces solo se pide el código. Si acabas de usarlo, espera al siguiente antes de iniciar
otra sesión. Tras cinco fallos espera cinco minutos y vuelve a iniciar sesión con Discord.

## Sesiones habituales

La pantalla de desbloqueo pide contraseña maestra y un código nuevo de seis dígitos. Se comprueba la
posesión de la llave registrada mediante una firma y luego se valida el código en EC2. La contraseña
y la llave privada no salen del dispositivo. Un código usado en el flujo de Discord no se puede reutilizar
para desbloquear; espera al siguiente código de la app.

Cada sesión dura 30 minutos por defecto; puedes ajustar `CLIENT_SESSION_TTL` en el entorno del cliente local.
Al bloquear o vencer el plazo se descartan las llaves de conversación en memoria y se vuelven a pedir los
dos factores. Cerrar solo la pestaña no cierra el cliente local. Si no hay conexión con el directorio, el
desbloqueo falla y el historial sigue bloqueado. Los códigos de recuperación se usan desde el flujo de
Discord para vincular un nuevo autenticador, no en el campo de seis dígitos del desbloqueo.

El formato de los archivos no cambia: están cifrados con la contraseña maestra. Este MFA controla el acceso
desde la aplicación, pero alguien con una copia de los archivos y la contraseña correcta puede descifrarlos
con otro programa. Para proteger ese caso se necesitaría otro diseño con una clave adicional custodiada por
el servidor; esta versión no implementa esa dependencia criptográfica ni altera las exportaciones existentes.

La cancelación del registro borra el factor del servidor. Si conservas archivos locales después de cancelar,
no se podrá validar su próximo desbloqueo habitual; exporta lo que necesites antes de hacerlo.

## Si pierdes el celular

Después de iniciar sesión con Discord, introduce un código de recuperación en el mismo campo.
Se mostrará un nuevo QR: vincula el nuevo dispositivo y confirma su código para recibir el token.
El factor anterior y todos los códigos anteriores dejan de servir. Guarda los nuevos códigos.

Los códigos de recuperación no recuperan la contraseña maestra ni descifran el historial local.
Si pierdes tanto el autenticador como sus códigos, no hay un restablecimiento automático mediante
correo o Discord que permita saltarse el segundo factor.
