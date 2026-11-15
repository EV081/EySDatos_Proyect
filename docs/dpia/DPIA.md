# Evaluación de Impacto en la Protección de Datos (DPIA)

**Sistema:** mensajería cifrada de extremo a extremo sobre Discord
**Versión:** 1.3 · **Elaborada:** 2026-10-25 · **Fecha de aprobación:** 2026-11-15 · **Formato:** plantilla de 7 pasos (ICO), adaptada a la Ley 29733 y su reglamento (DS 016-2024-JUS)

## Datos del responsable

| | |
|---|---|
| Responsable del tratamiento | Equipo del proyecto: Elmer Villegas Suarez y Farid Aquino Castro |
| Delegado / oficial de datos | No designado. Ambos realizamos la revisión interna; esto no sustituye el cargo de oficial de datos personales cuando corresponda |
| Contacto para ejercer derechos | [elmer.villegas@utec.edu.pe](mailto:elmer.villegas@utec.edu.pe) y [farid.aquino@utec.edu.pe](mailto:farid.aquino@utec.edu.pe) |

---

## Paso 1. Necesidad de una DPIA

**Qué hace el proyecto.** Una capa de cifrado de extremo a extremo (E2EE) sobre la API de Discord. Cada persona usa un frontend conectado a un cliente local que cifra los mensajes antes de enviarlos. Discord recibe el texto cifrado y los metadatos del protocolo. Un *directorio de llaves* publica, por cada usuario, su ID de Discord y su llave pública de firma para que otros puedan encontrarla.

**Por qué se hace una DPIA.** Como parte del proyecto realizamos esta evaluación para identificar los riesgos del tratamiento de datos personales y definir las medidas para reducirlos, considerando los siguientes factores:

1. **Tecnología novedosa:** un protocolo criptográfico propio (handshake autenticado con PFS) que no ha tenido una auditoría externa.
2. **Puede alcanzar datos sensibles:** el contenido de las conversaciones es libre y puede incluir datos de salud, políticos, de menores, etc., aunque no podemos leerlos.
3. **Identificadores de personas reales:** el directorio relaciona un ID de Discord con una llave y una fecha.
4. **Privacidad desde el diseño:** conviene identificar los riesgos antes de que entre un solo dato real.

---

## Paso 2. Descripción del tratamiento

### 2.1 Naturaleza: cómo se recogen, usan, guardan y borran los datos

![Flujo de datos entre el dispositivo, el directorio en EC2 y Discord](../img/dpia-tratamiento.png)

El directorio está desplegado en Amazon EC2, en Virginia del Norte, Estados Unidos (`us-east-1`). PostgreSQL está alojado en Supabase, en el proyecto que elegimos; debemos registrar su región por separado de la de EC2. El cliente y el frontend siguen en el dispositivo de cada persona. Desplegamos y probamos el MFA del registro y del desbloqueo habitual con Microsoft Authenticator. Las copias cifradas se guardan en el bucket privado S3 `proyecto-eticayseguridad`, en `us-east-1`; descargamos una copia y la restauramos en PostgreSQL aislado.

| Etapa | Qué ocurre | Dónde |
|---|---|---|
| **Recolección** | La persona escribe su ID de Discord y acepta el aviso de privacidad. El dispositivo genera la llave de identidad; solo la llave **pública** y el ID se publican. OAuth2 y TOTP autorizan el registro; el secreto del factor se guarda cifrado y los códigos de recuperación como hashes. | Dispositivo -> directorio |
| **Almacenamiento** | Llave privada y datos locales: cifrados con AES-256-GCM bajo una clave derivada de la contraseña maestra (Argon2id). Directorio: base de datos con ID, llave pública y fechas. Discord: ciphertext. | Dispositivo; directorio; Discord |
| **Uso** | Cifrar, firmar y descifrar mensajes y verificar contactos en el dispositivo. El directorio valida la firma de desbloqueo y el TOTP antes de que el cliente abra el historial. | Dispositivo; directorio para autenticación |
| **Compartición** | Con otros usuarios (llave pública, por diseño) y con Discord (ciphertext y metadatos, por necesidad técnica). El proveedor del alojamiento del directorio también procesa los datos necesarios para prestar ese servicio; la base PostgreSQL está en Supabase, separada de EC2 y los respaldos cifrados se almacenan en S3, en Virginia del Norte. | No aplica |
| **Destrucción** | Llaves de sesión y llaves efímeras: se destruyen al rotar o bloquear. El resto, según la tabla de retención (2.2). | Dispositivo; directorio |

**Fuentes de datos:** la propia persona (ID, mensajes) y el dispositivo (llaves generadas). El ID de Discord se vincula con su cuenta mediante OAuth2 (`identify`), sin pedir nada más.

**Tratamientos de riesgo alto presentes:** tecnología novedosa (protocolo propio sin auditoría externa). **No hay** perfilado, decisiones automatizadas, seguimiento de comportamiento ni vigilancia sistemática.

### 2.2 Alcance: qué datos, cuántos, cuánto tiempo

