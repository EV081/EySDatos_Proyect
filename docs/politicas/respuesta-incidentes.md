# Plan de respuesta a incidentes

**Versión 1.0, 31 de octubre de 2026.** Cumple la restricción C-19 de la DPIA. Sigue la estructura de NIST SP 800-61 rev. 3 (2025), que integra la respuesta a incidentes en las funciones del CSF 2.0: **Gobernar, Identificar y Proteger** (preparación), **Detectar**, **Responder** y **Recuperar**, con mejora continua. Se ajusta a la Ley N.° 29733 y su reglamento (DS 016-2024-JUS): **notificar a la ANPD dentro de las 48 horas desde que se conoce la brecha** y avisar a las personas afectadas cuando el impacto es alto. Lo que sigue no es asesoría legal: el texto vigente se verifica antes de un uso real.

## 1. Gobernar: roles y contactos

| Rol | Quién | Responsabilidad |
|---|---|---|
| Coordinador del incidente | Farid (suplente: Elmer) | Declara el incidente, asigna tareas, lleva la bitácora y decide la notificación |
| Responsable técnico de criptografía y cliente | Elmer (suplente: Farid) | Evalúa el impacto en el protocolo, en el cliente y en las llaves de las personas |
| Responsable técnico de infraestructura | Farid | Directorio, base de datos, TLS, copias, registros y bots |
| Contacto con la ANPD y con las personas afectadas | El responsable del banco de datos (el equipo) | Envía las notificaciones y responde consultas |

**Contactos:** ANPD (Autoridad Nacional de Protección de Datos Personales, Ministerio de Justicia y Derechos Humanos), por su mesa de partes virtual. Discord: Trust & Safety, para la revocación de bots o los abusos de la plataforma. El correo del equipo y el domicilio se completan antes de un uso real (pendiente en el aviso de privacidad).

## 2. Identificar y Proteger: preparación

Lo que ya existe y que este plan usa:

| Capacidad | Dónde |
|---|---|
| Registros de auditoría seudonimizados, 90 días | `logs/audit.jsonl` (F5) |
| Alertas automáticas | `logs/alerts.jsonl` y el webhook opcional (F5) |
| Copias cifradas, fuera del servidor, con restauración probada | `python -m ops.backup.backup` (F4) |
| Revocación del certificado del directorio | `python -m ops.certs.pki revoke` (F2) |
| Cancelación y cambio de llave en el directorio | `DELETE /v1/keys/{id}`, `PUT` con `old_signature` (F1) |
| Detección de secretos y de dependencias vulnerables | CI con gitleaks, pip-audit y npm audit (F6) |
| Alerta de cambio de llave a los contactos | Cliente (RF8) |
| Inventario de datos y riesgos | DPIA y secciones 6.4 y 7 del informe |

## 3. Detectar: fuentes y clasificación

**Fuentes:** alertas del directorio (`acceso_ajeno`, firmas inválidas repetidas, enumeración, cambios de llave), fallos de la CI (gitleaks, pip-audit), avisos de una persona usuaria (por ejemplo, "me salió una alerta de cambio de llave que yo no hice"), avisos de Discord y de terceros, y la revisión diaria de alertas.

**Severidad:**

| Nivel | Criterio | Ejemplos | Tiempo para empezar a responder |
|---|---|---|---|
| **Crítico** | Se expone el contenido de los mensajes, una llave privada o la llave de la CA, o hay una sustitución de llaves en curso | S3, S4 con muchas personas, S7, fuga de `ca.key` | Inmediato |
| **Alto** | Se exponen datos personales del directorio o de las copias, o se filtra un token o un secreto del servidor | S2, S6, S9, fuga de `.env` | Antes de 4 h |
| **Medio** | Hay un intento detectado sin exposición confirmada | Alerta de enumeración, `acceso_ajeno` aislado, dependencia vulnerable sin explotación conocida | Antes de 24 h |
| **Bajo** | Hay una indisponibilidad sin exposición | S12 | Siguiente día hábil |

**Reloj legal:** el plazo de 48 horas para la ANPD corre desde que el equipo **conoce** la brecha de datos personales, no desde que termina la investigación. La primera entrada de la bitácora registra la fecha y hora de ese momento (T0).

## 4. Responder

### 4.1 Pasos generales

1. **Declarar** el incidente: abrir la bitácora (plantilla en el anexo A) con T0, quién lo detectó y la severidad inicial.
2. **Preservar la evidencia antes de tocar nada:** copiar `logs/` y la última copia de seguridad a un medio aparte y calcular el SHA-256 de cada archivo. No borrar registros mientras dure el incidente (se suspende la purga de 90 días para esos archivos).
3. **Contener** según la guía del escenario (4.2).
4. **Evaluar el impacto:** qué datos, de cuántas personas, desde cuándo, y si el riesgo para ellas es alto. Usar el inventario de la DPIA y las entidades afectadas de la sección 7.2 del informe.
5. **Notificar** (sección 5) si hubo una brecha de datos personales.
6. **Erradicar y recuperar** (sección 6).
7. **Cerrar** con la revisión posterior (sección 7).

### 4.2 Guías por escenario

