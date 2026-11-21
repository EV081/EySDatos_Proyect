# Política de privacidad

**Versión:** 1.4
**Vigente desde:** 2026-11-14

Esta política explica, con palabras simples, cómo cuidamos tus datos personales y cómo puedes ejercer tus derechos. Sigue la Ley N.° 29733, Ley de Protección de Datos Personales del Perú, y su reglamento. El detalle de qué datos se publican y para qué está en el Aviso de privacidad, que aceptas al crear tu identidad (página /privacidad).

## Resumen en un minuto

- Publicamos tu **ID de Discord**, tu **llave pública** y algunas **fechas**. Para la autenticación guardamos
  además un secreto TOTP cifrado, hashes de recuperación y el estado necesario para limitar intentos y evitar
  códigos repetidos. Estos datos de autenticación son privados y se eliminan al cancelar el registro.
- **No podemos leer tus mensajes.** Se cifran en tu dispositivo y solo la otra persona puede descifrarlos.
- Tienes cuatro derechos principales, llamados **derechos ARCO**: **A**cceso, **R**ectificación, **C**ancelación y **O**posición.
- Pedirlos es **gratis** y puedes hacerlo cuando quieras.
- Si no te respondemos o no estás de acuerdo con la respuesta, puedes reclamar ante la **Autoridad Nacional de Protección de Datos Personales (ANPD)**.

## Qué es la Ley 29733

Es la ley peruana que protege tus datos personales: cualquier información que sirva para identificarte, como tu nombre, tu DNI o, en nuestro caso, tu ID de Discord. La ley dice que quien usa tus datos debe pedirte permiso, decirte para qué los usa, cuidarlos y dejarte controlarlos.

## Quién es responsable de tus datos

Somos Elmer Villegas Suarez y Farid Aquino Castro, en Lima, Perú. Decidimos cómo se usa el directorio de llaves y respondemos por él. Puedes escribir a elmer.villegas@utec.edu.pe y farid.aquino@utec.edu.pe.

El directorio se aloja en AWS EC2 en Virginia del Norte (`us-east-1`) y PostgreSQL en Supabase. Las copias de seguridad se conservan cifradas en Amazon S3, en Virginia del Norte (`us-east-1`), durante 30 días con rotación. Nos falta confirmar y documentar la región del proyecto Supabase en el inventario de alojamiento.

## Los principios que seguimos

La ley establece reglas básicas, llamadas principios. Así las cumplimos:

- **Legalidad:** usamos tus datos solo de formas permitidas por la ley. No compramos datos ni los obtenemos con engaños.
- **Consentimiento:** solo publicamos tus datos si marcas la casilla de aceptación. La casilla viene desmarcada y puedes retirar tu permiso cuando quieras.
- **Finalidad:** tus datos sirven para que otras personas te encuentren y puedan escribirte de forma cifrada,
  y para proteger tu registro y el desbloqueo habitual con verificación en dos pasos. No los usamos para publicidad, perfiles ni estadísticas.
- **Proporcionalidad:** pedimos lo mínimo. No te pedimos nombre, correo, teléfono, foto ni dirección.
- **Calidad:** tus datos deben ser correctos. Si tu llave cambia, puedes actualizarla.
- **Seguridad:** ciframos tus mensajes de extremo a extremo, tu llave privada queda protegida con tu contraseña maestra y el directorio usa conexiones protegidas y permisos mínimos.
- **Disposición de recurso:** si crees que algo está mal, tienes un camino para reclamar, primero con nosotros y luego ante la ANPD.
- **Nivel de protección adecuado:** si tus datos pasan por otro país, como los servidores de Discord en Estados Unidos, el contenido viaja cifrado y nadie allí puede leerlo.

## Tus derechos ARCO, en simple

### Acceso: saber qué tenemos de ti

Puedes preguntarnos qué datos tuyos hay en el directorio, para qué los usamos, de dónde salieron y con quién los compartimos.

**Ejemplo:** "Quiero saber qué datos míos tienen guardados." En la aplicación, **Mis datos y derechos ARCO** te muestra al instante lo que hay en tu dispositivo y en el directorio (tu ID, tu llave, las fechas y la versión del aviso que aceptaste), y te deja descargarlo.

### Rectificación: corregir lo que esté mal

Si algún dato está equivocado o desactualizado, puedes pedir que lo corrijamos.

**Ejemplo:** crees que tu llave se vio comprometida. Con **Cambiar mi llave** generas una nueva, que tu llave anterior autoriza con su firma; tu historial se conserva y tus contactos deberán volver a verificarte.

### Cancelación: borrar tus datos

Puedes pedir que eliminemos tu registro del directorio. Lo quitamos de inmediato y de las copias de seguridad en un máximo de 30 días. Después de eso, nadie podrá encontrar tu llave para escribirte.

**Ejemplo:** "Ya no quiero usar la aplicación, borren mi registro." Lo haces tú mismo con **Cancelar mi registro**, confirmando con tu contraseña maestra.