| Dato | Dónde está | Sensibilidad | Quién lo puede ver | Retención |
|---|---|---|---|---|
| ID de Discord | Directorio; contactos locales; datos de remitente y destinatario de cada mensaje; registros (seudonimizado) | Personal (identificador) | Directorio, Discord y miembros del canal | Hasta que la persona cancele su registro |
| Llave pública de firma | Directorio; contactos locales | Pública por diseño | Cualquier usuario | Igual que el ID. Llaves reemplazadas: 90 días |
| Fechas de registro y de cambio de llave | Directorio | Personal (metadato) | Operadores del directorio | Igual que el registro |
| Versión del aviso aceptado y fecha | Directorio; almacén local | Personal (prueba de consentimiento) | Operadores; la propia persona | Mientras dure el registro; la auditoría se conserva seudonimizada durante 90 días |
| Secreto TOTP cifrado, hashes de recuperación y estado de autenticación | Directorio; secreto también en la app autenticadora | Crítica (autenticación) | Backend con clave de cifrado independiente; metadatos accesibles a la persona | Hasta cancelar el registro o reemplazar el factor; altas sin confirmar: un día; sesiones de vinculación: cinco minutos, con purga diaria; desafío de desbloqueo: 120 segundos |
| Contenido de los mensajes (texto plano) | **Solo** el dispositivo: memoria y almacén local cifrado | **Potencialmente sensible**; no podemos leerlo | Solo los dos interlocutores | Hasta que la persona lo borre localmente |
| Mensajes cifrados | Discord | Ilegible sin las llaves de sesión, que ya no existen tras rotar o bloquear | Discord y miembros del canal | Según Discord (fuera de nuestro control) |
| Metadatos de mensajes (quién, a quién, cuándo, tamaño) | Discord; canal | Personal (relaciones sociales) | Discord y miembros del canal | Según Discord |
| Llave privada y clave del almacén local | Solo el dispositivo, en la bóveda cifrada | Crítica | Nadie sin la contraseña maestra | Hasta que la persona borre la bóveda |
| Alias y pines de los contactos, historial, cola de salida | Almacén local cifrado | Personal | Solo la persona | Hasta que la persona los borre |
| Registros de auditoría | Servidor del directorio | Personal (ID seudonimizado) | Operadores | 90 días |
| Copias de seguridad del directorio | Fuera del servidor, cifradas | Igual que el directorio | Operadores | Rotación de 30 días |

**Por qué estos plazos.** Cada dato se conserva solo mientras sirve a su finalidad (limitación del plazo de conservación):

* **Registro del directorio, hasta que la persona lo cancele.** Su base es el consentimiento; sin él no hay razón para conservarlo.
* **Registros de auditoría, 90 días.** Un incidente suele detectarse semanas después de ocurrir; ese tiempo permite investigarlo y reunir la evidencia que pide la notificación a la autoridad (48 horas desde que se conoce). Más allá no hay finalidad que lo justifique.
* **Llaves reemplazadas, 90 días.** Permiten explicar y revisar un cambio de llave sospechoso; después no aportan nada.
* **Copias de seguridad, 30 días con rotación.** Equilibran poder recuperarse de un desastre o ataque con que una cancelación quede completa, también en las copias, en un mes. Una copia más antigua sobreviviría al borrado.
* **Autenticación:** el factor confirmado se conserva hasta cancelar el registro o reemplazarlo. El estado de vinculación sin confirmar se purga tras un día; las sesiones web vencen a los cinco minutos y los desafíos firmados a los 120 segundos. La sesión local real dura 30 minutos por defecto y no se persiste como autorización para un próximo desbloqueo. Estos plazos son distintos de la retención de datos.
* **Contenido local:** lo decide la persona, porque solo existe en su dispositivo.

Definimos estos plazos en el código y en las políticas. Debemos comprobar su programación y ejecución en el alojamiento y revisarlos si cambia la finalidad.

**Categorías especiales:** el sistema no las recoge ni puede leerlas; solo podrían aparecer dentro de los mensajes, que solo ven las personas que conversan.
**Volumen y frecuencia:** demostración con 2 usuarios; uso real previsto de decenas. Un registro por persona; los mensajes dependen de ellas.
**Personas afectadas:** usuarios de la aplicación y sus contactos (que solo se publican mediante registro con OAuth2, prueba de posesión y consentimiento: ver R7).
**Área geográfica:** Participantes del proyecto en Perú. Discord trata datos en su infraestructura internacional. El directorio se aloja en AWS EC2, en Virginia del Norte, Estados Unidos (`us-east-1`); PostgreSQL se aloja en Supabase. Nos falta confirmar la región de Supabase; no podemos deducirla de la región de EC2. Las copias cifradas se alojan en S3, en Virginia del Norte (`us-east-1`).

### 2.3 Contexto

