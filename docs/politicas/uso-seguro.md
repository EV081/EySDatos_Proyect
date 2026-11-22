# Políticas de uso seguro

Estas políticas establecen el uso del MFA, el vencimiento de la sesión local, la custodia de la clave que cifra el TOTP y la concientización y formación del equipo. Desplegamos y probamos el MFA del registro y del desbloqueo con Microsoft Authenticator.

## 1. Para las personas usuarias

| Política | Por qué |
|---|---|
| Usa una **contraseña maestra** larga y única (una frase de 4 o más palabras), que no uses en otro sitio. No podemos restablecerla; conserva una exportación de identidad con otra contraseña que recuerdes | Protege a la vez tu llave, tu historial y tus contactos (punto único de falla, sección 2.3 del [plan de incidentes](respuesta-incidentes.md)) |
| **Protege el autenticador y sus códigos de recuperación.** Guarda los códigos fuera del dispositivo, no los compartas y comprueba el dominio antes de escribir un TOTP | El código es temporal, pero un sitio falso puede usarlo mientras sigue vigente. La recuperación no recupera tu contraseña maestra |
| **Verifica** a cada contacto comparando la huella **fuera de Discord** (en persona, por llamada o con el QR) antes de hablar de algo sensible | Es la única defensa contra un directorio que entregue una llave falsa (R2). Un contacto sin verificar se muestra como tal |
| Si aparece la **alerta de cambio de llave**, no sigas la conversación: confirma con la persona por otra vía y repite la verificación. La aplicación no ofrece "continuar" | Un cambio de llave inesperado puede ser una suplantación |
| **Bloquea** la aplicación cuando no la uses y protege el dispositivo (bloqueo de pantalla, sistema actualizado, antivirus) | Con la aplicación desbloqueada, quien tenga el dispositivo ve todo (S4) |
| Guarda tu **exportación de identidad** en un medio fuera del dispositivo, con otra contraseña fuerte | Respalda la identidad y la clave del almacén, pero no incluye historial ni contactos. Para recuperarlos también hace falta el almacén local cifrado; una exportación con contraseña débil expone tus llaves |
| Si pierdes el dispositivo o sospechas que tu llave se filtró, **cancela tu registro** o publica una llave nueva, y avisa a tus contactos | Tus contactos recibirán la alerta y dejarán de confiar en la llave vieja |
| La aplicación es para **mayores de edad** y para conversaciones legítimas. No la uses para acosar, para el fraude ni para compartir contenido ilegal | Aviso de privacidad y consideraciones éticas (informe, sección 6.2) |
| Recuerda que Discord y los miembros del canal ven **quién habla con quién y cuándo**, aunque no el contenido | Los metadatos no están protegidos (R1) |

## 2. Para el equipo que opera el servicio

### 2.1 Acceso y mínimo privilegio

* Solo nosotros dos administramos el servidor del directorio y el servidor de Discord. No compartimos cuentas.
* La aplicación usa el rol `directory_app` (solo lectura y escritura de filas); las copias, `directory_backup` (solo lectura). Solo usamos el superusuario de Postgres para `migrations.apply` y para restaurar copias.
* Los bots tienen solo *Ver canal*, *Enviar mensajes* y *Leer historial* en `#e2ee-relay`. Ejecutamos `python -m discord_adapter.check` antes de cada demostración y tras cualquier cambio de permisos.
* El canal del proyecto es privado: `@everyone` no lo ve.

### 2.2 Secretos

* No versionamos secretos. Los guardamos en `.env` (ignorado por git) o en variables de entorno. gitleaks revisa el historial y el árbol en cada push, y GitGuardian revisa el repositorio en GitHub.
* **Tampoco las credenciales de prueba o de CI**, aunque protejan algo efímero: la CI genera las suyas en cada ejecución. Lo aprendimos en INC-2026-01 (anexo C del plan de incidentes).
* Custodiamos el `.env` real en el dispositivo o servidor que necesita cada secreto, con permisos restringidos; nunca lo versionamos. `TOTP_ENCRYPTION_KEY` se usa en el directorio, fuera de PostgreSQL, y mantenemos su respaldo protegido y separado de la instancia y del volcado de la base.
* Nunca compartimos secretos en Discord, en issues, en chats ni en capturas de pantalla.

**Calendario de rotación:**

| Secreto | Rotación ordinaria | Rotación inmediata si… | Cómo |
|---|---|---|---|
| Certificado TLS del directorio | Cada 60 días (vence a los 90) | Se filtra `server.key` | `python -m ops.certs.pki issue` (y `revoke` del anterior) |
| CRL | Cada 30 días (la regenera `issue`) | Hay un certificado revocado | `pki issue` / `pki revoke` y distribuir `crl.pem` |
| Llave de la CA | 5 años | Se filtra `ca.key` o su contraseña | CA nueva y reemplazar `ca.pem` en todos los clientes (incidente) |
| `PSEUDONYM_KEY` | 90 días (igual que la retención de registros) | Se filtra | Generar una nueva; los registros previos dejan de ser vinculables |
| `TOTP_ENCRYPTION_KEY` | Rotación planificada con recifrado; no cambiarla en cada despliegue | Se filtra o se sospecha exposición | Conservar la clave anterior para recifrar los secretos; cambiar solo la variable impediría validarlos. Guardar respaldo protegido por separado |
| Factor de cada persona | Al reemplazar el autenticador | Se pierde o se roba el celular o se expone el secreto | Iniciar con Discord y un código de recuperación, vincular otro factor y guardar los códigos nuevos; no omitir MFA |
| Token de cada bot | Cada semestre | Cualquier sospecha | Developer Portal -> *Reset Token*, actualizar `DISCORD_TOKEN` |
| `DISCORD_CLIENT_SECRET` (OAuth2) | Cada semestre | Cualquier sospecha | Developer Portal -> *Reset Secret* |
| `BACKUP_KEY` | Anual | Se filtra | Clave nueva, copia nueva y borrar las anteriores |
| Contraseñas de Postgres | Al cambiar el equipo | Se filtra `.env` | `ALTER ROLE ... PASSWORD`, actualizar `.env` y `migrations.apply` |