**Importante:** al cancelar puedes elegir si también se borra lo que está en tu dispositivo (identidad, contactos e historial). También puedes borrar solo eso con **Borrar mis datos de este dispositivo**.

### Oposición: decir "no" a un uso de tus datos

Puedes oponerte a que usemos tus datos o retirar el permiso que nos diste, si tienes un motivo legítimo o si cambias de opinión. En la práctica, retirar tu consentimiento significa cancelar tu registro, porque sin tu llave publicada el servicio no puede funcionar.

**Ejemplo:** "Ya no quiero que mi ID de Discord aparezca en el directorio." Usa **Cancelar mi registro**: retira tu consentimiento y borra tu registro en el mismo paso.

## Otros derechos que también tienes

- **Información:** conocer, antes de dar tus datos, quién los usará, para qué y por cuánto tiempo. Por eso te mostramos el aviso de privacidad antes de crear tu identidad.
- **Portabilidad:** llevar tu identidad a otro dispositivo. La aplicación te permite exportarla en un archivo cifrado con la contraseña que elijas para esa exportación; no incluye el historial ni los contactos.
- **Tutela:** reclamar ante la ANPD si no respetamos tus derechos.

## Cómo pedir tus derechos

**Desde la aplicación (lo más rápido):** abre la gestión de identidad y entra a **Mis datos y derechos ARCO**. Ahí puedes ver y descargar tus datos, cambiar tu llave, cancelar tu registro y borrar los datos de tu dispositivo. Lo que cambia el directorio te pide tu contraseña maestra y un token de registro de hasta 10 minutos emitido tras Discord y Authenticator, para comprobar que eres tú. El desbloqueo habitual usa contraseña y TOTP nuevo, sin repetir OAuth2; la sesión local dura 30 minutos por defecto. Si el directorio no responde, el historial sigue bloqueado.

**Si prefieres pedírnoslo o algo no funciona:**

1. Escribe a elmer.villegas@utec.edu.pe o farid.aquino@utec.edu.pe. No publiques tus datos personales ni códigos del autenticador en el repositorio.
2. Dinos **qué derecho** quieres ejercer y **qué pides** exactamente.
3. Escríbenos **desde tu propia cuenta de Discord**. Así comprobamos que eres el dueño del ID, sin pedirte tu DNI ni otros documentos.
4. Si actúas en nombre de otra persona, debes demostrar que te autorizó.

**Es gratis.** No te cobraremos nada por ejercer tus derechos.

## Cuánto tardamos en responder

Respondemos dentro de los plazos máximos que fija el reglamento de la ley, contados en días hábiles desde que recibimos tu pedido:

- **Información:** 8 días hábiles.
- **Acceso:** 20 días hábiles.
- **Rectificación, cancelación y oposición:** 10 días hábiles.

Si tu pedido está incompleto, te avisaremos para que lo completes.

## Lo que no podemos darte

Hay datos que **no tenemos**, así que no podemos entregarlos, ni a ti ni a nadie, ni siquiera a una autoridad:

- El **contenido de tus mensajes**: está cifrado y solo lo leen tú y la otra persona.
- Tu **llave privada** y tu **contraseña maestra**: nunca salen de tu dispositivo.
- Tus **contactos** y tu **historial**: viven solo en tu dispositivo.

No podemos restablecer tu contraseña maestra. Si la olvidas, puedes recuperar la identidad desde una exportación previa cuya contraseña recuerdes; también puedes generar una exportación mientras conserves una sesión abierta. La exportación contiene la identidad y la clave del almacén, pero no el historial ni los contactos: para recuperarlos también necesitas conservar el almacén local cifrado.

## Si no estás de acuerdo con nuestra respuesta

Si no te respondemos a tiempo, o si nuestra respuesta no te convence, puedes presentar una reclamación (procedimiento de tutela) ante la **Autoridad Nacional de Protección de Datos Personales (ANPD)** del Ministerio de Justicia y Derechos Humanos. Es gratuito.

## Acceso con el autenticador

Desplegamos y probamos el MFA del registro y del desbloqueo con Microsoft Authenticator. La contraseña cifra la bóveda; el TOTP permite abrirla desde la aplicación oficial. No modifica el cifrado de los archivos: quien tenga una copia y la contraseña correcta puede descifrarlos con otro programa. Cerrar la pestaña no bloquea por sí solo el cliente; debes bloquearlo o esperar a que venza el plazo local.

Si pierdes el autenticador, usa un código de recuperación después de entrar con Discord para vincular uno nuevo. Esos códigos no recuperan la contraseña maestra. Cancelar el registro borra el factor: exporta lo necesario antes de cancelar, porque no podrás validar el próximo desbloqueo habitual de los archivos conservados.

## Menores de edad

La aplicación está dirigida a personas **mayores de edad**. El registro exige declarar esa condición; no se comprueba mediante documentos ni fecha de nacimiento.

## Cambios en esta política

Si cambiamos esta política, subiremos el número de versión y la fecha de vigencia. Si el cambio afecta a cómo usamos tus datos, también actualizaremos el aviso de privacidad y te pediremos aceptarlo de nuevo.
