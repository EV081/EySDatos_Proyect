# Informe del Proyecto: Mensajería Cifrada en Discord

## 1. Motivación

Discord no cifra de extremo a extremo: la empresa puede leer los mensajes. Nuestro proyecto agrega una capa de cifrado para que Discord solo guarde texto que no puede leer. La motivación completa está en la sección 1 de la [primera entrega](primera-entrega.md).

## 2. Trasfondo teórico

El diseño se apoya en el cifrado de extremo a extremo (E2EE) y en la criptografía híbrida: AES-256-GCM cifra y autentica los mensajes, Ed25519 firma y X25519 acuerda claves efímeras para tener *forward secrecy* (PFS). SHA-256, HKDF y Argon2id cubren la huella, la derivación de claves y la protección de la contraseña. Un directorio publica las llaves, y la verificación fuera de banda detecta si las sustituye. El MFA con TOTP protege el acceso desde la aplicación. La explicación completa, con sus referencias, está en la sección 2 de la [primera entrega](primera-entrega.md).

## 3. Requerimientos

El modelo de amenaza y la lista completa de requerimientos de la primera entrega están en la sección 3 de la [primera entrega](primera-entrega.md). En resumen, consideramos adversarios a Discord, a quien acceda a sus servidores y a atacantes pasivos o activos en la red (Dolev y Yao, 1983), y dejamos fuera los metadatos, la disponibilidad y el compromiso físico del dispositivo.

* **Funcionales (RF1–RF14):** generar la identidad Ed25519 en el dispositivo y publicarla en un directorio; acordar una clave de sesión con Diffie-Hellman efímero autenticado; cifrar cada mensaje antes de enviarlo y descifrar los entrantes; mostrar la huella, verificar contactos fuera de Discord y alertar si cambia la llave de uno verificado; indicar el estado de cada conversación; autenticarse ante Discord sin exponer credenciales; marcar los mensajes no descifrables; exportar e importar la identidad; y encolar los mensajes hasta que haya sesión.
* **De seguridad (RS1–RS15):** la llave privada no sale del dispositivo y se guarda cifrada con Argon2id; el texto plano no va a registros ni a archivos temporales; AES-256-GCM con nonce de 96 bits y rechazo de etiquetas inválidas; TLS 1.3 con el directorio; verificación fuera de banda con huella SHA-256; rotación de claves; tokens en variables de entorno; CSPRNG; *forward secrecy*; firmas del *handshake* con contexto por rol; rechazo de mensajes repetidos o de otra sesión; y un único propósito por llave.

La tabla de [trazabilidad](trazabilidad/trazabilidad.md) muestra el texto de cada requerimiento junto con su evidencia.

### 3.1. Requerimientos agregados durante la implementación

Al construir el directorio y las operaciones, identificamos requerimientos que habíamos dejado implícitos en la primera versión. Los derivamos del modelo de amenaza (el directorio como adversario, sección 3) y de la DPIA (restricciones C-05 a C-12). Relacionamos cada uno con sus pruebas en la [tabla de trazabilidad](trazabilidad/trazabilidad.md).

* **RF15:** La persona debe poder cancelar su registro en el directorio desde su cliente, con su llave vigente y una sesión OAuth2; el registro se borra en el acto y desaparece de las copias en 30 días como máximo.

* **RS16:** Publicar, cambiar o cancelar una llave debe exigir a la vez la prueba de posesión de la llave privada (firma sobre un nonce de un solo uso, con propósito y caducidad) y el vínculo OAuth2 con el mismo ID de Discord; solo el dueño de un ID puede modificar su registro.

* **RS17:** El directorio debe operar con un rol de base de datos sin permisos de DDL ni de superusuario, usar solo consultas parametrizadas, limitar las solicitudes por origen y responder con errores genéricos. La consulta pública de llaves (RF2) indica si un ID está registrado; para frenar la enumeración, se limita por IP y se alerta ante muchas consultas de IDs inexistentes.

* **RS18:** Por defecto, el cliente debe confiar únicamente en la CA propia del proyecto para conectarse al directorio y rechazar certificados vencidos o de otro nombre; si se configura la CRL (`DIRECTORY_CRL_FILE`), también los revocados. No debe ofrecer ninguna opción para continuar ante un certificado inválido. Solo con `DIRECTORY_PUBLIC_CA=1`, pensado para un directorio detrás de una plataforma con certificado público, confía en las CA del sistema, manteniendo TLS 1.3 y la verificación del nombre.

* **RS19:** Los registros de auditoría no deben contener texto de mensajes, llaves, tokens, IPs ni IDs en claro (los IDs se seudonimizan con HMAC); deben alimentar alertas ante abusos y conservarse 90 días.

* **RS20:** El directorio debe respaldarse a diario con copias cifradas, guardadas fuera de su servidor, con restauración probada y rotación de 30 días.


## 4. Diseño

El diseño funcional (interfaz y experiencia de usuario) y el diseño de seguridad (arquitectura, algoritmos, protocolos, verificación, análisis de ataques y respaldo) están completos en la sección 4 de la [primera entrega](primera-entrega.md).

## 5. Implementación

La implementación propuesta (esquema criptográfico, tecnologías, fases de ejecución y limitaciones reconocidas) está en la sección 5 de la [primera entrega](primera-entrega.md). Aquí describimos lo que logramos implementar.

### 5.1 Implementación lograda

Implementamos todos los componentes de la arquitectura descrita en la sección 4.2 de la [primera entrega](primera-entrega.md). El sistema integra la librería criptográfica, el cliente local, el frontend, el directorio, el transporte por Discord y las operaciones. El directorio está desplegado en una instancia de Amazon EC2 en Virginia del Norte, Estados Unidos (`us-east-1`), con PostgreSQL alojado en Supabase y respaldos cifrados en Amazon S3 (`us-east-1`); cada cliente cifra y descifra en su propio dispositivo.

Las pruebas automáticas de cada componente están en la sección 8.1.

| Componente | Qué hace |
|---|---|
| `crypto/` | Identidad, bóveda, *handshake* con PFS, sesión, huella y seudonimización |
| `client/` | API local: orquesta las sesiones, la cola de salida, la rotación y las alertas; desbloqueo con MFA, derechos ARCO, rotación de la llave de firma y quitar contactos |
| `frontend/` | Interfaz en Next.js: identidad, contactos, chat, verificación con código QR, alertas, TOTP al desbloquear y la sección "Mis datos" (derechos ARCO) |
| `directory/` | Directorio de llaves (FastAPI + PostgreSQL 17): OAuth2 y prueba de posesión, MFA con TOTP, consulta del registro propio, cambio de llave, cancelación, TLS 1.3, auditoría y alertas |
| `discord_adapter/` | Un bot por persona sobre `discord.py`; solo publica mensajes `E2EE1:` |
| `ops/` | CA propia, copias cifradas de Supabase a S3, restauración, tarea diaria, análisis de código y trazabilidad |

