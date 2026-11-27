# Aviso de privacidad

**Versión:** 1.4
**Vigente desde:** 2026-11-14

Este aviso te explica, en lenguaje claro, qué datos tuyos trata esta aplicación de mensajería cifrada, para qué, quién los recibe y cómo ejercer tus derechos, según la Ley N.° 29733 de Protección de Datos Personales y su reglamento.

## En pocas palabras

- Publicamos tu ID de Discord y tu llave pública para que otras personas puedan escribirte de forma cifrada. Nada más.
- El contenido de tus mensajes y tu llave privada nunca salen de tu dispositivo. Nosotros no podemos leerlos.
- Discord no puede leer tus mensajes, pero sí puede ver quién habla con quién y cuándo.
- Puedes cancelar tu registro y ejercer tus derechos cuando quieras.

## Quién es el responsable

Somos Elmer Villegas Suarez y Farid Aquino Castro, responsables del tratamiento y titulares del banco de datos del directorio, con domicilio en Lima, Perú. Puedes escribir a elmer.villegas@utec.edu.pe y farid.aquino@utec.edu.pe. Completaremos el domicilio postal antes de ampliar el uso con datos de terceros.

Para ejercer tus derechos, escribe a elmer.villegas@utec.edu.pe o a farid.aquino@utec.edu.pe. Te responderemos por un canal privado. No publiques tus datos personales en el repositorio.

## Qué datos tratamos

En el directorio guardamos:

- Tu **ID de Discord**.
- Tu **llave pública de firma**, que por diseño es pública.
- Las **fechas** de registro y de cambio de llave.
- La **versión de este aviso** que aceptaste y la fecha en que lo hiciste.
- Para la verificación en dos pasos: un **secreto TOTP cifrado**, hashes de códigos de recuperación,
  el estado de vinculación y los contadores y fechas necesarios para impedir reutilización y limitar intentos.
  Estos datos de autenticación son privados y no se publican con tu llave. El QR se genera sin servicios externos. Al desbloquear, el directorio recibe también un código temporal y una firma sobre un desafío; no recibe tu contraseña ni el historial. El directorio valida TOTP directamente, sin consultar una API de Microsoft.

La aplicación no solicita tu nombre, correo, teléfono, foto ni nombre de usuario, y sus registros no guardan tu dirección IP. Revisamos los registros del alojamiento por separado. No hacemos perfiles, no usamos tus datos para publicidad ni para análisis.

Lo que se queda **solo en tu dispositivo** y nosotros no vemos: el contenido de tus conversaciones, tu llave privada, tus contactos y su estado de verificación, y los mensajes pendientes de envío. Todo se guarda cifrado con una clave derivada de tu contraseña maestra.

## Para qué usamos tus datos

Solo para estas finalidades:

1. Que otras personas encuentren tu llave pública y puedan escribirte de forma cifrada.
2. Que tú y tus contactos comprueben que hablan con la persona correcta.
3. Proteger el registro y los cambios en el directorio mediante Discord y un código de Microsoft Authenticator, y validar el desbloqueo habitual con un código nuevo y una prueba firmada por tu cliente.

No usaremos tus datos para ninguna otra finalidad. Si esto cambiara, publicaríamos una nueva versión de este aviso y te pediríamos aceptarla de nuevo.

## Tu consentimiento

Tratamos tus datos con tu consentimiento, que es libre, previo, expreso, informado e inequívoco. La casilla de aceptación viene desmarcada y se refiere únicamente a las finalidades descritas arriba. Puedes retirarlo en cualquier momento cancelando tu registro, y retirarlo debe ser tan fácil como darlo.

## Carácter obligatorio u opcional

Tu ID de Discord, tu llave pública y la vinculación de una app autenticadora son **obligatorios** para registrar tu llave en el servicio. Si no los das, no podrás registrarte. Este servicio está pensado para personas **mayores de edad**; el registro exige declarar esa condición. No solicitamos documentos ni fecha de nacimiento para comprobarla.

## Quién recibe tus datos

- **Otras personas usuarias:** ven tu ID de Discord y tu llave pública cuando te buscan.
- **Discord:** recibe tus mensajes **ya cifrados** y los metadatos (quién escribe, a quién, cuándo y de qué tamaño). Discord es un responsable independiente de su propia plataforma.
- **Quienes operamos el directorio:** accedemos a los datos que conserva, con permisos mínimos.
- **Proveedor de alojamiento:** el directorio se aloja en Amazon EC2 en Virginia del Norte, Estados Unidos (`us-east-1`), y PostgreSQL está alojado en Supabase. Debemos confirmar y documentar la región del proyecto Supabase. Las copias de seguridad se conservan cifradas en Amazon S3, en Virginia del Norte, Estados Unidos (`us-east-1`).
- **Autoridades:** solo si una orden válida lo exige, y únicamente con los datos que realmente conservamos en el directorio y sus registros, descritos en este aviso. **No podemos entregar el contenido de tus mensajes ni tu llave privada, porque no los tenemos.** No existe ninguna llave de acceso excepcional ni puerta trasera.

No vendemos ni cedemos tus datos a otras personas o empresas.

## Transferencias internacionales

Tus mensajes cifrados y sus metadatos pasan por los servidores de Discord, que están en Estados Unidos. El contenido viaja cifrado de extremo a extremo y no puede leerse allí. El directorio se aloja en AWS EC2, Virginia del Norte, Estados Unidos (`us-east-1`), y la base PostgreSQL se aloja en Supabase. Tu ID de Discord, llave pública, fechas y datos privados de autenticación se tratan en esos servicios; debemos confirmar la región del proyecto Supabase antes de ampliar el uso con datos de terceros. Las copias de seguridad se conservan cifradas en Amazon S3, en Virginia del Norte, Estados Unidos (`us-east-1`). Debemos revisar las condiciones del proveedor y las garantías aplicables antes de ampliar el uso con datos de terceros.