* **Relación con las personas:** directa y voluntaria; no tenemos ningún vínculo de autoridad sobre ellas.
* **Control que tienen:** crean y bloquean su identidad, exportan su identidad cifrada, verifican contactos, deciden con quién hablan. Pueden borrar su registro del directorio con la opción de cancelación (C-11).
* **Expectativas:** quien usa una herramienta "cifrada" espera que nadie lea sus mensajes; no necesariamente que los **metadatos** queden visibles (ver R1). Por eso el aviso lo dice explícitamente.
* **Menores y grupos vulnerables:** La aplicación está dirigida a mayores de edad. El frontend exige declarar esa condición al aceptar el aviso, pero no comprueba edad con documentos ni fecha de nacimiento (ver R12).
* **Inquietudes previas:** el debate público sobre el acceso excepcional frente al E2EE. Adoptamos una posición explícita: **no existe ninguna llave de custodia ni puerta trasera**.
* **Novedad:** el protocolo es propio, aunque se compone de primitivas estándar y sigue el patrón de SSH y TLS 1.3. No ha pasado una auditoría externa.
* **Códigos de conducta o certificaciones:** ninguno.

### 2.4 Finalidades

1. Permitir conversaciones privadas sobre una plataforma popular, de modo que ni Discord ni una brecha en sus servidores expongan el contenido.
2. Permitir que las personas encuentren la llave de sus contactos y comprueben su identidad.
3. Proteger el registro del directorio con Discord y TOTP, y validar el desbloqueo habitual mediante contraseña local, desafío firmado y un código nuevo del autenticador.

**Efecto buscado en las personas:** más privacidad de lo que dicen, sin cambiar de plataforma. **Beneficio más amplio:** demostrar que se puede añadir E2EE sobre un servicio que no lo ofrece.

---

## Paso 3. Proceso de consulta

| Parte | Cómo se consulta | Estado |
|---|---|---|
| Equipo del proyecto | Revisamos de forma cruzada el trabajo de cada integrante | Finalizada |
| Personas usuarias | Probamos internamente el sistema y revisamos la claridad del aviso, la recuperación del acceso y la verificación de contactos | Finalizada; consulta interna |
| Revisión por pares | Revisamos entre ambos las finalidades, los plazos de conservación, los riesgos y las medidas de esta DPIA | Finalizada |
| Discord | No le consultamos porque es un tercero independiente. Tomamos sus condiciones como un dato de contexto (ver paso 4) | No aplica |
| Revisión técnica | Analizamos el código con Bandit, pip-audit y gitleaks, y realizamos entre ambos la revisión humana del protocolo | Finalizada: análisis automatizado y revisión humana realizados |
| Auditoría externa del protocolo | Recomendamos una auditoría independiente antes de ampliar el uso del sistema | Recomendada |

---

## Paso 4. Necesidad y proporcionalidad

* **Base de licitud:** consentimiento libre, previo, expreso, informado e inequívoco (Ley 29733), pedido al registrarse y por separado de cualquier otra cosa. Está **desmarcado por defecto**, cubre las finalidades de 2.4 y su versión se registra. No se condiciona el uso a ninguna otra finalidad.
* **¿Se logra la finalidad?** Sí: conversación cifrada de extremo a extremo con verificación de identidad.
* **¿Hay otra forma de lograrlo?** Usar Signal o similar da mejor protección, pero el objetivo es proteger conversaciones **dentro de Discord**. Descartamos intercambiar llaves a mano por la dificultad de uso; el directorio es el compromiso, y la ceremonia de verificación fuera de banda impide que el directorio pueda sustituir llaves sin que se detecte.
* **Prevención de usos adicionales (*function creep*):** el directorio solo guarda lo que está en la tabla 2.2; las finalidades se limitan a las de 2.4; no se hace analítica ni publicidad; si el aviso cambia, sube la versión y hay que volver a aceptarlo.
* **Calidad y minimización:** no se piden nombre, correo, teléfono, avatar ni nombre de usuario; el directorio no registra direcciones IP (C-05 implementada en la aplicación; revisar registros del alojamiento). El cliente nunca envía contenido al directorio.
* **Información a las personas:** resumen del aviso (versión 1.4) visible antes de aceptar; el texto completo, con los elementos que exige la Ley 29733, se publica dentro de la aplicación y está disponible en el [aviso de privacidad](../privacidad/aviso-de-privacidad.md).
* **Derechos (ARCO y portabilidad):**

| Derecho | Cómo se atiende | Estado |
|---|---|---|
| Acceso | La persona consulta su propio registro (ID, llave, fechas, aviso aceptado, llaves reemplazadas) y lo que hay en su dispositivo, y lo descarga en JSON | Implementado en «Mis datos y derechos ARCO» |
| Rectificación | La persona cambia su llave, autoriza el cambio con la anterior y conserva el historial de cambios | Implementada en «Cambiar mi llave» |
| Cancelación | La persona solicita el borrado de su registro, firmado con su llave; el directorio lo elimina de inmediato y las copias en un máximo de 30 días; los registros de auditoría caducan a los 90 días | Implementada en «Cancelar mi registro» |
| Oposición | La persona puede no registrarse o cancelar su registro; retirar el consentimiento utiliza la misma opción de cancelación | Implementada por diseño y desde la aplicación |
| Portabilidad | La persona exporta su identidad cifrada con la contraseña que elija para importarla en otro dispositivo; el archivo no incluye historial ni contactos | Implementada y probada |
| Borrado local de datos | La persona borra la bóveda y el almacén cifrado mediante su contraseña maestra | Implementado en «Borrar mis datos de este dispositivo» |