### 2.3 Datos personales y registros

* El directorio publica ID y llave pública y conserva fechas, aviso y los datos privados mínimos del segundo factor: secreto cifrado, hashes de recuperación, pasos utilizados y estado de intentos. El código temporal y la contraseña maestra no se registran. Antes de agregar un dato nuevo, debemos revisar la DPIA y el aviso de privacidad y subir su versión.
* Los registros de la aplicación no contienen IDs en claro, IPs, llaves, tokens ni mensajes; las pruebas automatizadas comprueban esta restricción. Revisamos por separado los registros de EC2 y de cualquier proxy. Solo nosotros leemos los registros, y únicamente para investigar un incidente o una alerta.
* Retención: registros de auditoría 90 días, llaves reemplazadas 90 días, copias de seguridad 30 días y el registro del directorio hasta que la persona lo cancele. La tarea diaria (`python -m ops.scheduled daily`) aplica la purga. También elimina las sesiones MFA vencidas (cinco minutos de validez) y altas sin confirmar de más de un día. La sesión local de 30 minutos por defecto es otro plazo y no se conserva como token de desbloqueo.
* Respondemos las solicitudes de derechos (acceso, rectificación, cancelación, oposición) en el plazo legal. La cancelación la puede hacer la propia persona desde su cliente.

### 2.4 Cambios y despliegue

* Trabajamos cada cambio en una rama de tarea (por ejemplo, `1-directorio-de-llaves`) y lo integramos a `main` mediante un *pull request* que revisa la otra persona.
* No integramos cambios con la CI en rojo: pruebas de los cinco componentes, Bandit, Semgrep, pip-audit, npm audit y gitleaks.
* Las dependencias van con versión fija. Justificamos cada dependencia nueva en el PR y la comprobamos con pip-audit o npm audit.
* Solo aceptamos un `# nosec` o `// nosemgrep` para una línea y una regla, con su justificación, y lo registramos en `ops/reports/README.md`.

### 2.5 Continuidad

* Copia diaria cifrada en el bucket privado S3 `proyecto-eticayseguridad`, en Virginia del Norte (`us-east-1`), respaldo protegido separado de `TOTP_ENCRYPTION_KEY` y restauración de prueba semanal. Objetivos: RPO de 24 h y RTO de 30 min. La tarea programada está instalada y activa; descargamos una copia de S3 y la restauramos en PostgreSQL aislado. Nos falta observar una ejecución automática y probar el inicio de sesión del servicio recuperado.
* Revisamos las alertas (`alerts.jsonl` o el webhook) a diario. Tratamos una alerta de `acceso_ajeno` o de varios `cambio_de_llave` como un posible incidente.

### 2.6 Revisión interna y aprobación

Completamos la revisión cruzada del proyecto, la revisión humana del protocolo y el análisis automatizado de seguridad. Aprobamos las medidas y los riesgos residuales descritos en la [DPIA](../dpia/DPIA.md), donde consignamos nuestros correos elmer.villegas@utec.edu.pe y farid.aquino@utec.edu.pe como firma. El [plan de respuesta a incidentes](respuesta-incidentes.md) establece los roles, contactos y procedimientos de actuación.

### 2.7 Concientización y formación

* **Al incorporarse**, cada integrante lee estas políticas, el [plan de respuesta a incidentes](respuesta-incidentes.md), la [DPIA](../dpia/DPIA.md) y la [política de privacidad](../privacidad/politica-de-privacidad.md), y confirma en el PR de su primer cambio que las leyó.
* **Los incidentes reales se usan para aprender.** Cada revisión posterior (por ejemplo, INC-2026-01) termina con una regla, una prueba o un cambio de política, y se comenta con todo el equipo.
* **Simulacros:** el simulacro en papel del plan de incidentes es también la práctica del equipo. Se hace cada semestre y antes de ampliar el uso.
* **Revisión de código como formación:** quien revisa un PR comprueba los puntos de estas políticas (secretos, dependencias, registros sin datos personales) y explica en el comentario lo que falta.
* **Concientización de las personas usuarias:** la sección 1 de estas políticas se muestra en lenguaje simple; el aviso de privacidad se acepta antes de crear la identidad, y la aplicación explica qué significan la huella, la alerta de cambio de llave y el bloqueo.
* **Actualización:** cuando cambia una política, el plan o la DPIA, se sube su versión y se avisa al equipo en el PR que lo cambia.

## 3. Incumplimiento

Si incumplimos estas políticas, tratamos el hecho como un incidente (ver el plan) y lo revisamos en la retrospectiva. Si una persona usuaria hace un uso abusivo, podemos cancelar su registro en el directorio y retirar su bot del servidor del proyecto.