| Escenario | Contener | Erradicar y recuperar | ¿Notificar a la ANPD? |
|---|---|---|---|
| **S2 / S9: brecha de la base o de las copias** | Detener el directorio; cambiar las contraseñas de los roles de Postgres; revocar el acceso del atacante | Restaurar desde la última copia verificada en un servidor limpio (`backup restore`); rotar `BACKUP_KEY` y `PSEUDONYM_KEY`; revisar los registros por cambios de llave en la ventana del incidente | **Sí**: ID de Discord, llave y fechas son datos personales |
| **S3: el directorio sustituye llaves** (alertas de `cambio_de_llave` no reconocidos o reportes de personas) | Detener el directorio; avisar por el canal del proyecto (fuera del directorio) que **nadie inicie conversaciones con contactos sin verificar** | Comparar las llaves con la última copia previa al incidente; restaurar las legítimas; pedir a las personas afectadas que repitan la verificación | **Sí**, si se confirma una sustitución |
| **Fuga de `server.key` o de la llave de la CA** | Certificado: `pki revoke <serial>` + `pki issue`, y distribuir `crl.pem`. CA: detener el directorio | CA: crear una nueva (`pki init` en otra carpeta), distribuir el nuevo `ca.pem` por un canal confiable y revisar si hubo emisiones no autorizadas | Solo si se usó para interceptar datos |
| **S6: fuga del token de un bot** | Developer Portal → *Reset Token*; quitar el bot del servidor si hay abuso | Actualizar `DISCORD_TOKEN`; revisar el canal por mensajes inyectados (el protocolo los rechaza) | En general no: solo hay texto cifrado y metadatos. Evaluar si se descargaron metadatos de muchas personas |
| **Fuga del `.env`** (secretos del servidor) | Rotar **todo** lo del calendario de la política de uso seguro | Revisar el historial de git (gitleaks), los registros y los accesos a la base | Si hay indicios de acceso a la base, tratar como S2 |
| **S5 / S4: la llave o el dispositivo de una persona** | La persona cancela su registro o publica una llave nueva desde otro dispositivo; sus contactos reciben la alerta | La persona crea una identidad nueva y repite las verificaciones | El dispositivo es de la persona: el equipo la asiste. Notificar si el origen fue una falla del sistema |
| **S7 / S8: dependencia maliciosa o defecto del protocolo** | Retirar la versión afectada; avisar a las personas que bloqueen la aplicación hasta actualizar | Corregir, agregar una prueba que reproduzca el defecto, publicar una versión nueva y pedir rotar las sesiones (las sesiones viejas se descartan al rotar) | **Sí**, si pudo exponer contenido o llaves |
| **Enumeración o `acceso_ajeno`** | Bajar los límites de solicitudes; bloquear el origen en el firewall si persiste | Revisar si algún intento tuvo éxito (cambios de llave en la ventana) | No, salvo que haya tenido éxito |

## 5. Notificación

**A la ANPD, dentro de las 48 h desde T0:**

* Descripción del incidente y fecha y hora de inicio, de detección (T0) y de contención.
* Categorías y número aproximado de personas y de registros afectados (por ejemplo, "N IDs de Discord con su llave pública y fechas").
* Consecuencias probables para las personas.
* Medidas adoptadas y propuestas, incluidas las que reducen el daño.
* Datos de contacto del responsable.

Si a las 48 h todavía faltan datos, **se notifica igual** con lo que se sabe y se completa después. Notificar tarde es una infracción aparte.

**A las personas afectadas, cuando el riesgo para ellas es alto** (por ejemplo, una sustitución de llaves o la exposición de contenido): en lenguaje claro, por un medio que no dependa del sistema afectado. El aviso dice qué pasó, qué datos se expusieron, qué hizo el equipo y **qué deben hacer** (verificar de nuevo a sus contactos, cambiar la contraseña maestra, crear una identidad nueva).

**A Discord**, si el incidente involucra el abuso de su plataforma o de los bots.

## 6. Recuperar

* Restaurar el servicio desde un estado limpio: copia verificada (`backup verify`), secretos rotados y certificado nuevo.
* Confirmar que el servicio funciona: la CI en verde, `discord_adapter.check` sin problemas y una consulta de llave por HTTPS con la CA nueva.
* Vigilar con más atención (revisar las alertas cada hora) durante 7 días.
* La cancelación que pidió una persona afectada se aplica también a las copias, a más tardar en 30 días (rotación).

## 7. Mejora continua: revisión posterior

Dentro de los 7 días siguientes al cierre, sin buscar culpables:

* Cronología con los tiempos (T0, contención, notificación, recuperación).
* Qué funcionó, qué no y por qué se detectó (o no) antes.
* Acciones con responsable y fecha: nuevas pruebas, reglas de alerta o cambios a las políticas.
* Actualizar la DPIA (riesgos y puntuaciones) y este plan.

## 8. Ejercicios

* **Simulacro en papel** cada semestre, y antes de un uso real. Escenario sugerido: "llega una alerta de 3 cambios de llave en una hora y una persona reporta que su contacto ya no está verificado". El equipo recorre las secciones 4 a 6 con el reloj de 48 h corriendo y registra los resultados en el anexo B.
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
| Notificación a la ANPD (hora y medio) | Límite: T0 + 48 h |
| Aviso a las personas afectadas (hora y medio) | |
| Recuperación confirmada (hora) | |
| Revisión posterior (fecha y enlace) | |

## Anexo B: registro de simulacros

| Fecha | Escenario | Participantes | Tiempo hasta la decisión de notificar | Hallazgos y acciones |
|---|---|---|---|---|
| (pendiente: primer simulacro antes de la demostración) | | | | |