* **Encargados:** Discord **no** es un encargado nuestro: es un responsable independiente de su propia plataforma. AWS presta el alojamiento del directorio en EC2, Virginia del Norte, Estados Unidos (`us-east-1`), y Supabase presta el alojamiento de PostgreSQL. El directorio se conecta a la base con el rol de aplicación y verificación TLS. Debemos revisar las condiciones de tratamiento y los accesos de administración, incluidos los respaldos cifrados en S3 (`us-east-1`). El cifrado E2EE no elimina el tratamiento de los identificadores por estos proveedores.
* **Transferencias internacionales:** a Discord (EE. UU.) viajan solo texto cifrado y metadatos; el contenido no puede leerse en destino. El directorio trata identificadores y datos de autenticación en Estados Unidos (`us-east-1`). Supabase almacena los registros y datos privados de autenticación en la región configurada para su proyecto; debemos confirmar y documentar esa región para evaluar el flujo internacional completo. Esto constituye otro flujo internacional de datos personales; debemos revisar las garantías aplicables, incluidas las de los respaldos cifrados en S3, en Virginia del Norte.

---

## Paso 5. Identificación y evaluación de los riesgos

**Escalas (plantilla ICO).** Probabilidad: *Remota*, *Posible*, *Probable*. Gravedad: *Mínima*, *Significativa*, *Grave*. Riesgo global:

| | Mínima | Significativa | Grave |
|---|---|---|---|
| **Probable** | Medio | **Alto** | **Alto** |
| **Posible** | Bajo | Medio | **Alto** |
| **Remota** | Bajo | Bajo | Medio |

Los riesgos están descritos con las medidas **de diseño base** ya consideradas (E2EE, firmas y PFS) pero **antes** de las medidas adicionales del paso 6. Usamos las categorías LINDDUN: L = vinculabilidad, I = identificabilidad, N = no repudio, D = detectabilidad, Di = divulgación, U = desconocimiento, NC = incumplimiento.

| ID | Riesgo y su impacto en las personas | LINDDUN | Probabilidad | Gravedad | Riesgo global |
|---|---|---|---|---|---|
| **R1** | **Exposición de metadatos.** Discord y quienes están en el canal ven quién habla con quién, cuándo y con qué tamaño. Permite inferir relaciones, hábitos y a veces el contenido por el patrón de mensajes. | L, D | Probable | Significativa | **Alto** |
| **R2** | **Sustitución de la llave por un directorio malicioso o comprometido.** Un atacante entrega su llave en lugar de la del contacto y se interpone en el primer contacto, con acceso a la conversación. | I, Di | Posible | Grave | **Alto** |
| **R3** | **Robo o infección del dispositivo.** Acceso al historial, contactos, cola de salida y a la bóveda. | Di | Posible | Grave | **Alto** |
| **R4** | **Contraseña maestra débil, olvidada o perdida.** Un atacante con la bóveda robada puede probar contraseñas; si la persona la olvida sin conservar una sesión abierta ni una exportación utilizable, no puede recuperar la identidad ni descifrar el historial. La exportación permite elegir otra contraseña y conserva la clave del almacén, pero recuperar el historial requiere además el almacén local cifrado. | Di | Posible | Significativa | Medio |
| **R5** | **Brecha en la base de datos del directorio.** Se filtran IDs, fechas y estado de autenticación, secretos TOTP cifrados y hashes de recuperación. Si también se filtra la clave de cifrado del factor TOTP, se pueden generar códigos del factor; el robo de la base por sí solo no revela la contraseña ni el historial local. | I, L, D | Posible | Significativa | Medio |
| **R6** | **Conservación excesiva o borrado incompleto.** Los datos permanecen en copias de seguridad, registros o Discord tras pedir la cancelación. | NC | Probable | Significativa | **Alto** |
| **R7** | **Falta de transparencia.** Las personas no entienden qué se ve y qué no (metadatos, verificación, sin recuperación), o un contacto aparece en el directorio sin haberlo aceptado. | U | Probable | Significativa | **Alto** |
| **R8** | **Registros (logs) con datos personales.** Un fallo deja IDs en claro, llaves o texto en los registros del servicio. | Di, D | Posible | Significativa | Medio |
| **R9** | **Incumplimiento legal.** Banco de datos sin inscripción cuando corresponda, transferencia internacional sin garantías o incumplimiento de las comunicaciones del art. 34 del reglamento. | NC | Posible | Significativa | Medio |
| **R10** | **Filtración del token del bot o de las credenciales OAuth.** Un tercero lee o publica en el canal y observa el tráfico cifrado y los metadatos. | Di, D | Posible | Significativa | Medio |
| **R11** | **Robo de la llave de identidad.** El atacante firma handshakes futuros y se hace pasar por la persona ante sus contactos. | I, N | Posible | Grave | **Alto** |
| **R12** | **Menores de edad.** Una persona menor podría declarar falsamente ser mayor de edad y publicar su ID sin comprender el alcance. La declaración del frontend no es verificación documental. | U, NC | Posible | Significativa | Medio |
| **R13** | **Defecto en el protocolo o en su implementación.** Un fallo criptográfico no detectado expone mensajes o permite suplantar. Sin auditoría externa. | Di, I | Posible | Grave | **Alto** |
| **R14** | **Pérdida del autenticador o indisponibilidad de la validación remota.** El cliente real no abre el historial sin comprobar el factor. Una caída del directorio, perder la clave de cifrado del TOTP o quedarse sin autenticador ni códigos impide el acceso habitual aunque se conserve la contraseña. | U | Probable | Significativa | **Alto** |