## Cuánto tiempo conservamos tus datos

- **Tu registro en el directorio:** hasta que lo canceles.
- **Segundo factor confirmado:** hasta cancelar el registro; reemplazarlo invalida el factor anterior y sus códigos.
  Los intentos de vinculación sin confirmar se eliminan después de un día y las sesiones web de vinculación vencen en cinco minutos;
  la eliminación del estado vencido se ejecuta con la tarea diaria de mantenimiento. Los desafíos de desbloqueo duran hasta 120 segundos; la sesión local de la aplicación dura 30 minutos por defecto. Cerrar solo la pestaña no cierra el cliente local.
- **Llaves que reemplazaste:** 90 días.
- **Registros de auditoría del servicio:** 90 días, sin tu texto, sin tus llaves y con tu ID seudonimizado.
- **Copias de seguridad cifradas:** 30 días, con rotación.
- **Tus datos locales** (conversaciones, contactos, bóveda): hasta que tú los borres de tu dispositivo.

Lo que Discord conserve depende de sus propias condiciones. Aun así, los mensajes que guarda son ilegibles: las claves con las que se cifraron se destruyen al renovar o bloquear la sesión.

## El banco de datos

Los datos del directorio forman un banco de datos personales. El banco del proyecto **no está inscrito** en el Registro Nacional de Protección de Datos Personales. Antes de ampliar el uso del servicio, evaluaremos la obligación de inscripción y realizaremos el trámite si corresponde, como indicamos en la DPIA.

## Tus derechos

Puedes ejercer, cuando quieras y sin costo:

- **Acceso:** saber qué datos tuyos hay en el directorio, para qué se usan y con quién se comparten.
- **Rectificación:** corregir datos inexactos, por ejemplo cambiando tu llave.
- **Cancelación:** borrar tu registro. Lo quitamos del directorio de inmediato y de las copias de seguridad en un máximo de 30 días.
- **Oposición:** oponerte al tratamiento o retirar tu consentimiento.
- **Portabilidad:** llevarte tu identidad cifrada a otro dispositivo; la aplicación te permite exportarla.
- **Información:** conocer este aviso antes de dar tus datos y cada vez que cambie.
- **Tutela:** si crees que no se respetaron tus derechos, puedes reclamar ante la Autoridad Nacional de Protección de Datos Personales (ANPD) del Ministerio de Justicia y Derechos Humanos.

Responderemos dentro de los plazos que establece la ley. No tomamos decisiones automatizadas sobre ti.

## Cómo protegemos tus datos

Desplegamos y probamos el MFA del registro y del desbloqueo con Microsoft Authenticator. Usamos cifrado de extremo a extremo con renovación periódica de claves, verificación de identidad fuera de Discord, tu llave privada cifrada con tu contraseña maestra, conexión protegida con el directorio, permisos mínimos y registros con IDs seudonimizados, sin contenido ni secretos. Si ocurre un incidente de seguridad, lo documentaremos y evaluaremos las comunicaciones del artículo 34 del reglamento. Cuando se cumplan sus supuestos, notificaremos a la ANPD en un máximo de 48 horas desde que lo conozcamos; si afecta a otros derechos, te lo comunicaremos también dentro de las 48 horas y sin dilación indebida. En el entorno digital se contempla además la comunicación al Centro Nacional de Seguridad Digital.

## Lo que debes saber

- **No hay recuperación de contraseña.** No podemos restablecer tu contraseña maestra. Si la olvidas y no conservas una sesión abierta ni una exportación cuya contraseña recuerdes, no podrás recuperar tu identidad. Puedes exportarla previamente con otra contraseña. Esa exportación no incluye el historial: para recuperarlo también necesitas conservar el almacén local cifrado.
- **El desbloqueo habitual requiere conexión al directorio y un código nuevo.** Si falla la validación, la aplicación no abre la identidad ni el historial. Una sesión que ya estaba abierta conserva su plazo restante. El modo de desarrollo sin conexión es una simulación y no valida este segundo factor.
- **El MFA no cambia el cifrado de tus archivos.** Una copia de la bóveda y la contraseña correcta permiten descifrarla fuera de la aplicación, sin consultar al directorio ni introducir un código TOTP. Para leer el historial también hace falta el archivo del almacén local cifrado.
- **Guarda los códigos de recuperación del autenticador fuera del dispositivo.** Se usan después de iniciar sesión con Discord para vincular otro autenticador; no recuperan la contraseña maestra. Si pierdes el autenticador y los códigos, no hay restablecimiento automático.
- **Antes de cancelar el registro, exporta lo que necesites.** La cancelación elimina el factor del servidor. Si conservas los archivos locales, su próximo desbloqueo habitual ya no podrá validarse.
- **Los metadatos son visibles** para Discord y para las personas del canal.
- **Verifica a tus contactos.** Para conversar con alguien, los dos deben comparar antes la huella fuera de Discord: hasta entonces la aplicación no envía ni recibe mensajes de esa persona. Es lo que te asegura que hablas con quien crees.
- **Si el dispositivo está comprometido,** por ejemplo con un programa malicioso, la aplicación no puede protegerte.

## Cambios en este aviso

Si cambiamos este aviso, subiremos el número de versión y te pediremos aceptarlo de nuevo antes de seguir usando el servicio.
