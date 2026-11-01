# Políticas de uso seguro

**Versión 1.0, 31 de octubre de 2026.** Se aplica a las personas que usan la aplicación y al equipo que opera el directorio de llaves y el servidor de Discord del proyecto. Se revisa junto con la DPIA ante cualquier cambio de datos, finalidad, tecnología o proveedor. Lo que pasa cuando algo sale mal está en el [plan de respuesta a incidentes](respuesta-incidentes.md).

## 1. Para las personas usuarias

| Política | Por qué |
|---|---|
| Usa una **contraseña maestra** larga y única (una frase de 4 o más palabras), que no uses en otro sitio. No hay recuperación: si la olvidas, solo te queda tu exportación | Protege a la vez tu llave, tu historial y tus contactos (punto único de falla, sección 7.3 del informe) |
| **Verifica** a cada contacto comparando la huella **fuera de Discord** (en persona, por llamada o con el QR) antes de hablar de algo sensible | Es la única defensa contra un directorio que entregue una llave falsa (R2). Un contacto sin verificar se muestra como tal |
| Si aparece la **alerta de cambio de llave**, no sigas la conversación: confirma con la persona por otra vía y repite la verificación. La aplicación no ofrece "continuar" | Un cambio de llave inesperado puede ser una suplantación |
| **Bloquea** la aplicación cuando no la uses y protege el dispositivo (bloqueo de pantalla, sistema actualizado, antivirus) | Con la aplicación desbloqueada, quien tenga el dispositivo ve todo (S4) |
| Guarda tu **exportación de identidad** en un medio fuera del dispositivo, con otra contraseña fuerte | Es tu único respaldo; un archivo exportado con contraseña débil es una llave expuesta |
| Si pierdes el dispositivo o sospechas que tu llave se filtró, **cancela tu registro** o publica una llave nueva, y avisa a tus contactos | Tus contactos recibirán la alerta y dejarán de confiar en la llave vieja |
| La aplicación es para **mayores de edad** y para conversaciones legítimas. No la uses para acosar, para el fraude ni para compartir contenido ilegal | Aviso de privacidad y consideraciones éticas (6.3) |
| Recuerda que Discord y los miembros del canal ven **quién habla con quién y cuándo**, aunque no el contenido | Los metadatos no están protegidos (R1) |

## 2. Para el equipo que opera el servicio

### 2.1 Acceso y mínimo privilegio

* Solo los dos integrantes del equipo administran el servidor del directorio y el servidor de Discord. No hay cuentas compartidas.
* La aplicación usa el rol `directory_app` (solo lectura y escritura de filas); las copias, `directory_backup` (solo lectura). El superusuario de Postgres solo se usa para `migrations.apply` y para restaurar copias.
* Los bots tienen solo *Ver canal*, *Enviar mensajes* y *Leer historial* en `#e2ee-relay`. `python -m discord_adapter.check` se ejecuta antes de cada demostración y tras cualquier cambio de permisos.
* El canal del proyecto es privado: `@everyone` no lo ve.

### 2.2 Secretos

* Ningún secreto se versiona. Todos van en `.env` (ignorado por git) o en variables de entorno. gitleaks revisa el historial y el árbol en cada push.
* El `.env` real vive solo en el equipo del responsable, con permisos de lectura para su usuario.
* Nunca se pegan secretos en Discord, en issues, en chats ni en capturas de pantalla.

**Calendario de rotación:**

| Secreto | Rotación ordinaria | Rotación inmediata si… | Cómo |
|---|---|---|---|
| Certificado TLS del directorio | Cada 60 días (vence a los 90) | Se filtra `server.key` | `python -m ops.certs.pki issue` (y `revoke` del anterior) |
| CRL | Cada 30 días (la regenera `issue`) | Hay un certificado revocado | `pki issue` / `pki revoke` y distribuir `crl.pem` |
| Llave de la CA | 5 años | Se filtra `ca.key` o su contraseña | CA nueva y reemplazar `ca.pem` en todos los clientes (incidente) |
| `PSEUDONYM_KEY` | 90 días (igual que la retención de registros) | Se filtra | Generar una nueva; los registros previos dejan de ser vinculables |
| Token de cada bot | Cada semestre | Cualquier sospecha | Developer Portal → *Reset Token*, actualizar `DISCORD_TOKEN` |
| `DISCORD_CLIENT_SECRET` (OAuth2) | Cada semestre | Cualquier sospecha | Developer Portal → *Reset Secret* |
| `BACKUP_KEY` | Anual | Se filtra | Clave nueva, copia nueva y borrar las anteriores |
| Contraseñas de Postgres | Al cambiar el equipo | Se filtra `.env` | `ALTER ROLE ... PASSWORD`, actualizar `.env` y `migrations.apply` |

### 2.3 Datos personales y registros

* El directorio guarda solo el ID, la llave pública, las fechas y la versión del aviso aceptado. Agregar cualquier dato nuevo exige actualizar antes la DPIA y el aviso de privacidad (y subir su versión).
* Los registros nunca contienen IDs en claro, IPs, llaves, tokens ni mensajes; se revisan con `test_C09_*` en cada push. Solo el equipo lee los registros, y únicamente para investigar un incidente o una alerta.
* Retención: registros de auditoría 90 días, llaves reemplazadas 90 días, copias de seguridad 30 días y el registro del directorio hasta que la persona lo cancele. La tarea diaria (`python -m ops.scheduled daily`) lo aplica.
* Las solicitudes de derechos (acceso, rectificación, cancelación, oposición) se responden en el plazo legal. La cancelación la puede hacer la propia persona desde su cliente.

### 2.4 Cambios y despliegue

* Todo cambio entra por una rama (`farid/<tarea>`, `elmer/<tarea>`) y un *pull request* revisado por la otra persona.
* No se integra nada con la CI en rojo: pruebas de los cinco componentes, Bandit, Semgrep, pip-audit, npm audit y gitleaks.
* Las dependencias van con versión fija. Una dependencia nueva se justifica en el PR y pasa pip-audit o npm audit.
* Un `# nosec` o `// nosemgrep` solo se acepta para una línea y una regla, con su justificación, y se registra en `ops/reports/README.md`.

### 2.5 Continuidad

* Copia diaria cifrada fuera del servidor y restauración de prueba semanal (`ops.backup.backup verify`). Objetivos: RPO de 24 h y RTO de 30 min.
* Las alertas (`alerts.jsonl` o el webhook) se revisan a diario. Una alerta de `acceso_ajeno` o de varios `cambio_de_llave` se trata como un posible incidente.

## 3. Incumplimiento

Una violación de estas políticas por parte del equipo se trata como un incidente (ver el plan) y se revisa en la retrospectiva. Si una persona usuaria hace un uso abusivo, se puede cancelar su registro en el directorio y retirar su bot del servidor del proyecto.