---

## Paso 6. Medidas para reducir los riesgos

Identificamos las medidas como **restricciones verificables** (C-xx). Indicamos cómo comprobar cada una y el área correspondiente; ambos nos encargamos de su implementación y revisión.

### 6.1 Restricciones

| ID | Restricción | Cómo se verifica | Área responsable | Estado |
|---|---|---|---|---|
| **C-01** | Ningún contenido de mensaje sale del dispositivo en claro: en el canal solo hay mensajes `E2EE1:` y el texto cifrado | Pruebas de envío cifrado y revisión de los mensajes publicados en el canal | Cliente y criptografía | Implementada |
| **C-02** | La llave privada, la clave del almacén local y el historial solo existen en disco cifrados con AES-256-GCM; las llaves de sesión y efímeras nunca se escriben | Pruebas de cifrado de archivos locales y de eliminación de llaves efímeras y de sesión | Cliente y criptografía | Implementada |
| **C-03** | Argon2id con al menos t=3, m=64 MiB, p=4 y *salt* único; los parámetros están autenticados y acotados | Revisión de los parámetros de derivación y pruebas de rechazo de parámetros alterados o fuera de los límites | Cliente y criptografía | Implementada |
| **C-04** | Tras 5 contraseñas incorrectas, el desbloqueo se bloquea 30 s; al bloquear o vencer la sesión local se destruyen las sesiones | Pruebas de bloqueo por intentos fallidos y destrucción de sesiones al bloquear la aplicación | Cliente y criptografía | Implementada |
| **C-05** | La aplicación guarda ID de Discord, llave pública, fechas, aviso y los datos privados mínimos para TOTP (secreto cifrado y hashes de recuperación). Sus registros no guardan nombre, correo, avatar ni IP; revisar por separado los registros de EC2 y de cualquier proxy | Revisión del esquema de la base y pruebas de minimización de datos y registros | Directorio | Implementada |
| **C-06** | Publicar o cambiar una llave exige prueba de posesión firmada, OAuth2 con el mismo ID y un segundo factor TOTP sin reutilización de códigos | Pruebas de vinculación, rechazo de códigos reutilizados, bloqueo, recuperación y concurrencia; registro con Discord y Microsoft Authenticator | Directorio | Desplegada y probada con Microsoft Authenticator |
| **C-07** | El directorio solo se sirve por TLS 1.3 con una CA propia y el cliente rechaza un certificado inválido sin ofrecer continuar | Pruebas de rechazo de certificados inválidos, vencidos, revocados o de otro nombre, y de conexiones TLS 1.2 | Infraestructura | Implementada |
| **C-08** | La aplicación usa un rol de base de datos sin permisos de DDL ni de propietario y solo consultas parametrizadas; *rate-limit* anti-enumeración | Pruebas del rol con permisos limitados, rechazo de inyección SQL y bloqueo de accesos ajenos | Directorio | Implementada |
| **C-09** | Los registros de auditoría no contienen texto, llaves, tokens ni IDs en claro (los IDs se seudonimizan con HMAC y una clave que se rota cada 90 días) | Revisión de los registros generados durante los flujos de uso y pruebas del filtro de redacción | Auditoría | Implementada |
| **C-10** | Retención: registros 90 días; llaves reemplazadas 90 días; copias de seguridad 30 días con rotación; registro del directorio hasta su cancelación | Pruebas de purga de registros, llaves reemplazadas y rotación de copias de seguridad | Operaciones | Implementada en código; activación y evidencia del entorno real pendientes |
| **C-11** | Existe una opción para cancelar el registro de una persona mediante una solicitud firmada con su llave y borrarlo en el directorio de inmediato y de las copias en un máximo de 30 días | Pruebas de borrado inmediato del registro y de caducidad de las copias a los 30 días | Directorio y respaldos | Implementada |
| **C-12** | Las copias de seguridad están cifradas, fuera del servidor del directorio, con restauración probada | Pruebas de cifrado y restauración; objetivos de recuperación: pérdida máxima de 24 horas de datos y recuperación en 30 minutos | Respaldos | Copia real en S3 descargada y restaurada en PostgreSQL aislado (2 registros y 1 factor MFA descifrable); tarea programada instalada y activa; falta observar una ejecución automática |
| **C-13** | Los secretos (token del bot, credenciales OAuth y clave de cifrado del factor TOTP) están en variables de entorno; el repositorio no contiene secretos; el token de la API local solo se envía a `127.0.0.1`/`localhost` | Escaneo del repositorio y su historial con gitleaks sin hallazgos; pruebas de restricción del token de la API al dispositivo local | Operaciones y cliente | Implementada |
| **C-14** | Antes de publicar una llave, la persona acepta el aviso de privacidad vigente (casilla desmarcada, finalidades declaradas); se registra la versión y la fecha y el directorio las conserva | Pruebas de aceptación obligatoria del aviso y conservación de su versión y fecha | Cliente y directorio | Implementada |
| **C-15** | El aviso de privacidad completo cumple los elementos de la Ley 29733 y se muestra antes de aceptar; sube de versión si cambia | Revisión del contenido del aviso y pruebas de su publicación en la aplicación y de coherencia de versión y plazos | Privacidad | Implementada |
| **C-16** | Ante un cambio de llave de un contacto verificado: se revoca la verificación, se aborta el handshake y no se ofrece "continuar" | Pruebas de revocación de la verificación y rechazo de la conexión tras un cambio de llave | Cliente y criptografía | Implementada |
| **C-17** | Nada de lo que llega de Discord se interpreta como HTML ni se ejecuta | Pruebas en navegador con contenido malicioso y revisión del tratamiento de los mensajes como texto | Cliente y criptografía | Implementada |
| **C-18** | La API local solo escucha en `127.0.0.1`, exige token, restringe CORS al origen del frontend y valida el `Host` | Pruebas de rechazo de tokens incorrectos, orígenes y nombres de servidor no autorizados | Cliente y criptografía | Implementada |
| **C-19** | Existe un plan con registro de incidentes, rotación y revocación de llaves y evaluación de las comunicaciones del art. 34 del reglamento, incluido el plazo máximo de 48 horas cuando corresponde | [Plan de respuesta a incidentes](../politicas/respuesta-incidentes.md), con contactos del equipo y procedimiento de simulacro (anexo B) | Equipo | Plan implementado; validación de contactos operativos y simulacro pendientes |
| **C-20** | El código pasa SAST (Bandit/Semgrep) y escaneo de dependencias (pip-audit) en CI, y los hallazgos altos están corregidos | Análisis automatizado en integración continua y revisión de reportes: sin hallazgos abiertos tras su clasificación | Operaciones | Implementada |
| **C-21** | Existe un botón para borrar localmente la bóveda y el almacén cifrado | Pruebas de borrado de la bóveda y del almacén cifrado desde la aplicación | Cliente y criptografía | Implementada |
| **C-22** | El protocolo está documentado, con tabla de ataques considerados y pruebas negativas por cada defensa; se deja constancia de que no hubo auditoría externa | Documentación del protocolo, revisión humana interna y pruebas negativas comprobadas mediante defectos introducidos a propósito | Cliente y criptografía | Implementada |
| **C-23** | El canal de Discord del proyecto es privado y de acceso restringido a los participantes | Comprobación del servidor real: el canal solo es visible para participantes autorizados y el bot dispone de permisos mínimos | Transporte | Implementada |
| **C-24** | Antes de ampliar el uso del servicio: inscribir el banco de datos ante la ANPD si corresponde, mantener el servicio dirigido a mayores de edad y revisar las condiciones de tratamiento del proveedor que ya aloja el directorio | Lista de verificación previa a la ampliación del servicio | Ambos | Pendiente |
| **C-25** | El desbloqueo habitual exige contraseña, nonce firmado de propósito `unlock` y TOTP nuevo; no habilita el historial si falta el factor o el directorio falla. La sesión local vence a los 1800 segundos por defecto y descarta las llaves en memoria | Pruebas de contraseña, desafío firmado, segundo factor y vencimiento de sesión; uso real con Microsoft Authenticator | Cliente, criptografía y directorio | Implementada, desplegada y probada con Microsoft Authenticator |