**Cómo cumplimos lo propuesto y qué decisiones tomamos:**

* **Vínculo con la cuenta de Discord (RS16).** El contrato del cliente con el directorio no lleva credenciales, así que el **directorio** hace el flujo OAuth2 (código de autorización con `state` y PKCE, alcance `identify`). Lee el ID, revoca enseguida el token de Discord y entrega un token de registro propio de 10 minutos, de un solo uso y ligado a ese ID. Así el token de Discord nunca llega al cliente, y el cliente no tuvo que cambiar.
* **Cambio y cancelación de llaves.** Un cambio con OAuth2 guarda la llave anterior 90 días y dispara la alerta de RF8 en los contactos; si además viene la firma de la llave anterior (`sign_key_change`), se exige que valga. La cancelación se firma, de forma provisoria, como un "cambio hacia la llave nula" con un nonce reservado para cancelar.
* **TLS 1.3 (RS6, RS18).** Una CA propia (ECDSA P-256), un certificado de servidor de 90 días y una CRL. Por defecto el cliente no usa las CA del sistema: así, ninguna CA pública puede emitir un certificado para el directorio. La opción `DIRECTORY_PUBLIC_CA=1` existe para un despliegue detrás de una plataforma y no se usa en EC2.
* **Transporte.** Los mensajes se entregan al cliente desde un hilo propio, porque el cliente responde con `send()` mientras procesa un mensaje y entregarlos desde el bucle de `discord.py` produciría un bloqueo mutuo. El adaptador se niega a publicar cualquier texto que no sea del protocolo.
* **Derechos ARCO en el directorio.** La persona consulta todo lo que el directorio guarda de ella (`GET /v1/me`, con su sesión OAuth2 y solo su propio registro), cambia su llave y cancela su registro. El cliente y la sección "Mis datos" del frontend lo exponen; el detalle está en la [política de privacidad](privacidad/politica-de-privacidad.md).

**Ensayos con servicios reales.** Probamos el adaptador con la API real de Discord, el login OAuth2 con una cuenta real y una conversación entre dos clientes con su propio bot; los resultados están en la sección 8.3.

### 5.2 Operaciones, políticas e incidentes

