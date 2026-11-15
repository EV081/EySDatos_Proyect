# Activar Microsoft Authenticator en el directorio

El flujo es Discord → Microsoft Authenticator → token de registro. Se usa TOTP estándar;
no requiere API key, suscripción de Microsoft, correo ni SMS. También funciona con otras apps TOTP.
Microsoft explica cómo añadir cuentas externas en
[su documentación](https://support.microsoft.com/en-us/authenticator/how-to-add-your-accounts-to-microsoft-authenticator).

## Actualizar EC2

1. Lleva el código actualizado al servidor e instala `directory/requirements.txt` en su entorno virtual
   (o reconstruye la imagen Docker).
2. Genera una clave **una sola vez** en el servidor:

   ```bash
   .venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

3. Guarda el resultado como `TOTP_ENCRYPTION_KEY` en el entorno del directorio. No lo subas al repositorio.
   Conserva una copia protegida fuera del servidor y separada de los respaldos de Postgres. Reutiliza la
   misma clave en cada despliegue; una rotación requiere recifrar los secretos con la clave anterior.
4. Con las variables de administración de la base cargadas, aplica el esquema:

   ```bash
   .venv/bin/python -m directory.migrations.apply
   ```

   Esto incluye `003_mfa.sql`, es idempotente y no borra las llaves públicas existentes.
5. Reinicia el directorio con HTTPS y el entorno actualizado. En Compose, `TOTP_ENCRYPTION_KEY` ya
   se pasa al contenedor y es obligatoria. Mantén desactivados los registros de acceso también en el
   proxy inverso: las URLs de OAuth y los cuerpos de formularios contienen información sensible.
6. Comprueba que la hora del servidor esté sincronizada y que siga ejecutándose la purga diaria.

Los tokens de registro emitidos antes de la actualización vencen en diez minutos. Si quieres invalidarlos
inmediatamente durante el despliegue, con el servicio detenido elimina las filas de `directory.auth_tokens`
usando una conexión administrativa. Esto obliga a obtener un nuevo token con el segundo factor.

## Vincular tu celular

1. Ejecuta `python -m directory.client_lib.login` o abre `/auth/login` en el directorio por HTTPS.
2. Autoriza tu cuenta de Discord.
3. En Microsoft Authenticator pulsa **+ → Otra cuenta (Google, Facebook, etc.)** y escanea el QR.
   Si no puedes escanearlo, abre «Introducir la clave manualmente» e introdúcela en la app.
4. Escribe el código de seis dígitos de la app y confirma.
5. Guarda los diez códigos de recuperación fuera del dispositivo. Solo se muestran esta vez.
6. Copia el token de registro y continúa en el cliente como antes.

Las siguientes veces solo se pide el código. Si acabas de usarlo, espera al siguiente antes de iniciar
otra sesión. Tras cinco fallos espera cinco minutos y vuelve a iniciar sesión con Discord.

## Si pierdes el celular

Después de iniciar sesión con Discord, introduce un código de recuperación en el mismo campo.
Se mostrará un nuevo QR: vincula el nuevo dispositivo y confirma su código para recibir el token.
El factor anterior y todos los códigos anteriores dejan de servir. Guarda los nuevos códigos.

Los códigos de recuperación no recuperan la contraseña maestra ni descifran el historial local.
Si pierdes tanto el autenticador como sus códigos, no hay un restablecimiento automático mediante
correo o Discord que permita saltarse el segundo factor.
