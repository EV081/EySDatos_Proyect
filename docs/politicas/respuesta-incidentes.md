# Plan de respuesta a incidentes

**Versión 1.6, 22 de noviembre de 2026.** El plan cubre el directorio en EC2, el MFA de registro y desbloqueo, los contactos y los criterios de notificación. También reúne los escenarios de brecha, las entidades afectadas y los puntos únicos de falla (sección 2). Sigue NIST SP 800-61 rev. 3 (2025): Gobernar, Identificar y Proteger como preparación; Detectar, Responder y Recuperar durante el incidente, con mejora continua. El plan corresponde a la medida C-19 de la DPIA; el simulacro y la validación de los contactos operativos forman parte de las acciones pendientes.

**Alcance.** Directorio en EC2, Virginia del Norte, Estados Unidos (`us-east-1`), y PostgreSQL alojado en Supabase; respaldos, certificados y cuenta AWS; clientes locales, frontend y bots de Discord. Las copias cifradas se alojan en el bucket privado S3 `proyecto-eticayseguridad`, en Virginia del Norte (`us-east-1`). No se incluyen IP, credenciales ni tokens en este documento.

**Regla de notificación.** Evaluamos los supuestos de los artículos 34 a 36 del [reglamento de la Ley 29733, DS 016-2024-JUS](https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus). Documentamos todo incidente y evaluamos las obligaciones de comunicación de cada caso. La sección 5 fija los criterios.

## 1. Gobernar: roles y contactos

| Rol | Quién | Responsabilidad |
|---|---|---|
| Coordinación del incidente | Integrante de turno del equipo; el otro actúa como suplente | Declara el incidente, asigna tareas, lleva la bitácora y decide la notificación |
| Responsable técnico de criptografía y cliente | Área de cliente y criptografía | Evalúa el impacto en el protocolo, en el cliente y en las llaves de las personas |
| Responsable técnico de infraestructura | Área de infraestructura | Directorio, base de datos, TLS, copias, registros y bots |
| Contacto con la ANPD y con las personas afectadas | El responsable del banco de datos (el equipo) | Envía las notificaciones y responde consultas |

**Contactos:** ANPD (Autoridad Nacional de Protección de Datos Personales, Ministerio de Justicia y Derechos Humanos), por su mesa de partes virtual. Discord: Trust & Safety, para la revocación de bots o los abusos de la plataforma. Contactos del equipo: [elmer.villegas@utec.edu.pe](mailto:elmer.villegas@utec.edu.pe) y [farid.aquino@utec.edu.pe](mailto:farid.aquino@utec.edu.pe). Para AWS, usar el canal de soporte de la cuenta. Para la base, usamos el soporte y los controles de acceso del proyecto Supabase; debemos documentar su región por separado. Antes del simulacro, debemos comprobar que ambos podemos acceder a esos canales desde un dispositivo seguro.