| Área | Qué implementamos | Dónde |
|---|---|---|
| Certificados | CA de 5 años con la llave cifrada; certificado de 90 días (se renueva a los 60); CRL de 30 días; revocación | [ops/certs](../ops/certs/README.md) |
| Copias de seguridad | `pg_dump` con rol de lectura y AES-256-GCM; subida a S3 con verificación y limpieza de 30 días. Copia real a S3 verificada y restaurada en PostgreSQL aislado: 2 registros y 1 factor MFA descifrable ([evidencia](../ops/reports/f4-s3-smoke.txt)). Cron está configurado y activo; falta observar una ejecución automática. RPO 24 h y RTO 30 min son objetivos | [ops/backup](../ops/backup/README.md) |
| Registros y alertas | JSON con IDs seudonimizados, filtro de redacción, 90 días; alertas por acceso ajeno, firmas inválidas, enumeración y cambios de llave | [directory/README.md](../directory/README.md) |
| Tarea diaria | Copia, purga de la base y retención de registros en un solo comando programable | `python -m ops.scheduled daily` |
| Análisis de código | Bandit, Semgrep, pip-audit y npm audit con SBOM CycloneDX, y gitleaks, en CI; reportes antes y después | [ops/reports](../ops/reports/README.md) |
| Políticas de uso seguro | Políticas y procedimientos para personas y operadores, calendario de rotación de secretos, y concientización y formación del equipo. El detalle está en el documento enlazado | [politicas/uso-seguro.md](politicas/uso-seguro.md) |
| Política de privacidad | Cumplimiento de la Ley 29733 y su reglamento (DS 016-2024-JUS): principios, derechos ARCO y plazos, nivel de protección del alojamiento y situación de cada obligación legal (aviso, inscripción del banco de datos, oficial de datos, notificación de incidentes). El detalle está en el documento enlazado | [privacidad/politica-de-privacidad.md](privacidad/politica-de-privacidad.md) |
| Riesgos de una brecha y entidades afectadas | 12 escenarios de brecha (S1 a S12) con lo que exponen y su defensa, las entidades afectadas y los puntos únicos de falla. El detalle está en las secciones 2.1 a 2.3 del plan de incidentes | [politicas/respuesta-incidentes.md](politicas/respuesta-incidentes.md#21-escenarios-de-brecha) |
| Plan de respuesta a incidentes | Plan básico ante fuga o pérdida de datos según NIST SP 800-61 rev. 3: roles, severidad, guías por escenario, notificación a la ANPD, a las personas y al CNSD según el art. 34 del reglamento, recuperación y revisión posterior. Incluye el incidente real INC-2026-01. El detalle está en el documento enlazado | [politicas/respuesta-incidentes.md](politicas/respuesta-incidentes.md) |

### 5.3 Protección de datos en reposo y en tránsito

Resumen de las medidas que protegen los datos, agrupadas como las pide el esquema del curso. El detalle de cada una está en la sección 6.3 y en las secciones 4 y 5 de la [primera entrega](primera-entrega.md).

| Medida | En reposo | En tránsito |
|---|---|---|
| **Cifrado** | Bóveda de identidad con Argon2id + AES-256-GCM; historial, contactos y cola en un almacén AES-256-GCM; secreto TOTP cifrado con Fernet y clave fuera de la base; copias del directorio con AES-256-GCM en S3 | Mensajes con AES-256-GCM y claves de un *handshake* X25519 efímero (E2EE con PFS); cliente-directorio con TLS 1.3 y CA propia; directorio-Supabase con TLS (`sslmode=verify-full`); subida de copias por HTTPS |
| **Hashing** | Códigos de recuperación guardados como hashes; seudónimos HMAC-SHA256 de los IDs en la auditoría; SHA-256 de cada copia para verificarla | Huella de verificación SHA-256 sobre ambas llaves; HKDF-SHA256 y confirmación HMAC-SHA256 en el *handshake* |
| **Gestión de accesos** | Contraseña maestra y TOTP para desbloquear, sesión local de 30 min, bloqueo tras 5 intentos; rol de base sin DDL y rol de copias de solo lectura; bucket privado con rol IAM limitado | Publicar, cambiar o cancelar una llave exige OAuth2 + TOTP + firma (RS16); API local con token por ejecución, CORS y validación de `Host`; límite de solicitudes por IP |
| **Registros de auditoría** | JSON con IDs seudonimizados, sin texto, llaves, tokens ni IPs; retención de 90 días; alertas por abuso (RS19) | Sin registro de acceso HTTP en el directorio, para no guardar IPs ni IDs en claro |

## 6. Privacidad y ética

### 6.1 Evaluación de impacto en la protección de datos (DPIA)

Antes de usar datos reales hicimos una DPIA con la plantilla de siete pasos de las autoridades de protección de datos, adaptada a la Ley 29733 (documento completo: [DPIA](dpia/DPIA.md)).

**Qué datos se tratan.** El directorio publica el ID de Discord y la llave pública de firma, y conserva fechas y la versión del aviso. También guarda datos privados de autenticación: secreto TOTP cifrado, hashes de recuperación, contadores de intentos y último paso utilizado. Los mensajes y las llaves privadas no salen del dispositivo. Discord sí puede ver los **metadatos** (quién, a quién y cuándo).

**Riesgos.** Se evaluaron 14 siguiendo el ciclo de vida del dato y las categorías LINDDUN (Deng et al., 2011):

| ID | Riesgo | Inicial | Residual |
|---|---|---|---|
| R1 | Metadatos expuestos a Discord y al canal | Alto | Medio (aceptado) |
| R2 | Sustitución de llaves por un directorio malicioso | Alto | Medio (aceptado) |
| R3 | Robo o infección del dispositivo | Alto | Medio (aceptado) |
| R4 | Contraseña maestra débil o perdida | Medio | Bajo |
| R5 | Brecha de la base de datos del directorio | Medio | Bajo |
| R6 | Conservación excesiva o borrado incompleto | Alto | Bajo |
| R7 | Falta de transparencia hacia las personas | Alto | Bajo |
| R8 | Datos personales en los registros | Medio | Bajo |
| R9 | Incumplimiento legal | Medio | Bajo |
| R10 | Filtración del token del bot | Medio | Bajo |
| R11 | Robo de la llave de identidad | Alto | Medio (aceptado) |
| R12 | Personas menores de edad | Medio | Bajo |
| R13 | Defecto del protocolo sin auditoría externa | Alto | Medio (aceptado) |
| R14 | Pérdida del autenticador o indisponibilidad de la validación remota | Alto | Medio (aceptado) |

**Medidas.** Definimos 25 condiciones de seguridad y privacidad. Cada una se relaciona con una prueba o evidencia. Las principales: E2EE con PFS, verificación fuera de banda con *pin*, cifrado en reposo con Argon2id y bloqueo tras intentos fallidos, directorio mínimo, TLS 1.3 con CA propia, registros con IDs seudonimizados y plazos de retención, consentimiento por versión y desbloqueo con MFA y caducidad local (C-25).

**Decisión.** Revisamos de forma cruzada el proyecto y realizamos la revisión humana del protocolo. Aprobamos la DPIA y aceptamos seis riesgos residuales de nivel medio por las razones expuestas en el paso 6. Consignamos nuestros correos como firma en el paso 7. El directorio está desplegado en EC2 y los clientes se ejecutan localmente. Implementamos el análisis de código, el borrado local y el MFA, que desplegamos y probamos con Microsoft Authenticator. Antes de ampliar el uso, debemos realizar el simulacro de incidentes, completar las comprobaciones operativas del alojamiento y revisar los requisitos de C-24.

### 6.2 Consideraciones éticas

* **Sin acceso excepcional ni llave de custodia.** Es la decisión central. Una llave que deje leer conversaciones a una autoridad o al operador anula la PFS y tarde o temprano se filtra o se usa mal (Abelson et al., 2015). El costo es real: ante una orden solo podemos entregar los datos que realmente conserva el directorio, incluidos sus registros de autenticación, nunca el contenido de los chats, y no podemos ayudar a investigar algo que pase dentro de un chat. El aviso lo dice claro.
* **Las llaves son de la persona.** El servicio no puede restablecer la contraseña maestra. Una exportación previa con otra contraseña conocida permite recuperar la identidad y la clave del almacén; también puede generarse mientras la sesión siga abierta. El historial y los contactos no se incluyen en la exportación: para recuperarlos se necesita además el almacén local cifrado. Sin una sesión abierta ni una exportación utilizable, olvidar la contraseña impide recuperar esos datos. Recuperar el autenticador no recupera la contraseña ni descifra los archivos locales.
* **MFA y disponibilidad.** El segundo factor ya protege el registro y el desbloqueo habitual, pero necesita conexión al directorio. Si se pierde el celular, la recuperación pasa por Discord y un código de recuperación; sin ambos medios no hay restablecimiento automático. Cancelar el registro elimina el factor: si se conservan archivos locales, hay que exportar lo necesario antes de cancelar, porque el próximo desbloqueo habitual no podrá validarse.
* **El directorio concentra confianza.** Quien lo opere podría dar una llave falsa. Por eso guarda lo mínimo, no registra IP, deja rastro de cada cambio de llave y no sustituye llaves. Lo que las reglas no evitan lo limita el diseño: con la verificación fuera de banda cualquiera comprueba que no lo engañan.
* **Advertencias sin "continuar".** Ante un cambio de llave de un contacto verificado no se puede seguir sin volver a verificar. Es algo paternalista, pero en estudios de campo entre un tercio y siete de cada diez personas ignoraron advertencias de certificados que sí dejaban continuar (Akhawe & Felt, 2013).
* **Abuso.** El E2EE protege igual al que conversa en privado y al que acosa; el operador no puede moderar lo que no lee. Cada persona puede bloquear o silenciar con Discord y denunciar mostrando lo que recibió. Un mecanismo de denuncia verificable queda como recomendación.
* **Menores y accesibilidad.** La aplicación está dirigida a mayores de edad y exige esa declaración en el consentimiento. No pide fecha de nacimiento ni documento: la declaración no comprueba la edad. Comparar 60 dígitos puede ser difícil, por eso están los grupos de cinco y el QR.
* **Respeto a la plataforma.** Usamos solo la API oficial con bots, nunca el token de una cuenta personal, y un canal privado creado para el proyecto.

### 6.3 Clasificación de datos y técnicas de privacidad

Cada dato lleva una etiqueta completa con dos partes: la **categoría** dice *qué tipo* de dato es y el **nivel** dice *cuánto* protegerlo (por ejemplo, "Personal · Restringido").

| Dato | Categoría | Nivel | Controles | Dónde |
|---|---|---|---|---|
| Mensajes, historial y cola de salida | Personal + Sensible | **Restringido** | E2EE; texto plano solo en memoria; en reposo AES-256-GCM; desbloqueo con contraseña y MFA | Dispositivo |
| Llave privada, llaves de sesión y archivo de identidad exportado | Confidencial | **Restringido** | Argon2id + AES-256-GCM; llaves de sesión solo en memoria; nunca salen del dispositivo | Dispositivo |
| Contraseña maestra | Confidencial | **Restringido** | No se guarda ni se envía; bloqueo tras 5 intentos fallidos | — |
| Secreto TOTP, códigos de recuperación y `TOTP_ENCRYPTION_KEY` | Confidencial | **Restringido** | Secreto cifrado con Fernet; códigos guardados como hashes; clave fuera de PostgreSQL; fuera de consultas públicas y registros | Directorio y app autenticadora |
| Token del bot y secretos del servidor (`.env`) | Confidencial | **Restringido** | Variables de entorno fuera del repositorio; gitleaks en CI; calendario de rotación | Equipo de la persona y EC2 |
| Copias del directorio | Personal + Confidencial | **Restringido** | Volcado cifrado con AES-256-GCM, bucket privado, verificación SHA-256, rotación de 30 días y claves bajo custodia separada | Amazon S3 (`us-east-1`) |
| ID de Discord | Personal | **Confidencial** | Solo se entrega junto a su llave a quien ya conoce el ID (no se puede listar); límite de consultas; seudonimizado con HMAC en los registros | Directorio |
| Fecha de registro y versión del aviso aceptado | Personal | **Confidencial** | Solo en el directorio; visibles para la propia persona (derecho de acceso) | Directorio |
| Metadatos de mensajes (quién, a quién, cuándo) | Personal | **Confidencial** | No se pueden ocultar; canal privado; el aviso lo declara | Discord |
| Contactos, *pines* y verificación | Personal | **Confidencial** | Solo locales y cifrados en el almacén | Dispositivo |
| Registros de auditoría | Personal (seudonimizado) + Confidencial | **Confidencial** | IDs con HMAC, sin texto, llaves, IPs ni códigos; retención de 90 días; solo los leen los operadores | Directorio en EC2 |
| Mensajes del *handshake* y texto cifrado | Personal (metadatos) | **Interno** | Ilegibles sin las claves; solo visibles para los miembros del canal privado | Discord |
| Llave pública y huella | Público | **Público** | Integridad con TLS, firmas y verificación fuera de banda | Directorio y cliente |
| Aviso y política de privacidad, código fuente | Público | **Público** | Versionados en el repositorio | GitHub y aplicación |

**No recogemos:** nombre, correo, teléfono, foto, nombre de usuario, IP, edad, documento ni ubicación. Lo que no se recoge no hay que cifrarlo, borrarlo ni notificarlo si hay una brecha.

| Técnica | Dónde | Límite |
|---|---|---|
| **Minimización** | El directorio guarda solo lo necesario | Ninguno; es la más barata y fuerte |
| **Cifrado AES-256-GCM** | Mensajes, bóveda, almacén local y copias del directorio en S3 | Todo depende de quién tiene la clave |
| **Firmas y DH efímero** | *Handshake* | No protege un dispositivo ya comprometido |
| **Argon2id con sal** | Contraseña maestra | Una contraseña débil sigue siendo débil |
| **Seudonimización con HMAC-SHA256** | IDs en los registros de auditoría | Sigue siendo dato personal; quien tenga la clave puede calcular el seudónimo |
| **Enmascarado** (`1234…5678`) | Mensajes de diagnóstico y pantallas | No protege datos guardados |
| **Mínimo privilegio** | Rol de base de datos sin DDL, token de API local | Vale solo si la autenticación es buena |
| **Datos falsos en pruebas** | IDs inventados en todos los tests | — |
| Privacidad diferencial | No aplica (ver abajo) | — |
| Tokenización | No aplica: no hay datos de pago | — |
| Anonimización de registros | No se pretende: no publicamos datos fila por fila ni estadísticas | — |

**Por qué no aplicamos privacidad diferencial.** Los únicos datos del directorio que servirían para estadísticas de uso son dos columnas: la fecha de registro y la versión del aviso de privacidad que la persona aceptó. Ninguna es de nivel restringido ni sensible (tabla de clasificación de esta sección), y no publicamos estadísticas sobre ellas, así que agregar ruido con privacidad diferencial no protegería nada que lo necesite. Los datos restringidos, como el contenido de los mensajes y las llaves privadas, nunca llegan al directorio.

**Por qué HMAC y no un hash simple.** Un ID de Discord es enumerable (incluye la fecha de creación), así que basta probar candidatos y comparar. Con HMAC y una clave secreta eso no se puede. La clave se rota cada 90 días, igual que la retención (`crypto/pseudonym.py`).

**Límites.**

* Seudonimizar no es anonimizar: el seudónimo sigue siendo dato personal.
* Los metadatos permiten reidentificar: en el concurso de recomendaciones de Netflix se identificó al 99 % de las personas cruzando datos "anonimizados" con reseñas públicas (Narayanan & Shmatikov, 2008), y cuatro puntos de espacio y tiempo identifican al 95 % en datos de movilidad (de Montjoye et al., 2013). Con quién y cuándo hablas puede delatarte aunque no se vea el contenido (riesgo R1, aceptado y declarado).
* El desbloqueo de la aplicación exige contraseña y TOTP. Los archivos y exportaciones siguen dependiendo de la contraseña; protegerlos con un factor criptográfico adicional queda como mejora futura. TOTP tampoco evita el phishing del código.

La clasificación se revisa cada vez que cambia un dato, finalidad o proveedor, y al menos cada 6 a 12 meses junto con la DPIA.

## 7. Recomendaciones de protección futura

Proponemos las siguientes mejoras para futuras versiones. Las agrupamos según cuándo sería razonable trabajarlas y qué riesgo ayudarían a reducir. Los riesgos R1 a R14 son los de la [DPIA](dpia/DPIA.md) (sección 6.1) y los escenarios S1 a S12 son los del [plan de respuesta a incidentes](politicas/respuesta-incidentes.md#21-escenarios-de-brecha).

### 7.1 Antes de ampliar el uso

| Recomendación | Reduce | Por qué | Por qué no ahora |
|---|---|---|---|
| Auditoría externa y verificación formal del protocolo (ProVerif, Tamarin) | R13, S8 | Los fallos de protocolos suelen estar en cómo se combinan las piezas y quien lo diseñó ya no los ve | Cuesta dinero y tiempo |
| Autenticación resistente al phishing (WebAuthn) y llaves protegidas por hardware | R3, R4, R11 | El MFA con TOTP ya existe, pero un código puede capturarse mediante phishing y la bóveda sigue dependiendo de la contraseña | Cambia el registro, la recuperación y la compatibilidad entre dispositivos |
| Bloqueo por inactividad y mensajes con vida limitada | R3, R6 | Ya hay vencimiento absoluto de 30 minutos; falta medir inactividad y limitar la retención de mensajes | Requiere probar el comportamiento con usuarios |
| Almacén de claves para seudonimización, CA y cifrado del TOTP | R5, R8, R10 | Una variable de entorno es tan segura como su servidor | Requiere integrar la gestión de secretos con el despliegue en EC2 |
| Comprobar dependencias y firmar los archivos que distribuimos | S7 | Es el riesgo de mayor impacto y ninguna prueba funcional lo detecta | Pide infraestructura de publicación; el escaneo y el SBOM ya corren en CI |
| Divulgación responsable de vulnerabilidades y pentests periódicos | S8, S10 | Quien encuentre un fallo debe saber cómo avisar | No tiene sentido sin usuarios reales |
| Requisitos para ampliar el uso (banco de datos, edad mínima, contacto, GDPR si aplica) | R9, R12 | Son obligaciones que se revisan según el alcance del servicio | Requiere completar la evaluación y las acciones de C-24 antes de ampliar el uso |

### 7.2 A mediano plazo

Proponemos como siguiente cambio de cifrado una clave aleatoria adicional, distinta de la contraseña y del código TOTP. La bóveda necesitaría la contraseña y esa clave para descifrarse. EC2 conservaría la clave cifrada y la entregaría por HTTPS después de validar el autenticador; al bloquear o vencer la sesión, el cliente dejaría de conservarla en memoria. Así, copiar los archivos y conocer la contraseña no bastaría, y EC2 seguiría sin conocer la contraseña maestra ni la llave privada de mensajería.

Esto requiere diseñar la migración de bóvedas y exportaciones, la forma de guardar y recuperar esa clave, y qué hacer si el servidor deja de estar disponible. Perderla sin respaldo podría impedir el acceso a los datos. También hay que resolver la autenticación inicial: no se puede exigir para entregar la clave una firma cuya llave privada todavía está dentro de la bóveda cerrada. Esta propuesta no está implementada; el MFA actual sigue siendo un control de acceso de la aplicación.

| Recomendación | Reduce | Por qué | Por qué no ahora |
|---|---|---|---|
| Clave aleatoria adicional custodiada por EC2 y liberada tras MFA | R3, R4 | Evitaría abrir una copia de la bóveda solo con la contraseña | Requiere rediseñar cifrado, exportaciones, autenticación inicial, migración y recuperación; introduce dependencia criptográfica del servidor |
| *Double ratchet* (renovar claves por mensaje) | S4, S5 | Ayudaría a recuperar la seguridad después de una filtración de claves (Cohn-Gordon et al., 2016) | Es el cambio más grande al protocolo |
| Mensajes asíncronos con llaves previas (X3DH) | Limitación del *handshake* | Escribir a alguien desconectado | Reintroduce una llave de mediano plazo |
| Transparencia de llaves (Melara et al., 2015) | R2, S3 | Un directorio que cambie una llave dejaría prueba pública | Es un componente complejo |
| Protección de metadatos (relleno, un canal por par) | R1, S1 | Es la mayor exposición aceptada | Gasta ancho de banda y complica los canales |
| Varios dispositivos con una llave cada uno | R11, S5 | Perder uno no obliga a rotar todo | Cambia el modelo de identidad |
| Respaldo repartido de la identidad (Shamir, 1979) | R4 | Evita elegir entre "sin recuperación" y "el operador guarda una copia" | Flujo nuevo y difícil de explicar |
| Continuidad de la validación MFA y pruebas de recuperación | R14, S12 | El directorio ya es necesario para volver a abrir el historial; una copia de la base no sirve sin la clave de cifrado del TOTP | Ya recuperamos una copia de S3 y desciframos su factor MFA; falta automatizar la prueba, medir el tiempo y probar el login del servicio recuperado |
| Monitoreo y simulacros periódicos | S2, S9 | Un plan que nunca se ensaya falla cuando se necesita | Requiere un servicio con usuarios |

### 7.3 A largo plazo

| Recomendación | Reduce | Por qué | Por qué no ahora |
|---|---|---|---|
| Criptografía poscuántica híbrida (FIPS 203 y 204) | *Harvest now, decrypt later* | Combinada con X25519 sigue segura si una falla | Las bibliotecas aún no son estables |
| Mensajes de grupo con MLS (RFC 9420) | Ampliación funcional | Los grupos traen problemas nuevos (altas, bajas, orden) | Cambia todo el diseño |
| Denuncia verificable sin romper el cifrado (Grubbs et al., 2017) | Abuso (6.2) | Se puede probar un mensaje abusivo sin que el operador lea el resto | Cambia el cifrado de mensajes y quién modera |
| Pruebas de conocimiento cero para acreditar mayoría de edad | R12 | No hay que recoger la fecha de nacimiento | Tecnología poco madura |

Ninguna medida reemplaza a las otras: la seguridad se arma con capas, y cada una cubre la falla de otra.

## 8. Resultados y experimentos

Esta sección reúne la evidencia de que las medidas funcionan: pruebas automáticas, análisis de código, y simulacros con servicios reales. Cada resultado enlaza a su reporte, y la [tabla de trazabilidad](trazabilidad/trazabilidad.md) los conecta con los requerimientos.

### 8.1 Pruebas automáticas

| Componente | Pruebas | Qué demuestran |
|---|---|---|
| `crypto/` | 129 | Los caminos de rechazo: firma, confirmación de clave y etiqueta GCM inválidas, *replay*, reflexión, llaves efímeras destruidas y bóveda sin secretos en claro |
| `client/` | 91 | Sesiones, cola de salida, rotación, alerta y revocación por cambio de llave, desbloqueo con MFA y vencimiento de la sesión local, derechos ARCO y robustez de la API local |
| `directory/` | 101 | Prueba de posesión, OAuth2, MFA con TOTP (código reutilizado, recuperación), **acceso ajeno por endpoint**, esquema mínimo, TLS 1.3 con CA propia, auditoría sin datos personales y alertas |
| `discord_adapter/` | 14 | Conversación cifrada completa entre dos clientes; el adaptador se niega a publicar texto plano |
| `ops/` | 28 | Copias cifradas, subida a S3 y restauración, rol de solo lectura, tarea diaria y tabla de trazabilidad |
| `frontend/` | 39 + e2e | Formato, validación de contraseñas, aviso y consentimiento, TOTP al desbloquear, derechos ARCO; flujo completo en navegador |

Todas corren en CI en cada *push*, contra un PostgreSQL 17 real, y ninguna usa datos reales: los IDs son inventados.

### 8.2 Análisis de código antes y después

| Herramienta | Antes | Después | ¿Detecta? (prueba con fallas plantadas) |
|---|---|---|---|
| Bandit 1.9.4 | 5 (severidad baja) | 0 | 6 de 6 fallas conocidas |
| Semgrep 1.182.1 | 4 | 0 | 3 fallas plantadas (las demás las marca Bandit) |
| pip-audit 2.10.1 con SBOM por componente | 0 | 0 | 49 vulnerabilidades en dependencias viejas |
| npm audit con SBOM | 0 | 0 | — |
| gitleaks 8.30.1 (historial + árbol) | 0 + 2 | 0 + 0 | 4 de 4 secretos falsos |

Los 12 hallazgos se clasificaron uno por uno ([ops/reports](../ops/reports/README.md)): dos eran defectos reales (una exclusión de gitleaks mal anclada que no excluía nada y contraseñas de la CI publicadas, detectadas por GitGuardian), el resto falsos positivos o riesgos aceptados con su justificación en la misma línea. **Un cero solo vale si la herramienta es capaz de detectar**: por eso se plantaron fallas conocidas en un repositorio aparte y se comprobó que cada herramienta las encuentra ([f6-canarios.txt](../ops/reports/f6-canarios.txt)).

### 8.3 Simulacros y ensayos con servicios reales

| Ensayo | Resultado | Evidencia |
|---|---|---|
| Copia de seguridad cifrada y restauración | 16/16 comprobaciones: el archivo no tiene IDs ni llaves en claro, detecta un byte alterado o un archivo renombrado, la base restaurada coincide fila por fila. Restauración en 0,1 s frente a un RTO de 30 min | [f4-simulacro.txt](../ops/reports/f4-simulacro.txt) |
| Copia real de Supabase a S3 | Subida verificada y restaurada en un PostgreSQL aislado: 2 registros y 1 factor MFA descifrable | [f4-s3-smoke.txt](../ops/reports/f4-s3-smoke.txt) |
| Auditoría, alertas y tarea diaria | 13/13: 36 consultas a IDs inexistentes disparan las alertas de enumeración; ni los registros ni el *webhook* contienen IDs, IPs o tokens; la purga respeta los 90 días | [f5-simulacro.txt](../ops/reports/f5-simulacro.txt) |
| Adaptador con la API real de Discord | 9/9: publica y recibe, rechaza texto plano y mensajes largos, recupera lo atrasado al reconectar | [discord-smoke.txt](../ops/reports/discord-smoke.txt) |
| Permisos del canal y del bot | Canal privado; el bot no es administrador ni tiene permisos extra | [discord-check.txt](../ops/reports/discord-check.txt) |
| Login OAuth2 con una cuenta real | 13/13: un token no puede publicar la llave de otro ID, es de un solo uso, la cancelación borra la fila en el acto y el ID nunca aparece en claro en la auditoría | [oauth-discord.txt](../ops/reports/oauth-discord.txt) |
| Conversación entre dos cuentas | Dos clientes, cada uno con su bot, intercambian mensajes cifrados por `#e2ee-relay`; en el canal solo se ve `E2EE1:…` | Sección 5.1 |
| Incidente real INC-2026-01 | Contraseñas de la CI publicadas en GitHub: se aplicó el plan de respuesta, se rotaron y quedó una regla nueva de gitleaks | [respuesta-incidentes.md](politicas/respuesta-incidentes.md) |

### 8.4 Interpretación: privacidad frente a utilidad

Cada técnica quita algo de utilidad. La pregunta de diseño fue **qué utilidad necesita cada actor** y quitar solo la que no necesita:

| Técnica | Utilidad que se conserva | Utilidad que se pierde | Evidencia |
|---|---|---|---|
| Cifrado de extremo a extremo | La conversación completa para las dos personas | Discord y el operador no pueden moderar, buscar ni indexar el contenido | 8.1, 8.3 |
| Minimización del directorio | Encontrar la llave de alguien por su ID | Cualquier análisis de nombres, correos o IPs (no existen) | Esquema, `test_esquema.py` |
| Seudonimización con HMAC en la auditoría | Detectar un ataque repetido de la misma persona | Saber quién es esa persona sin la clave | 8.3 (simulacro F5) |
| *Forward secrecy* y rotación | Mensajes nuevos sin interrupción | Releer en otro equipo mensajes viejos desde Discord (el historial vive cifrado en el dispositivo) | [Primera entrega](primera-entrega.md), 4.2.5 |
| Retención de 30 y 90 días | Restaurar el directorio e investigar un incidente reciente | Investigar algo más antiguo que esos plazos | 8.3 (simulacros F4 y F5) |

En todos los casos se pierde la utilidad que **no tiene una finalidad declarada** en el aviso de privacidad y se conserva la que sí la tiene. Ese es el principio de finalidad de la Ley 29733 convertido en decisiones de ingeniería.

## 9. Conclusiones

* **El objetivo se cumplió:** dos personas conversan por Discord sin que Discord, el operador del directorio ni un tercero con acceso al canal puedan leer el contenido. Los 35 requerimientos (RF1–RF15 y RS1–RS20) tienen evidencia en la [tabla de trazabilidad](trazabilidad/trazabilidad.md), comprobada en cada *push*.
* **La confianza se movió del servidor a la persona.** El directorio guarda lo mínimo, no puede leer nada y, si entrega una llave falsa, la ceremonia de verificación lo detecta. El precio es la responsabilidad de la persona: proteger su contraseña y verificar a sus contactos.
* **La operación importa tanto como la criptografía.** Los dos defectos reales del proyecto no estuvieron en el protocolo sino en la configuración: una exclusión de gitleaks que no excluía nada y contraseñas de la CI publicadas. Ambos se encontraron gracias a las herramientas y se corrigieron con el plan de incidentes.
* **Medir antes de afirmar.** Cada control se probó con una falla plantada (canarios, accesos ajenos, bytes alterados, presupuesto agotado). Un "0 hallazgos" o un "cifrado" sin esa prueba no habría significado nada.
* **Lo que queda es conocido y está declarado:** los metadatos visibles para Discord, el primer contacto sin verificar, la falta de auditoría externa y las obligaciones legales de un uso real (sección 5.3 de la [primera entrega](primera-entrega.md) y secciones 6.1 y 7).

**Desde el diseño, la privacidad y la ética**

* **Elegir bien los algoritmos no bastaba; había que diseñar el protocolo completo.** El primer diseño cifraba con la llave de identidad del receptor y no tenía *forward secrecy*. Separar la identidad que solo firma de las llaves efímeras de sesión (sección 4.2 de la [primera entrega](primera-entrega.md)) fue la decisión que más seguridad aportó, y salió de revisar el protocolo contra el modelo de amenaza, no de cambiar un algoritmo.
* **La verificación fuera de banda es lo que hace confiable al sistema.** El cifrado protege del proveedor y de la red, pero solo la comparación de huellas impide que un directorio malicioso entregue una llave falsa. Por eso la alerta de cambio de llave no tiene botón de "continuar", aunque eso sea menos cómodo.
* **La privacidad se decidió en el diseño.** La DPIA y la clasificación de datos (6.1 y 6.3) se hicieron antes de guardar nada: no recogemos nombre, correo, teléfono ni IP, y lo que no se recoge no puede filtrarse. Los derechos ARCO se pueden ejercer desde la propia aplicación.
* **La decisión ética central fue no tener acceso excepcional.** Ni el equipo ni una autoridad pueden leer las conversaciones. Eso protege a las personas, pero también impide moderar el contenido y recuperar una contraseña olvidada; lo declaramos en el aviso de privacidad en lugar de ocultarlo (6.2).
* **Hay riesgos que aceptamos de forma explícita:** los metadatos visibles para Discord, el primer contacto sin verificar y el dispositivo comprometido. Quedan documentados en la DPIA con su justificación y con mejoras futuras propuestas (sección 7).

## 10. Lecciones aprendidas y retrospectiva

**Lo que salió bien**

* **Separar el proyecto en módulos con funciones definidas** (`crypto/`, `client/`, `frontend/` y `directory/`). Pudimos avanzar en paralelo y probar cada parte por separado, incluso con un Discord y un directorio simulados.
* **Probar también los casos que deben fallar** (firma mala, etiqueta GCM mala, *replay*). Encontramos varios errores del protocolo antes de que llegaran a la interfaz.
* **Entender la diferencia entre entrar a la aplicación y descifrar sus archivos.** El MFA limita el desbloqueo del cliente, pero no cambia la protección de una copia de la bóveda. La clave adicional custodiada por EC2 queda como siguiente paso y exige resolver la recuperación y la dependencia del servidor.
* **Hacer la DPIA y la clasificación de datos al principio.** Nos obligó a decidir qué no guardar (IP, nombre, correo) y eso simplificó todo lo demás.

**Lo que nos costó**

* **El primer diseño tenía un error.** Cifrábamos contra la llave pública de identidad del receptor y creíamos que con eso había *forward secrecy*. Al revisar el protocolo vimos que no. Rehacerlo con firmas y llaves efímeras en ambos lados fue más trabajo, pero era lo correcto. Aprendimos a revisar el protocolo completo y no solo a elegir algoritmos buenos.
* **Discord no deja enviar mensajes en nombre de un usuario.** Tuvimos que usar un bot por persona y dejar de confiar en el autor que muestra la plataforma.
* **Errores de integración que las pruebas unitarias no mostraban:** un bloqueo mutuo entre el cliente y el bucle de `discord.py`, una regla de `.gitignore` que dejó fuera `frontend/lib` y hacía que el frontend no compilara en un clon limpio, y contactos que "revivían" con *handshakes* vencidos.
* **Cosas que agregamos tarde:** los derechos ARCO en la interfaz, el QR de la huella y las reglas de contraseña. Mejor haberlas planeado desde la DPIA.

**Qué haríamos distinto**

1. Revisar el protocolo con alguien externo antes de programarlo.
2. Dejar el entorno de integración (dos cuentas, dos bots) listo desde el inicio, no al final.
3. Reservar tiempo fijo para documentar mientras se programa, y no al final.
4. Acordar los contratos entre módulos por escrito antes de repartir el trabajo.

**Aprendizaje del equipo.** Antes pensábamos que "usar AES" era suficiente. Ahora entendemos que la dificultad está en la gestión de llaves y la confianza: quién nos entrega la llave de la otra persona, cómo comprobamos que es la suya y qué ocurre si algo se compromete después. También aprendimos que la privacidad se decide en el diseño: los datos que no recogemos no se pueden filtrar.

### 10.1 Directorio, Discord y operaciones

**Qué funcionó**

* **Acordar contratos antes de programar.** Coordinamos con anticipación el formato de los mensajes, los puertos del cliente y las APIs. Con `client/fakes.py` como referencia, el directorio y el adaptador se construyeron en paralelo sin bloquear al cliente, y la integración casi no necesitó cambios.
* **Nombrar las pruebas por requerimiento** (`test_RS16_…`). Generar la tabla de trazabilidad desde esos nombres convirtió el informe en algo que la CI puede comprobar: si un requerimiento se queda sin evidencia, el  *build* falla.
* **Ensayar con los servicios reales** además de las pruebas simuladas: el ensayo con la API de Discord y el login OAuth2 con una cuenta real confirmaron supuestos que las pruebas con dobles no podían confirmar.

**Qué fue difícil y qué aprendimos**

* **Una herramienta que no detecta da una falsa tranquilidad.** La exclusión de gitleaks estaba anclada con `^` y gitleaks informa rutas con un prefijo, así que no excluía nada y, al revés, una regla mal escrita podía ocultar un secreto real. Desde entonces, cada herramienta se prueba con una falla plantada.
* **Los secretos "de prueba" también son secretos.** Las contraseñas de la base efímera de la CI no protegían nada, pero publicarlas era una mala práctica que GitGuardian detectó y gitleaks no. Se trató como un incidente real (INC-2026-01), lo que además sirvió para ensayar el plan de respuesta.
* **La concurrencia de `discord.py`.** Entregar los mensajes al cliente desde el bucle de eventos del bot producía un bloqueo mutuo, porque el cliente responde con `send()` mientras procesa. Se resolvió entregando desde un hilo propio.
* **El entorno de cada persona es parte del sistema.** Diferencias entre Windows y Linux (servir el frontend, rutas, versiones de Python y de Node) y una regla del `.gitignore` que excluía `frontend/lib/` hicieron que el proyecto funcionara en una máquina y no en un clon limpio. La CI con un entorno desde cero es la única forma confiable de comprobarlo.

**Qué haríamos distinto**

* Empezar el directorio y la CI al mismo tiempo que la librería criptográfica: la integración y los ensayos reales llegaron tarde y concentraron el trabajo al final.
* Hacer el simulacro del plan de incidentes antes de necesitarlo, y no después del primer incidente real.

---

## Referencias bibliográficas

* M'Raihi, D., Machani, S., Pei, M., & Rydell, J. (2011). *TOTP: Time-Based One-Time Password Algorithm* (RFC 6238). IETF. https://www.rfc-editor.org/rfc/rfc6238
* National Institute of Standards and Technology. (2025). *Digital Identity Guidelines: Authentication and Authenticator Management* (SP 800-63B-4). https://doi.org/10.6028/NIST.SP.800-63B-4

* Abadi, M., & Needham, R. (1996). Prudent engineering practice for cryptographic protocols. *IEEE Transactions on Software Engineering, 22*(1), 6–15. https://doi.org/10.1109/32.481513
* Abelson, H., Anderson, R., Bellovin, S. M., Benaloh, J., Blaze, M., Diffie, W., Gilmore, J., Green, M., Landau, S., Neumann, P. G., Rivest, R. L., Schiller, J. I., Schneier, B., Specter, M., & Weitzner, D. J. (2015). Keys under doormats: mandating insecurity by requiring government access to all data and communications. *Journal of Cybersecurity, 1*(1), 69–79. https://doi.org/10.1093/cybsec/tyv009
* Akhawe, D., & Felt, A. P. (2013). Alice in Warningland: a large-scale field study of browser security warning effectiveness. En *Proceedings of the 22nd USENIX Security Symposium* (pp. 257–272).
* Alatawi, M., & Saxena, N. (2023). SoK: An analysis of end-to-end encryption and authentication ceremonies in secure messaging systems. En *Proceedings of the 16th ACM Conference on Security and Privacy in Wireless and Mobile Networks* (pp. 187–201). ACM. https://doi.org/10.1145/3558482.3581773
* Cohn-Gordon, K., Cremers, C., Garratt, L., Millican, J., & Milner, K. (2016). On post-compromise security. En *2016 IEEE 29th Computer Security Foundations Symposium* (pp. 164–178). IEEE. https://doi.org/10.1109/CSF.2016.19
* Davis, D. (2001). Defective sign & encrypt in S/MIME, PKCS#7, MOSS, PEM, PGP, and XML. En *Proceedings of the USENIX Annual Technical Conference*.
* de Montjoye, Y.-A., Hidalgo, C. A., Verleysen, M., & Blondel, V. D. (2013). Unique in the crowd: The privacy bounds of human mobility. *Scientific Reports, 3*, 1376. https://doi.org/10.1038/srep01376
* Deng, M., Wuyts, K., Scandariato, R., Preneel, B., & Joosen, W. (2011). A privacy threat analysis framework: supporting the elicitation and fulfillment of privacy requirements. *Requirements Engineering, 16*(1), 3–32. https://doi.org/10.1007/s00766-010-0115-7
* Dolev, D., & Yao, A. C. (1983). On the security of public key protocols. *IEEE Transactions on Information Theory, 29*(2), 198–208. https://doi.org/10.1109/TIT.1983.1056650
* Ferguson, N., Schneier, B., & Kohno, T. (2010). *Cryptography engineering: Design principles and practical applications*. Wiley.
* Garg, P., Gupta, A., Singh, Y. P., & Goyal, P. (2026). End-to-end encryption: Evolution, barriers, and emerging trends. https://doi.org/10.1007/978-981-95-1683-4_8
* Grubbs, P., Lu, J., & Ristenpart, T. (2017). Message franking via committing authenticated encryption. En *CRYPTO 2017* (LNCS 10403, pp. 66–97). Springer.
* Josefsson, S., & Liusvaara, I. (2017). *Edwards-Curve Digital Signature Algorithm (EdDSA)* (RFC 8032). IETF. https://www.rfc-editor.org/rfc/rfc8032
* Krawczyk, H. (2003). SIGMA: The "SIGn-and-MAc" approach to authenticated Diffie-Hellman and its use in the IKE protocols. En *CRYPTO 2003* (LNCS 2729, pp. 400–425). Springer.
* Krawczyk, H., & Eronen, P. (2010). *HMAC-based Extract-and-Expand Key Derivation Function (HKDF)* (RFC 5869). IETF. https://www.rfc-editor.org/rfc/rfc5869
* Langley, A., Hamburg, M., & Turner, S. (2016). *Elliptic Curves for Security* (RFC 7748). IETF. https://www.rfc-editor.org/rfc/rfc7748
* Melara, M. S., Blankstein, A., Bonneau, J., Felten, E. W., & Freedman, M. J. (2015). CONIKS: Bringing key transparency to end users. En *Proceedings of the 24th USENIX Security Symposium* (pp. 383–398).
* Naor, M., Rotem, L., & Segev, G. (2018). *The security of lazy users in out-of-band authentication* (IACR Cryptology ePrint 2018/823). https://eprint.iacr.org/2018/823
* Narayanan, A., & Shmatikov, V. (2008). Robust de-anonymization of large sparse datasets. En *2008 IEEE Symposium on Security and Privacy* (pp. 111–125). IEEE. https://doi.org/10.1109/SP.2008.33
* Park, Y., Yoo, H., Ryu, J., Choi, Y.-R., Kang, J.-S., & Yeom, Y. (2023). End-to-end post-quantum cryptography encryption protocol for video conferencing system based on government public key infrastructure. *Applied System Innovation, 6*(4), 66. https://doi.org/10.3390/asi6040066
* Rescorla, E. (2018). *The Transport Layer Security (TLS) Protocol Version 1.3* (RFC 8446). IETF. https://www.rfc-editor.org/rfc/rfc8446
* Shamir, A. (1979). How to share a secret. *Communications of the ACM, 22*(11), 612–613. https://doi.org/10.1145/359168.359176
* Stallings, W. (2017). *Cryptography and network security: Principles and practice* (7.ª ed.). Pearson.
* Ylonen, T., & Lonvick, C. (2006). *The Secure Shell (SSH) Transport Layer Protocol* (RFC 4253). IETF. https://www.rfc-editor.org/rfc/rfc4253
* Congreso de la República del Perú. (2011). *Ley N.° 29733, Ley de Protección de Datos Personales*.
* Ministerio de Justicia y Derechos Humanos del Perú. (2024). *Decreto Supremo N.° 016-2024-JUS, Reglamento de la Ley N.° 29733*. https://www.gob.pe/institucion/anpd/normas-legales/6554453-n-016-2024-jus
* Parlamento Europeo y Consejo de la Unión Europea. (2016). *Reglamento (UE) 2016/679 (Reglamento General de Protección de Datos)*.
* National Institute of Standards and Technology. (2025). *Incident response recommendations and considerations for cybersecurity risk management* (NIST SP 800-61 Rev. 3). https://doi.org/10.6028/NIST.SP.800-61r3