### 6.2 Medidas por riesgo

| Riesgo | Medidas | Efecto | Riesgo residual | Aprobación |
|---|---|---|---|---|
| **R1** Metadatos | C-23 (canal privado y acotado), C-15 (el aviso lo dice con claridad), C-01. Recomendado a futuro (sección 8 del informe): relleno de mensajes a tamaño fijo y un canal por par de contactos (ver las recomendaciones) | Reducido: la exposición sigue existiendo, pero se limita a un público pequeño y la persona lo sabe; **sin la aplicación, Discord vería además el contenido** | Probable x Mínima -> **Medio** | Sí |
| **R2** Sustitución de llaves | C-07, C-06, C-16, y la ceremonia fuera de banda con *pin* | Reducido; el primer contacto no verificado sigue dependiendo de la confianza en el directorio (TOFU) | Remota x Grave -> **Medio** | Sí; la interfaz muestra "sin verificar" |
| **R3** Dispositivo | C-02, C-03, C-04, C-25. Fuera de alcance: un dispositivo ya comprometido con la aplicación desbloqueada | MFA limita el cliente oficial y el vencimiento reduce la ventana abierta. Una copia de los archivos con la contraseña correcta puede descifrarse fuera de la aplicación; no se reduce la puntuación por MFA | Remota x Grave -> **Medio** | Sí |
| **R4** Contraseña | C-03 y mínimo de 10 caracteres; exportación de la identidad como respaldo (RF12); el aviso dice que no hay recuperación | Reducido | Remota x Significativa -> **Bajo** | Sí |
| **R5** Brecha del directorio | C-05, C-07, C-08, C-10, C-12, C-13; secreto TOTP cifrado con Fernet y clave fuera de la base | Reducido para el robo de la base sin acceso a su clave de cifrado; incluye estado del factor y hashes de recuperación, pero no contenido ni contraseña. Comprometer también el servidor exige reevaluar el impacto | Remota x Significativa -> **Bajo** | Sí |
| **R6** Conservación | C-10, C-11, C-12; el cifrado hace que lo que quede en Discord sea inservible (*borrado criptográfico*, porque las claves de sesión se destruyen) | Reducido | Remota x Significativa -> **Bajo** | Sí |
| **R7** Transparencia | C-14, C-15, indicadores del estado de la sesión en la interfaz y registro de consentimiento por versión | Reducido | Remota x Significativa -> **Bajo** | Sí |
| **R8** Registros | C-09, C-10 | Reducido | Remota x Significativa -> **Bajo** | Sí |
| **R9** Incumplimiento | C-19, C-24, C-15; documentar la transferencia a Discord y alojar el directorio donde se justifique | Reducido | Remota x Significativa -> **Bajo** | Sí |
| **R10** Token del bot | C-13; permisos mínimos del bot y rotación del token ante cualquier sospecha | Reducido | Remota x Significativa -> **Bajo** | Sí |
| **R11** Robo de la llave | C-03 y C-04; cambio de llave con OAuth2 y TOTP, más la firma de la anterior cuando se aporta, que **alerta a los contactos** (RF8); la PFS protege lo pasado | Reducido; lo futuro no queda protegido hasta que la persona cambie de llave | Remota x Grave -> **Medio** | Sí |
| **R12** Menores | Declaración de mayoría de edad dentro del consentimiento y aviso dirigido a mayores de edad; C-24 (revisar la suficiencia de la declaración antes de ampliar el uso); datos mínimos, nada de perfilado ni publicidad, aviso en lenguaje claro | Reducido | Remota x Significativa -> **Bajo** | Sí |
| **R13** Defecto del protocolo | C-22, C-20; componentes criptográficos estándar, pruebas negativas (comprobadas a mano contra defectos introducidos a propósito); recomendación de auditoría externa | Reducido; **no eliminado** | Remota x Grave -> **Medio** | Sí; la limitación se declara en el informe |
| **R14** Acceso y MFA | C-25; códigos de recuperación fuera del dispositivo, clave TOTP respaldada por separado y recuperación por Discord; instrucciones en [la guía local](../guia/ejecucion-local.md#7-entrar-las-siguientes-veces-y-recuperar-el-acceso) | Reducido; no hay acceso offline habitual. Sin autenticador ni códigos no hay restablecimiento automático. La copia de la base debe restaurarse con su clave de cifrado original | Posible x Significativa -> **Medio** | Sí |

**Criterio para aceptar un riesgo en nivel medio.** Aceptamos un riesgo solo si se cumplen las cuatro condiciones: (1) no puede eliminarse sin dejar de cumplir la finalidad; (2) el beneficio compensa el impacto y no existe una alternativa implementada que mantenga las mismas garantías; (3) la persona lo sabe antes de aceptar, por el aviso y por los indicadores de la interfaz; y (4) existe una mejora recomendada para reducirlo más adelante.

| Riesgo residual aceptado | Por qué no se elimina | Mejora recomendada |
|---|---|---|
| R1 Metadatos | Discord los ve en cualquier uso de la plataforma | Relleno de mensajes a tamaño fijo; un canal por par de contactos |
| R2 Sustitución de llaves | Sin una autoridad confiable, el primer contacto depende de la verificación humana | Registro público de llaves auditable (transparencia de llaves); recordar verificar a quien aún no lo está |
| R3 Dispositivo | Un dispositivo ya comprometido queda fuera de lo que puede garantizar una aplicación | Bloqueo automático por inactividad; llave protegida por hardware |
| R11 Robo de la llave | No hay forma de evitar el robo si el dispositivo se compromete | Mostrar los dispositivos y llaves activos, y facilitar la revocación |
| R13 Defecto del protocolo | Ningún protocolo nuevo es demostrablemente correcto sin una revisión externa | Auditoría externa y verificación formal del protocolo |
| R14 Acceso y MFA | El desbloqueo real exige validar el factor en el directorio; continuar sin él anularía ese control | Continuidad del directorio, custodia de recuperación y simulacro de restauración de PostgreSQL y de la clave TOTP |

**Aceptamos seis riesgos residuales medios** (R1, R2, R3, R11, R13, R14) por las razones expuestas y consignamos nuestros correos como firma en el paso 7. Incluimos las comprobaciones operativas pendientes en el plan de acciones. Estas puntuaciones no suponen una exención legal; revisaremos la necesidad de actuaciones adicionales si cambian el alcance o los riesgos.

---

## Paso 7. Aprobación y registro de resultados

| Elemento | Nombre / cargo / fecha | Notas |
|---|---|---|
| Medidas aprobadas por | Elmer Villegas Suarez ([elmer.villegas@utec.edu.pe](mailto:elmer.villegas@utec.edu.pe)) y Farid Aquino Castro ([farid.aquino@utec.edu.pe](mailto:farid.aquino@utec.edu.pe)); integrantes del equipo; 2026-11-15 | Aprobamos las medidas y consignamos nuestros correos como firma. Incluimos las acciones pendientes en el plan siguiente |
| Riesgos residuales aprobados por | Elmer Villegas Suarez ([elmer.villegas@utec.edu.pe](mailto:elmer.villegas@utec.edu.pe)) y Farid Aquino Castro ([farid.aquino@utec.edu.pe](mailto:farid.aquino@utec.edu.pe)); integrantes del equipo; 2026-11-15 | Aceptamos R1, R2, R3, R11, R13 y R14 por las razones del paso 6 |
| Consejo del delegado | No aplica: no hay delegado designado | Realizamos la revisión interna entre ambos |
| Resumen del consejo | No aplica | No aplica |
| Consejo aceptado o rechazado por | No aplica | No aplica |
| Comentarios | No aplica | No aplica |
| Respuestas de la consulta revisadas por | Elmer Villegas Suarez y Farid Aquino Castro; 2026-11-15 | Completamos la revisión interna e incorporamos las observaciones a esta evaluación |
| Esta DPIA será revisada por | Ambos integrantes | Ante cambios de datos, finalidad, tecnología, proveedor o alcance del servicio |

**Decisión:** aprobamos las medidas y aceptamos los riesgos residuales descritos en el paso 6. El directorio está desplegado en EC2; el cliente y la interfaz se ejecutan en cada dispositivo. Implementamos el borrado local, los derechos ARCO y el MFA del registro y del desbloqueo, que desplegamos y probamos con Microsoft Authenticator. Antes de ampliar el uso con datos de terceros, completaremos las acciones operativas, revisaremos las condiciones de los proveedores y realizaremos el simulacro de incidentes del plan siguiente.

### Plan de acciones pendientes

| Acción | Responsable | Restricción | Para cuándo |
|---|---|---|---|
| Validar TLS, accesos de administración, registros, retención, copias externas y restauración en el despliegue | Infraestructura | C-05 a C-13 | Antes de ampliar el uso |
| Confirmar la región del proyecto Supabase; revisar las condiciones de AWS y Supabase y las garantías de los respaldos en S3 | Equipo | C-24 | Antes de ampliar el uso |
| Completar la recuperación del autenticador en la aplicación; la restauración desde S3 ya recuperó la base y permitió descifrar 1 factor MFA con la clave original, sin probar todavía un inicio de sesión tras la recuperación | Equipo | C-25, R14 | Antes de ampliar el uso |
| Realizar y registrar el simulacro del plan de incidentes | Equipo | C-19 | Antes de la entrega |
| Incorporar un contexto exclusivo para la firma de solicitudes de cancelación | Criptografía y cliente | C-11 | Antes de ampliar el uso |
| Revisar los requisitos del uso con datos de terceros | Equipo | C-24 | Antes de ampliar el uso |

## Referencias

* Autoridad Nacional de Protección de Datos Personales. *Decreto Supremo N.° 016-2024-JUS*. https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus
* Information Commissioner's Office (ICO). *Sample DPIA template*. Reino Unido.
* Congreso de la República del Perú (2011). *Ley N.° 29733, Ley de Protección de Datos Personales*. Y su reglamento, aprobado por el Decreto Supremo N.° 016-2024-JUS.
* Deng, M., Wuyts, K., Scandariato, R., Preneel, B., & Joosen, W. (2011). A privacy threat analysis framework: supporting the elicitation and fulfillment of privacy requirements. *Requirements Engineering, 16*(1), 3–32. https://doi.org/10.1007/s00766-010-0115-7
* Cavoukian, A. (2009). *Privacy by Design: The 7 Foundational Principles*. Information and Privacy Commissioner of Ontario.
* National Institute of Standards and Technology (2025). *Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile* (SP 800-61 Rev. 3).