Realizamos la revisión interna del protocolo y de la DPIA. Aprobamos las medidas y los riesgos residuales descritos en su [paso 7](../dpia/DPIA.md#paso-7-aprobación-y-registro-de-resultados), donde consignamos nuestros correos como firma.

## 2. Identificar y Proteger: preparación

Lo que ya existe y que este plan usa:

| Capacidad | Dónde |
|---|---|
| Registros de auditoría seudonimizados, 90 días | Registro de auditoría del directorio |
| Alertas automáticas | `logs/alerts.jsonl` y el webhook opcional (F5) |
| Copias cifradas, fuera del servidor, con restauración probada | S3 en Virginia del Norte; [procedimiento de copias y restauración](../../ops/backup/README.md) |
| Revocación del certificado del directorio | `python -m ops.certs.pki revoke` (F2) |
| Cancelación y cambio de llave en el directorio | `DELETE /v1/keys/{id}`, `PUT` con `old_signature` (F1) |
| Detección de secretos y de dependencias vulnerables | CI con gitleaks, pip-audit y npm audit (F6); GitGuardian revisa el repositorio público en GitHub |
| Alerta de cambio de llave a los contactos | Cliente: revoca la verificación y avisa al detectar un cambio de llave |
| Segundo factor y desbloqueo | OAuth2 + TOTP para el registro; desafío firmado + TOTP para desbloquear. Sesión local de 30 minutos por defecto; eventos `mfa_rechazado`, `mfa_recuperacion` y `sesion_local` en la auditoría |
| Inventario de datos y riesgos | [DPIA](../dpia/DPIA.md), sección 6.3 del [informe](../README.md) y secciones 2.1 a 2.3 de este plan |
| Inventario del alojamiento | EC2 en Virginia del Norte (`us-east-1`) y PostgreSQL en Supabase; confirmar la región del proyecto de la base. Respaldos cifrados en S3, Virginia del Norte (`us-east-1`). Mantener los identificadores de instancia, grupos de seguridad y accesos IAM en el registro privado |

**Comprobaciones operativas:** verificar TLS, permisos IAM, acceso de administración restringido y retención en el alojamiento. La tarea de copias está instalada y activa; descargamos una copia cifrada de S3 y la restauramos en PostgreSQL aislado, con 2 registros y 1 factor MFA descifrable mediante la clave original. Nos falta observar una ejecución automática y probar el inicio de sesión del servicio recuperado. Custodiamos la llave privada de la CA y la clave de los respaldos fuera de la instancia.

### 2.1 Escenarios de brecha

La DPIA mira los riesgos desde la privacidad; aquí los miramos desde la seguridad: qué pasa si falla cada componente y a quién afecta. Separar los servicios y cifrar los mensajes busca limitar lo que se expone si uno falla. Esto tiene límites: un directorio alterado puede engañar a quien no verificó la huella, y un dispositivo infectado puede mostrar los mensajes. Por eso también revisamos las llaves y el código.

| # | Escenario | Qué queda expuesto | Impacto | Defensa y estado |
|---|---|---|---|---|
| S1 | Brecha en Discord o intercepción de red | Texto cifrado y metadatos; **no** el contenido | Metadatos (R1) | E2EE con PFS; los metadatos son un límite aceptado |
| S2 | Brecha de la base del directorio | IDs, llaves, fechas y aviso; además, secretos TOTP cifrados, hashes de recuperación y estado del factor | Datos personales y autenticación (R5) | Rol sin DDL, cifrado del secreto con clave externa a la base y copias cifradas; si también se compromete el entorno del servidor, el cifrado del TOTP pierde su protección |
| S3 | Directorio comprometido entrega la llave del atacante | Una conversación completa con quien no verificó | Confidencialidad (R2) | Firmas, verificación, *pin* y alerta; el primer contacto sin verificar sigue expuesto |
| S4 | Robo o infección del dispositivo | Desbloqueado: historial, contactos y claves de sesión. Bloqueado: solo bóveda cifrada | Confidencialidad (R3) | Argon2id, MFA en la aplicación y vencimiento local; una copia de los archivos con la contraseña correcta se abre fuera del cliente y un dispositivo ya comprometido sigue fuera de alcance |
| S5 | Robo de la llave de identidad | Suplantar en sesiones futuras; no descifra lo grabado | Autenticidad (R11) | PFS, alerta de cambio de llave, cancelación del registro |
| S6 | Fuga del token del bot | Lectura del canal cifrado y mensajes falsos (el protocolo los rechaza) | Metadatos y disponibilidad (R10) | Token en entorno, gitleaks en CI, permisos mínimos del bot |
| S7 | Dependencia maliciosa (cadena de suministro) | Todo, **incluido el texto plano** | Confidencialidad total | Pocas dependencias con versión fija, pip-audit, npm audit y SBOM en CI. Es el más difícil de cerrar |
| S8 | Defecto del protocolo o su implementación | Contenido o suplantación | Todo (R13) | Componentes estándar, pruebas de rechazo y tabla de ataques; sin auditoría externa |
| S9 | Fuga de copias o registros | Copias en S3: los datos de S2, incluido el factor cifrado. Registros: eventos con IDs seudonimizados, sin códigos ni secretos | Confidencialidad (R5, R8) | Copias cifradas fuera del servidor, retención de 30 y 90 días |
| S10 | Abuso interno o *phishing* al equipo | Lo que contiene el directorio | Confidencialidad e integridad | Permisos mínimos, auditoría, verificación; el operador no ve contenido |
| S11 | Página maliciosa contra la API local | Con la app desbloqueada, leer chats y enviar mensajes | Confidencialidad e integridad | Token por ejecución, CORS restringido y validación de `Host` |
| S12 | Caída de Discord o del directorio | Discord: se retrasan mensajes. Directorio: falla el próximo desbloqueo y no se abre el historial desde la aplicación | Disponibilidad y acceso local (R14) | Cola y reintentos para mensajes; el desbloqueo real no continúa sin MFA. La sesión ya abierta conserva solo el plazo restante |

### 2.2 Entidades afectadas

| Entidad | Cómo le afecta | Qué le toca hacer |
|---|---|---|
| **Persona usuaria** | Pierde confidencialidad, puede ser suplantada y se revela con quién habla | Cuidar su dispositivo y contraseña, exportar su identidad, verificar |
| **Contactos** | Sus mensajes se exponen aunque su dispositivo esté seguro | Verificar la huella y atender alertas |
| **Terceros mencionados** | Sus datos aparecen en chats que no controlan | No hay medida técnica; por eso se protege el dispositivo |
| **Menores de edad** | Podrían declarar una edad que no tienen y no comprender el riesgo | Servicio para mayores de edad con declaración obligatoria, sin comprobación documental |
| **Equipo responsable** | Debemos evaluar y documentar la brecha y comunicarla según los supuestos del art. 34 del reglamento | Este plan, auditoría y evidencia |
| **Discord** | Puede revocar el bot o suspender el canal si se abusa de su API | Cumplir sus condiciones |
| **Institución vinculada al proyecto** | Su nombre queda ligado al proyecto si hay una brecha con datos reales | Completar las acciones de la DPIA antes de ampliar el uso con datos de terceros |
| **ANPD** | Recibe notificaciones y puede sancionar | Recibirlas a tiempo |
| **Proveedores de alojamiento (AWS EC2, S3 y Supabase)** | Un incidente puede afectar al directorio, a la base o a su disponibilidad | Revisar accesos y condiciones de AWS y Supabase, región del proyecto Supabase y copias cifradas en S3 (`us-east-1`) |

### 2.3 Puntos únicos de falla

* **La contraseña maestra** protege con cifrado la bóveda, el historial, los contactos y los mensajes en espera. El TOTP limita el desbloqueo desde la aplicación, pero no el descifrado de una copia con la contraseña.
* **El dispositivo desbloqueado** junta texto plano, claves de sesión y token de la API local (S4, S7, S11).
* **El directorio** concentra la publicación de llaves y la validación del segundo factor. La huella limita la sustitución de llaves (S3), pero una caída también impide nuevos desbloqueos (S12).
* **El autenticador y su recuperación** son necesarios para el acceso habitual. La clave `TOTP_ENCRYPTION_KEY` debe conservarse fuera de la instancia junto con un procedimiento para restaurarla sin publicarla.
* **El directorio depende de EC2 y de Supabase.** Una caída de cualquiera puede impedir la validación del segundo factor. Un compromiso de EC2 puede exponer las credenciales con las que se accede a la base de Supabase, aunque los servicios estén separados.
* **Directorio y copias en el mismo servidor** convertirían una pérdida de la instancia en pérdida de ambos. Por eso guardamos las copias cifradas en S3, fuera de EC2. Ambos servicios están en `us-east-1`: esta separación no equivale a un respaldo en otra región.
* **Un mismo operador para el servidor y el bot** vería metadatos y datos del directorio, pero nunca el contenido.

## 3. Detectar: fuentes y clasificación

**Fuentes:** alertas del directorio (`acceso_ajeno`, firmas inválidas repetidas, enumeración, cambios de llave), fallos de la CI (gitleaks, pip-audit), alertas de GitGuardian sobre el repositorio, avisos de una persona usuaria (por ejemplo, "me salió una alerta de cambio de llave que yo no hice"), avisos de Discord y de terceros, y la revisión diaria de alertas.

**Severidad:**

| Nivel | Criterio | Ejemplos | Tiempo para empezar a responder |
|---|---|---|---|
| **Crítico** | Se expone el contenido de los mensajes, una llave privada o la llave de la CA, o hay una sustitución de llaves en curso | S3, S4 con muchas personas, S7, fuga de `ca.key` | Inmediato |
| **Alto** | Se exponen datos personales del directorio o de las copias, o se filtra un token o un secreto del servidor | S2, S6, S9, fuga de `.env`, robo del factor o de `TOTP_ENCRYPTION_KEY` | Antes de 4 h |
| **Medio** | Hay un intento detectado sin exposición confirmada | Alerta de enumeración, `acceso_ajeno` aislado, dependencia vulnerable sin explotación conocida | Antes de 24 h |
| **Bajo** | Hay una indisponibilidad sin exposición | S12 | Siguiente día hábil |

Desplegamos y probamos el MFA del registro y del desbloqueo con Microsoft Authenticator. Restauramos una copia de S3 en una base aislada y desciframos un factor MFA con la clave TOTP original. Nos falta probar el inicio de sesión del servicio recuperado y realizar el simulacro del anexo B.

**Referencias de escenarios:** S1 a S12 corresponden a la tabla de la sección 2.1.

**Reloj legal:** cuando el incidente cumple los supuestos de notificación, el plazo máximo de 48 horas corre desde que **conocemos o tenemos constancia** del incidente, no desde que termina la investigación. La primera entrada de la bitácora registra la fecha y hora de ese momento (T0).

## 4. Responder

### 4.1 Pasos generales

1. **Declarar** el incidente: abrir la bitácora (plantilla en el anexo A) con T0, quién lo detectó y la severidad inicial.
2. **Preservar evidencia sin retrasar la contención urgente:** copiar registros y calcular SHA-256; guardar fecha, origen y custodio. En EC2, preservar el estado y los registros relevantes en un destino con acceso restringido y separado de la instancia afectada; crear una instantánea si corresponde. No copiar secretos a la bitácora pública ni borrar evidencia. Documentar el plazo excepcional de conservación y eliminarla al cerrar su finalidad.
3. **Contener** según la guía del escenario (4.2).
4. **Evaluar el impacto:** qué datos, de cuántas personas, desde cuándo, y si el riesgo para ellas es alto. Usar el inventario de la DPIA y las entidades afectadas de la sección 2.2.
5. **Decidir y registrar las comunicaciones** de la sección 5 según los datos y derechos afectados, aunque todavía falte parte de la investigación.
6. **Erradicar y recuperar** (sección 6).
7. **Cerrar** con la revisión posterior (sección 7).

### 4.2 Guías por escenario

| Escenario | Contener | Erradicar y recuperar | ¿Notificar a la ANPD? |
|---|---|---|---|
| **EC2 o cuenta AWS comprometida** | Desde un equipo seguro, restringir la instancia mediante sus grupos de seguridad y revocar las credenciales de administración comprometidas. Aislar sin destruir evidencia | Revisar IAM, accesos, volúmenes y cambios de configuración; recrear la instancia desde una base limpia y restaurar una copia verificada. Rotar las credenciales de acceso a Supabase que estuvieran en la instancia y revisar el esquema y los registros de la base por cambios no autorizados | Evaluar datos y derechos afectados con la sección 5; el alojamiento remoto no cambia los plazos |
| **S2 / S9: brecha de la base o de las copias** | Detener el directorio; cambiar las contraseñas de los roles de Postgres; revocar el acceso del atacante | Restaurar desde la última copia verificada en un servidor limpio (`backup restore`); rotar `BACKUP_KEY` y `PSEUDONYM_KEY` si estuvieron expuestas; conservar la clave que descifra los secretos TOTP o recifrarlos de forma controlada; revisar los registros por cambios de llave en la ventana del incidente | Evaluar art. 34.1: ID, llave, fechas y estado de autenticación son datos personales; documentar volumen, sensibilidad y perjuicio |
| **S3: el directorio sustituye llaves** (alertas de `cambio_de_llave` no reconocidos o reportes de personas) | Detener el directorio; avisar por el canal del proyecto (fuera del directorio) que **nadie inicie conversaciones con contactos sin verificar** | Comparar las llaves con la última copia previa al incidente; restaurar las legítimas; pedir a las personas afectadas que repitan la verificación | Evaluar art. 34.1 y avisar a las personas según 34.3 si afecta sus derechos |
| **Fuga de `server.key` o de la llave de la CA** | Certificado: `pki revoke <serial>` + `pki issue`, y distribuir `crl.pem`. CA: detener el directorio | CA: crear una nueva (`pki init` en otra carpeta), distribuir el nuevo `ca.pem` por un canal confiable y revisar si hubo emisiones no autorizadas | Evaluar el acceso posible y los datos afectados; no esperar a demostrar cada lectura si ya se conoce el incidente |
| **R14: pérdida del autenticador** | Bloquear la aplicación; comprobar que la persona conserva acceso a Discord y un código de recuperación. No pedir ni publicar el código en un issue o chat | La persona inicia sesión con Discord y usa el código para vincular otro autenticador. El factor y los códigos anteriores dejan de servir. Si faltan ambos medios, no hay un restablecimiento automático que omita MFA | Evaluar si fue una pérdida o un robo con uso indebido y aplicar la sección 5 |
| **Fuga de `TOTP_ENCRYPTION_KEY` o del secreto de un factor** | Restringir accesos al directorio y a la base; conservar evidencia sin copiar secretos a la bitácora. Evaluar uso indebido del factor y de los tokens ya emitidos | Si se dispone de la clave anterior, diseñar y ejecutar el recifrado de los secretos con una nueva clave. Cambiar solo la variable no recifra los registros. Ante exposición del secreto de una persona, gestionar una nueva vinculación mediante una recuperación verificada; no habilitar un acceso sin factor | Evaluar exposición de datos de autenticación, otras credenciales y derechos afectados según la sección 5 |
| **R14 / S12: caída del directorio o pérdida de la clave TOTP** | Avisar que el próximo desbloqueo no podrá validarse. No cambiar la configuración del cliente real para omitir MFA | Recuperar el directorio en EC2, restablecer la conexión con Supabase y conservar o restaurar la base con la clave TOTP original desde respaldos separados. Verificar reloj, factor, nonce de propósito `unlock` y vencimiento local. Sin la clave no se puede validar el factor conservado en la base | Documentar el impacto en el acceso a los datos y evaluar el art. 34; indisponibilidad no equivale por sí sola a divulgación |
| **S6: fuga del token de un bot** | Developer Portal -> *Reset Token*; quitar el bot del servidor si hay abuso | Actualizar `DISCORD_TOKEN`; revisar el canal por mensajes inyectados (el protocolo los rechaza) | Evaluar también los metadatos personales: el cifrado del contenido no excluye la obligación de comunicar |
| **Secreto publicado en el repositorio** (alerta de GitGuardian o de gitleaks) | Determinar qué protege el secreto y si se usa en otro lado; si protege algo real, rotarlo **antes** de tocar el repositorio | Sacar el secreto del código (variables de entorno, `secrets` de GitHub o generación por ejecución); agregar una regla de gitleaks si no lo detectó; no reescribir el historial publicado salvo que el secreto siga vigente y no se pueda rotar | Evaluar si el secreto daba acceso a datos personales y registrar el resultado, incluso si no corresponde notificación |
| **Fuga del `.env`** (secretos del servidor) | Rotar los secretos expuestos según el calendario de uso seguro; para `TOTP_ENCRYPTION_KEY`, preservar la anterior hasta recifrar o reconstruir de forma controlada los factores | Revisar el historial de git (gitleaks), los registros y los accesos a la base | Si hay indicios de acceso a la base, tratar como S2 |
| **S5 / S4: la llave o el dispositivo de una persona** | La persona cancela su registro o publica una llave nueva desde otro dispositivo; sus contactos reciben la alerta | La persona crea una identidad nueva y repite las verificaciones | Asistir a la persona; evaluar el tratamiento bajo responsabilidad del equipo y los criterios de la sección 5, sin descartar el incidente solo por ocurrir en un dispositivo personal |
| **S7 / S8: dependencia maliciosa o defecto del protocolo** | Retirar la versión afectada; avisar a las personas que bloqueen la aplicación hasta actualizar | Corregir, agregar una prueba que reproduzca el defecto, publicar una versión nueva y pedir rotar las sesiones (las sesiones viejas se descartan al rotar) | Evaluar los datos, las personas y los derechos afectados conforme al art. 34 |
| **S1: brecha en Discord o intercepción de red** | Confirmar con Discord el alcance; comprobar que en el canal solo hay mensajes `E2EE1:` y que ningún cliente aceptó mensajes alterados (se marcan "no descifrable") | No hay llaves que rotar: el contenido sigue cifrado y la PFS protege lo pasado. Si se sospecha que alguien suplantó un *handshake*, pedir a las personas que repitan la verificación de la huella | Evaluar los metadatos expuestos (quién habló con quién y cuándo) como datos personales según la sección 5 |
| **S10: abuso interno o *phishing* al equipo** | Revocar de inmediato las sesiones y credenciales de la persona afectada (AWS, Supabase, GitHub, Discord Developer Portal) y cambiar sus contraseñas desde un equipo seguro | Revisar en la auditoría cambios de llave, cancelaciones y accesos en la ventana del incidente; restaurar llaves alteradas desde la última copia verificada; rotar los secretos que esa persona podía ver según el calendario de uso seguro | Evaluar art. 34.1 si hubo acceso a la base o a las copias; el contenido de los mensajes no está al alcance del operador |
| **S11: página maliciosa contra la API local** | La persona bloquea la aplicación y detiene el cliente local; se genera un `CLIENT_API_TOKEN` nuevo | Revisar que `CLIENT_ALLOWED_ORIGIN` sea el origen del frontend; si se enviaron mensajes en su nombre, avisar a esos contactos por otra vía. Si el ataque explotó un defecto del cliente, tratarlo como S8 | Evaluar si se leyeron chats de terceros y aplicar la sección 5 |
| **Enumeración o `acceso_ajeno`** | Bajar los límites de solicitudes; bloquear el origen en el firewall si persiste | Revisar si algún intento tuvo éxito (cambios de llave en la ventana) | No, salvo que haya tenido éxito |

## 5. Notificación

### 5.1 Decisión y plazos

| Destinatario | Cuándo corresponde | Plazo y evidencia |
|---|---|---|
| ANPD | Art. 34.1: exposición de grandes volúmenes por cantidad o tipo, gran número de personas, datos sensibles o perjuicio evidente a otros derechos o libertades | Máximo 48 horas desde conocimiento o constancia. Registrar envío y acuse; resolver internamente el incidente no elimina la obligación |
| Personas afectadas | Art. 34.3: el incidente afecta a la persona en otros derechos | Dentro de las 48 horas, sin dilación indebida, en lenguaje claro. Evaluar la excepción del art. 34.4 si no hubo esa afectación y las medidas lo superaron totalmente |
| Centro Nacional de Seguridad Digital (CNSD) | Art. 34.5: incidente de datos personales en o mediante el entorno digital | Incluir la comunicación en la respuesta junto con la de la ANPD; registrar el canal y el acuse |
| Responsable del tratamiento | Art. 36: aviso del encargado cuando conoce un incidente | De forma inmediata; documentar cuándo informó el proveedor |
| AWS, Supabase o Discord | Cuando el incidente requiere contención o asistencia de su servicio | Abrir un caso por un canal de soporte verificado; conservar el identificador |

La coordinación deja por escrito la decisión de notificar o no, los hechos y el artículo aplicado. Documentamos todo incidente conforme al art. 35. No esperamos al resultado final de la investigación para iniciar las comunicaciones obligatorias. Si una comunicación supera el plazo, registramos y comunicamos los motivos y el sustento de la demora.

### 5.2 Contenido y canal

La notificación incluye:

* Naturaleza del incidente, fecha y hora del conocimiento (T0), categorías de datos y número aproximado de personas afectadas.
* Consecuencias probables y medidas adoptadas o propuestas para reducir el daño.
* Contactos del equipo: elmer.villegas@utec.edu.pe y farid.aquino@utec.edu.pe.
* Información todavía desconocida y cómo se completará, sin inventar cantidades ni afirmar que el cifrado elimina todo riesgo.

Usamos el canal oficial vigente de la ANPD y del CNSD, lo verificamos al enviar y guardamos el acuse. Escribimos a las personas por un medio que no dependa del componente comprometido: qué pasó, qué datos afecta y qué deben hacer (bloquear la aplicación, renovar credenciales o verificar de nuevo sus contactos). No incluir llaves, tokens ni datos de terceros en mensajes públicos.

## 6. Recuperar

* En EC2, reconstruir desde una imagen limpia y revisar IAM y grupos de seguridad. En Supabase, revisar accesos y el estado de la base; coordinar una restauración verificada cuando sea necesaria. Comprobar la conexión TLS entre ambos servicios. No asumir que el procedimiento de restauración de un PostgreSQL local se puede ejecutar con los mismos permisos en Supabase. Restaurar el servicio desde un estado limpio: copia verificada (`backup verify`), secretos rotados y certificado nuevo.
* Confirmar que el servicio funciona: la CI en verde, `discord_adapter.check` y `discord_adapter.smoke` sin problemas, y una consulta de llave por HTTPS con la CA vigente, renovada si se comprometió.
* Probar registro y desbloqueo con Authenticator: un código nuevo se acepta, el mismo código se rechaza al reutilizarlo y una caída de validación mantiene el historial bloqueado. La restauración no debe reactivar tokens o nonces viejos; el estado temporal no se restaura. Revisar también los pasos TOTP y códigos de recuperación que contenga una copia antigua y documentar cómo se evita reactivar factores o códigos revocados.
* Vigilar con más atención (revisar las alertas cada hora) durante 7 días.
* La cancelación que pidió una persona afectada se aplica también a las copias, a más tardar en 30 días (rotación).

## 7. Mejora continua: revisión posterior

Dentro de los 7 días siguientes al cierre, sin buscar culpables:

* Cronología con los tiempos (T0, contención, notificación, recuperación).
* Qué funcionó, qué no y por qué se detectó (o no) antes.
* Acciones con responsable y fecha: nuevas pruebas, reglas de alerta o cambios a las políticas.
* Actualizar la DPIA (riesgos y puntuaciones) y este plan.

## 8. Ejercicios

* **Simulacro en papel** cada semestre, y antes de ampliar el uso. Escenario sugerido: "llega una alerta de 3 cambios de llave en una hora y una persona reporta que su contacto ya no está verificado". Recorremos las secciones 4 a 6 con el plazo de 48 h en curso y registramos los resultados en el anexo B. Incluir pérdida de autenticador, indisponibilidad de EC2 y restauración de PostgreSQL con su clave de cifrado TOTP; la copia de la base por sí sola no basta.
* **Restauración real** de una copia cada semana (`backup verify`, automatizable) y una restauración completa sobre un servidor limpio cada semestre.

---

## Anexo A: bitácora del incidente

| Campo | Valor |
|---|---|
| Identificador | INC-AAAA-NN |
| T0 (se conoce el incidente) | AAAA-MM-DD hh:mm (UTC-5) |
| Detectado por / fuente | |
| Escenario y severidad inicial | |
| Evidencia preservada (archivo y SHA-256) | |
| Acciones de contención (hora y quién) | |
| ¿Brecha de datos personales? ¿Cuántas personas? | |
| Decisión ANPD: supuesto del art. 34.1, hora, medio y acuse | Si corresponde: límite T0 + 48 h |
| Comunicación CNSD: hora, medio y acuse | Evaluar art. 34.5 |
| Aviso a las personas: criterio, hora, medio y acuse | Evaluar arts. 34.3 y 34.4 |
| Estado del segundo factor, tokens y clave de cifrado TOTP | Registrar alcance y medidas, nunca códigos, hashes ni claves en la bitácora pública |
| Recursos de EC2, base y respaldos afectados | Identificadores en registro privado, sin credenciales |
| Recuperación confirmada (hora) | |
| Revisión posterior (fecha y enlace) | |

## Anexo B: registro de simulacros

| Fecha | Escenario | Participantes | Tiempo hasta la decisión de notificar | Hallazgos y acciones |
|---|---|---|---|---|
| Pendiente: primer simulacro antes de la entrega | | | | |

## Anexo C: incidentes registrados

### INC-2026-01: contraseñas de la CI publicadas en GitHub

| Campo | Valor |
|---|---|
| T0 (se conoce el incidente) | 2026-11-01 18:48 (UTC-5), minutos después del primer push de la rama |
| Detectado por / fuente | GitGuardian (dos alertas *Generic Password*, severidad alta, etiqueta *Publicly exposed*) |
| Escenario y severidad inicial | Secreto publicado en el repositorio. **Alta** por la regla de la sección 3 (se filtra un secreto) |
| Qué se expuso | `ci-postgres`, `ci-app` y `ci-backup` en `.github/workflows/ci.yml` (commits `c5d3f62` a `8c686ff`): contraseñas de la base PostgreSQL efímera de la CI |
| Evaluación del impacto | Protegían una base que solo existe dentro del runner de GitHub durante la ejecución y se destruye al terminar; no se usan en `.env` ni en ningún otro sistema (verificado). Severidad reclasificada a **baja**: sin acceso posible a datos |
| ¿Brecha de datos personales? | **No.** La base de la CI solo tiene datos sintéticos de las pruebas |
| Contención y erradicación | 18:54, commit `f91eb27`: la CI genera tres contraseñas aleatorias por ejecución (`openssl rand`), las enmascara en los registros (`::add-mask::`) y levanta Postgres en un paso en lugar de como servicio |
| Notificación a la ANPD | No corresponde (sin datos personales) |
| Recuperación confirmada | Run 41364404833 de la CI: las pruebas pasan con las contraseñas aleatorias; gitleaks sin hallazgos |
| Cierre en GitGuardian | *Resolve -> Secret revoked* |

**Revisión posterior.**

* **Por qué pasó:** consideramos inofensivas las contraseñas de las bases efímeras de CI y las escribimos en el workflow. Nuestra política 2.2 ("no versionamos secretos") no hacía excepciones, y aun así la incumplimos.
* **Por qué no lo detectamos antes:** las reglas por defecto de gitleaks ignoran contraseñas cortas y de baja entropía. La CI pasaba en verde con el secreto adentro.
* **Qué funcionó:** la detección externa (GitGuardian) llegó a los minutos; acotamos el impacto rápidamente porque la base era efímera y no reutilizábamos las contraseñas.
* **Acciones:**

| Acción | Responsable | Estado |
|---|---|---|
| Contraseñas aleatorias por ejecución en la CI | Operaciones | Completado `f91eb27` |
| Regla `password-en-configuracion` en `.gitleaks.toml`, probada con un canario (detecta valores fijos; ignora vacíos, `${{ secrets.* }}` y `${VAR}`) | Operaciones | Completado `f91eb27` |
| Registrar el hallazgo en la clasificación de `ops/reports/README.md` | Operaciones | Completado |
| Política 2.2: ni siquiera las credenciales de prueba o de CI se escriben en archivos versionados | Operaciones | Completado versión 1.1 |
| No reescribir el historial: el valor ya no protege nada y la rama es compartida | Equipo | Decidido |

## Referencias

* Autoridad Nacional de Protección de Datos Personales. (2024). [Decreto Supremo N.° 016-2024-JUS, reglamento de la Ley 29733](https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus), arts. 34 a 36.
* NIST. (2025). *Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile* (SP 800-61 Rev. 3). https://doi.org/10.6028/NIST.SP.800-61r3
