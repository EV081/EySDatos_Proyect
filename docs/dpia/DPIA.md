# Evaluación de Impacto en la Protección de Datos (DPIA)

**Sistema:** mensajería cifrada de extremo a extremo sobre Discord
**Versión:** 1.0 (borrador para firma) · **Elaborada:** 2026-10-25 · **Formato:** plantilla de 7 pasos (ICO), adaptada a la Ley 29733 y su reglamento (DS 016-2024-JUS)

> **Cómo leer el estado de las medidas.** Cada medida lleva su estado real: **✔ implementada y probada** (con la prueba que lo demuestra), **◐ implementada en el cliente, falta el lado del servicio** o **○ pendiente** (con su responsable). El riesgo residual de la sección 6 solo vale una vez que las medidas pendientes estén hechas; por eso la decisión final es *"se puede lanzar con condiciones"* y no *"se puede lanzar"*.

## Datos del responsable

| | |
|---|---|
| Responsable del tratamiento | Equipo del proyecto: Elmer Villegas Suarez y Farid Aquino Castro |
| Delegado / oficial de datos | No designado (proyecto académico). Su función de revisión la cumplen ambos integrantes, cada uno revisando la parte del otro |
| Contacto para ejercer derechos | A definir en el aviso de privacidad definitivo (tarea E6) |

---

## Paso 1. Necesidad de una DPIA

**Qué hace el proyecto.** Una capa de cifrado de extremo a extremo (E2EE) sobre la API de Discord. Cada persona usa una página web propia (el *cliente*) que cifra los mensajes antes de enviarlos; Discord solo ve texto cifrado. Un *directorio de llaves* publica, por cada usuario, su ID de Discord y su llave pública de firma para que otros puedan encontrarla.

**Por qué se hace una DPIA.** No es obligatoria por ley para un proyecto de este tamaño, pero se hace porque se cumplen varios de los factores que la hacen recomendable:

1. **Tecnología novedosa:** un protocolo criptográfico propio (handshake autenticado con PFS) que no ha tenido una auditoría externa.
2. **Puede alcanzar datos sensibles:** el contenido de las conversaciones es libre y puede incluir datos de salud, políticos, de menores, etc., aunque el responsable no puede leerlos.
3. **Identificadores de personas reales:** el directorio relaciona un ID de Discord con una llave y una fecha.
4. **Privacidad desde el diseño:** conviene identificar los riesgos antes de que entre un solo dato real.

---

## Paso 2. Descripción del tratamiento

### 2.1 Naturaleza: cómo se recogen, usan, guardan y borran los datos

```
 Dispositivo de la persona                         Servicios remotos
┌─────────────────────────────────┐    TLS 1.3    ┌──────────────────────┐
│ Frontend ─ Cliente local        │──────────────▶│ Directorio de llaves │
│  (texto plano solo en memoria;  │  ID + llave   │  (ID, llave pública, │
│   vault.json y store.enc        │  pública      │   fechas, versión    │
│   cifrados en disco)            │               │   del aviso)         │
└──────────────┬──────────────────┘               └──────────────────────┘
               │ mensajes del protocolo y texto cifrado (a través de un bot)
               ▼
        Canal privado de Discord  ── solo ciphertext + metadatos ──▶ Discord (EE. UU.)
```

| Etapa | Qué ocurre | Dónde |
|---|---|---|
| **Recolección** | La persona escribe su ID de Discord y acepta el aviso de privacidad. El dispositivo genera la llave de identidad; solo la llave **pública** y el ID se publican. | Dispositivo → directorio |
| **Almacenamiento** | Llave privada y datos locales: cifrados con AES-256-GCM bajo una clave derivada de la contraseña maestra (Argon2id). Directorio: base de datos con ID, llave pública y fechas. Discord: ciphertext. | Dispositivo; directorio; Discord |
| **Uso** | Cifrar, firmar y descifrar mensajes; verificar la huella de un contacto. | Solo en el dispositivo |
| **Compartición** | Con otros usuarios (llave pública, por diseño) y con Discord (ciphertext y metadatos, por necesidad técnica). Sin terceros adicionales. | — |
| **Destrucción** | Llaves de sesión y llaves efímeras: se destruyen al rotar o bloquear. El resto, según la tabla de retención (2.2). | Dispositivo; directorio |

**Fuentes de datos:** la propia persona (ID, mensajes) y el dispositivo (llaves generadas). El ID de Discord se vincula con su cuenta mediante OAuth2 (`identify`), sin pedir nada más.

**Tratamientos de riesgo alto presentes:** tecnología novedosa (protocolo propio sin auditoría externa). **No hay** perfilado, decisiones automatizadas, seguimiento de comportamiento ni vigilancia sistemática.

### 2.2 Alcance: qué datos, cuántos, cuánto tiempo

| Dato | Dónde está | Sensibilidad | Quién lo puede ver | Retención |
|---|---|---|---|---|
| ID de Discord | Directorio; contactos locales; campos `from`/`to` de cada mensaje; logs (seudonimizado) | Personal (identificador) | Directorio, Discord y miembros del canal | Hasta que la persona cancele su registro |
| Llave pública de firma | Directorio; contactos locales | Pública por diseño | Cualquier usuario | Igual que el ID. Llaves reemplazadas: 90 días |
| Fechas de registro y de cambio de llave | Directorio | Personal (metadato) | Operadores del directorio | Igual que el registro |
| Versión del aviso aceptado y fecha | Directorio; almacén local | Personal (prueba de consentimiento) | Operadores; la propia persona | Mientras dure el registro, más el plazo para demostrarlo |
| Contenido de los mensajes (texto plano) | **Solo** el dispositivo: memoria y almacén local cifrado | **Potencialmente sensible**; el responsable no puede leerlo | Solo los dos interlocutores | Hasta que la persona lo borre localmente |
| Mensajes cifrados | Discord | Ilegible sin las llaves de sesión, que ya no existen tras rotar o bloquear | Discord y miembros del canal | Según Discord (fuera de nuestro control) |
| Metadatos de mensajes (quién, a quién, cuándo, tamaño) | Discord; canal | Personal (relaciones sociales) | Discord y miembros del canal | Según Discord |
| Llave privada y `store_key` | Solo el dispositivo, en `vault.json` cifrado | Crítica | Nadie sin la contraseña maestra | Hasta que la persona borre la bóveda |
| Alias y pines de los contactos, historial, cola de salida | Almacén local cifrado (`store.enc`) | Personal | Solo la persona | Hasta que la persona los borre |
| Registros de auditoría | Servidor del directorio | Personal (ID seudonimizado) | Operadores | 90 días |
| Copias de seguridad del directorio | Fuera del servidor, cifradas | Igual que el directorio | Operadores | Rotación de 30 días |

**Por qué estos plazos.** Cada dato se conserva solo mientras sirve a su finalidad (limitación del plazo de conservación):

* **Registro del directorio, hasta que la persona lo cancele.** Su base es el consentimiento; sin él no hay razón para conservarlo.
* **Registros de auditoría, 90 días.** Un incidente suele detectarse semanas después de ocurrir; ese tiempo permite investigarlo y reunir la evidencia que pide la notificación a la autoridad (48 horas desde que se conoce). Más allá no hay finalidad que lo justifique.
* **Llaves reemplazadas, 90 días.** Permiten explicar y revisar un cambio de llave sospechoso; después no aportan nada.
* **Copias de seguridad, 30 días con rotación.** Equilibran poder recuperarse de un desastre o ataque con que una cancelación quede completa, también en las copias, en un mes. Una copia más antigua sobreviviría al borrado.
* **Contenido local:** lo decide la persona, porque solo existe en su dispositivo.

Son valores propuestos y se revisan si cambia la finalidad.

**Categorías especiales:** el sistema no las recoge ni puede leerlas; solo podrían aparecer dentro de los mensajes, que solo ven las personas que conversan.
**Volumen y frecuencia:** demostración con 2 usuarios; uso real previsto de decenas. Un registro por persona; los mensajes dependen de ellas.
**Personas afectadas:** usuarios de la aplicación y sus contactos (que pueden aparecer en el directorio sin ser usuarios activos: ver R7).
**Área geográfica:** Perú; los servidores de Discord están en EE. UU.; pueden participar personas de otros países, por ejemplo de la UE.

### 2.3 Contexto

* **Relación con las personas:** directa y voluntaria; el equipo no tiene ningún vínculo de autoridad sobre ellas.
* **Control que tienen:** crean y bloquean su identidad, exportan su identidad cifrada, verifican contactos, deciden con quién hablan. El borrado del registro en el directorio requiere el endpoint de cancelación (○ C-11).
* **Expectativas:** quien usa una herramienta "cifrada" espera que nadie lea sus mensajes; no necesariamente que los **metadatos** queden visibles (ver R1). Por eso el aviso lo dice explícitamente.
* **Menores y grupos vulnerables:** Discord admite usuarios desde los 13 años y la aplicación no verifica la edad (ver R12).
* **Inquietudes previas:** el debate público sobre el acceso excepcional frente al E2EE; el proyecto adopta una posición explícita: **no existe ninguna llave de custodia ni puerta trasera**.
* **Novedad:** el protocolo es propio, aunque se compone de primitivas estándar y sigue el patrón de SSH y TLS 1.3. No ha pasado una auditoría externa.
* **Códigos de conducta o certificaciones:** ninguno.

### 2.4 Finalidades

1. Permitir conversaciones privadas sobre una plataforma popular, de modo que ni Discord ni una brecha en sus servidores expongan el contenido.
2. Permitir que las personas encuentren la llave de sus contactos y comprueben su identidad.

**Efecto buscado en las personas:** más privacidad de lo que dicen, sin cambiar de plataforma. **Beneficio más amplio:** demostrar que se puede añadir E2EE sobre un servicio que no lo ofrece.

---

## Paso 3. Proceso de consulta

| Parte | Cómo se consulta | Estado |
|---|---|---|
| Equipo (Elmer y Farid) | Cada uno revisa la parte del otro; el reparto de medidas está en `REPARTO.md` | En curso |
| Personas usuarias | Sesión de prueba con 4 a 6 compañeros durante la demostración y tres preguntas de comprensión del aviso: (1) ¿qué puede ver Discord de tus mensajes?, (2) ¿qué pasa si olvidas la contraseña maestra?, (3) ¿cómo comprobarías que hablas con la persona correcta? Si más de una persona falla alguna, se reescribe el aviso (R7) | ○ Pendiente; **no se ha hecho** |
| Revisión por pares | Otro grupo revisa esta DPIA y su sistema con tres preguntas: ¿cada dato tiene finalidad y retención?, ¿falta algún riesgo evidente?, ¿alguna puntuación está subestimada? | ○ Pendiente |
| Discord | No se le consulta: es un tercero independiente. Se toman sus condiciones como un dato de contexto (ver paso 4) | — |
| Expertos en seguridad | Revisión del docente; análisis automático del código (Bandit, pip-audit, gitleaks) | ○ Pendiente (F6, Farid) |
| Auditoría externa del protocolo | No es viable en el alcance del proyecto; se deja como recomendación | Recomendado |

---

## Paso 4. Necesidad y proporcionalidad

* **Base de licitud:** consentimiento libre, previo, expreso, informado e inequívoco (Ley 29733), pedido al registrarse y por separado de cualquier otra cosa. Está **desmarcado por defecto**, tiene una única finalidad y su versión se registra (✔ `test_publicar_la_llave_exige_aceptar_el_aviso_de_privacidad_vigente`, `test_el_directorio_recibe_la_version_del_aviso_aceptado`). No se condiciona el uso a ninguna otra finalidad.
* **¿Se logra la finalidad?** Sí: conversación cifrada de extremo a extremo con verificación de identidad (✔ pruebas de `crypto/`, `client/` y e2e en navegador).
* **¿Hay otra forma de lograrlo?** Usar Signal o similar da mejor protección, pero el objetivo es proteger conversaciones **dentro de Discord**. Se descartó intercambiar llaves a mano por ser inusable; el directorio es el compromiso, y la ceremonia de verificación fuera de banda impide que el directorio pueda sustituir llaves sin que se detecte.
* **Prevención de usos adicionales (*function creep*):** el directorio solo guarda lo que está en la tabla 2.2; las finalidades se limitan a las dos de 2.4; no se hace analítica ni publicidad; si el aviso cambia, sube la versión y hay que volver a aceptarlo (✔ `client/privacy.py`).
* **Calidad y minimización:** no se piden nombre, correo, teléfono, avatar ni nombre de usuario; el directorio no registra direcciones IP (○ C-05). El cliente nunca envía contenido al directorio.
* **Información a las personas:** resumen del aviso (versión 1.0) visible antes de aceptar (✔ `frontend/components/IdentityGate.tsx`); el texto completo, con los elementos que exige la Ley 29733, está en [`privacidad/aviso-de-privacidad.md`](../privacidad/aviso-de-privacidad.md) y se publica dentro de la aplicación (✔ `frontend/test/notice.test.ts`).
* **Derechos (ARCO y portabilidad):**

| Derecho | Cómo se atiende | Estado |
|---|---|---|
| Acceso | La persona consulta su propio registro (ID, llave, fechas) | ○ Pendiente (F1) |
| Rectificación | Cambiar de llave: la anterior autoriza la nueva (`sign_key_change`) | ◐ Firma implementada en `crypto/`; falta el endpoint |
| Cancelación | Borrar el registro del directorio, firmado con su llave; los respaldos y registros caducan en 30 y 90 días | ○ Pendiente (C-11) |
| Oposición | No registrarse, o cancelar; no hay otro tratamiento al que oponerse | ✔ por diseño |
| Portabilidad | Exportar la identidad cifrada a otro dispositivo (RF12) | ✔ `test_RF12_exportar_e_importar_en_otro_dispositivo` |
| Borrado local de datos | Hoy se borra eliminando los archivos; falta un botón en la aplicación | ○ Pendiente (Elmer) |

* **Encargados:** Discord **no** es un encargado nuestro: es un responsable independiente de su propia plataforma. Si el directorio se aloja con un proveedor, se firmará un contrato y se elegirá la región con criterio legal (para la demostración corre en local).
* **Transferencias internacionales:** a Discord (EE. UU.) viajan solo texto cifrado y metadatos; el contenido no puede leerse en destino. El directorio no sale del equipo del responsable durante la demostración.

---

## Paso 5. Identificación y evaluación de los riesgos

**Escalas (plantilla ICO).** Probabilidad: *Remota*, *Posible*, *Probable*. Gravedad: *Mínima*, *Significativa*, *Grave*. Riesgo global:

| | Mínima | Significativa | Grave |
|---|---|---|---|
| **Probable** | Medio | **Alto** | **Alto** |
| **Posible** | Bajo | Medio | **Alto** |
| **Remota** | Bajo | Bajo | Medio |

Los riesgos están descritos con las medidas **de diseño base** ya consideradas (E2EE, firmas y PFS) pero **antes** de las medidas adicionales del paso 6. Las categorías LINDDUN son L = vinculabilidad, I = identificabilidad, N = no repudio, D = detectabilidad, Di = divulgación, U = desconocimiento, NC = incumplimiento.

| ID | Riesgo y su impacto en las personas | LINDDUN | Probabilidad | Gravedad | Riesgo global |
|---|---|---|---|---|---|
| **R1** | **Exposición de metadatos.** Discord y quienes están en el canal ven quién habla con quién, cuándo y con qué tamaño. Permite inferir relaciones, hábitos y a veces el contenido por el patrón de mensajes. | L, D | Probable | Significativa | **Alto** |
| **R2** | **Sustitución de la llave por un directorio malicioso o comprometido.** Un atacante entrega su llave en lugar de la del contacto y se interpone en el primer contacto, con acceso a la conversación. | I, Di | Posible | Grave | **Alto** |
| **R3** | **Robo o infección del dispositivo.** Acceso al historial, contactos, cola de salida y a la bóveda. | Di | Posible | Grave | **Alto** |
| **R4** | **Contraseña maestra débil, olvidada o perdida.** Un atacante con la bóveda robada puede probar contraseñas; si la persona la olvida pierde su identidad y su historial. | Di | Posible | Significativa | Medio |
| **R5** | **Brecha en la base de datos del directorio.** Se filtra qué IDs de Discord usan esta herramienta, con fechas. | I, L, D | Posible | Significativa | Medio |
| **R6** | **Conservación excesiva o borrado incompleto.** Los datos permanecen en copias de seguridad, registros o Discord tras pedir la cancelación. | NC | Probable | Significativa | **Alto** |
| **R7** | **Falta de transparencia.** Las personas no entienden qué se ve y qué no (metadatos, verificación, sin recuperación), o un contacto aparece en el directorio sin haberlo aceptado. | U | Probable | Significativa | **Alto** |
| **R8** | **Registros (logs) con datos personales.** Un fallo deja IDs en claro, llaves o texto en los registros del servicio. | Di, D | Posible | Significativa | Medio |
| **R9** | **Incumplimiento legal.** Banco de datos personales sin inscribir, transferencia internacional sin garantías, o no notificar una brecha en 48 horas. | NC | Posible | Significativa | Medio |
| **R10** | **Filtración del token del bot o de las credenciales OAuth.** Un tercero lee o publica en el canal y observa el tráfico cifrado y los metadatos. | Di, D | Posible | Significativa | Medio |
| **R11** | **Robo de la llave de identidad.** El atacante firma handshakes futuros y se hace pasar por la persona ante sus contactos. | I, N | Posible | Grave | **Alto** |
| **R12** | **Menores de edad.** Discord admite desde 13 años y la aplicación no verifica la edad; podrían publicar su ID sin una comprensión plena. | U, NC | Posible | Significativa | Medio |
| **R13** | **Defecto en el protocolo o en su implementación.** Un fallo criptográfico no detectado expone mensajes o permite suplantar. Sin auditoría externa. | Di, I | Posible | Grave | **Alto** |

---

## Paso 6. Medidas para reducir los riesgos

Las medidas se escriben como **restricciones verificables** (C-xx): cada una se puede comprobar con una prueba, un archivo o una revisión, y tiene un responsable. Las tareas F son de Farid; E, de Elmer (ver `REPARTO.md`).

### 6.1 Restricciones

| ID | Restricción | Cómo se verifica | Resp. | Estado |
|---|---|---|---|---|
| **C-01** | Ningún contenido de mensaje sale del dispositivo en claro: en el canal solo hay mensajes `E2EE1:` y el texto cifrado | `test_RF3_en_el_canal_solo_hay_mensajes_del_protocolo_y_ciphertext`; revisión del canal en la demostración | E | ✔ |
| **C-02** | La llave privada, la `store_key` y el historial solo existen en disco cifrados con AES-256-GCM; las llaves de sesión y efímeras nunca se escriben | `test_RS1_RS2_nada_secreto_en_claro_en_disco`; `test_RS12_ninguna_llave_efimera_sobrevive_al_handshake` | E | ✔ |
| **C-03** | Argon2id con al menos t=3, m=64 MiB, p=4 y *salt* único; los parámetros están autenticados y acotados | `KdfParams` por defecto; `test_RS2_los_parametros_de_kdf_estan_autenticados`; `test_RS2_parametros_fuera_de_rango…` | E | ✔ |
| **C-04** | Tras 5 contraseñas incorrectas, el desbloqueo se bloquea 30 s; al bloquear se destruyen las sesiones | `test_RS2_contrasena_incorrecta_y_bloqueo_temporal`; `test_al_bloquear_se_destruyen_las_sesiones` | E | ✔ |
| **C-05** | El directorio guarda solo `discord_id`, llave pública, fechas y versión del aviso. No registra nombre de usuario, correo, avatar ni direcciones IP | Revisión del esquema de la base de datos (migración) y una prueba que lista las columnas | F (F1) | ○ |
| **C-06** | Publicar o cambiar una llave exige prueba de posesión firmada y el vínculo OAuth2 con el mismo ID | `verify_registration` ya existe (✔); falta la prueba del endpoint y OAuth2 | F (F1) | ◐ |
| **C-07** | El directorio solo se sirve por TLS 1.3 con una CA propia y el cliente rechaza un certificado inválido sin ofrecer continuar | Prueba de conexión con certificado vencido o ajeno; revisión de la configuración | F (F2) | ○ |
| **C-08** | La aplicación usa un rol de base de datos sin permisos de DDL ni de propietario y solo consultas parametrizadas; *rate-limit* anti-enumeración | Revisión de `GRANT/REVOKE`; prueba de inyección y de acceso ajeno por endpoint | F (F1) | ○ |
| **C-09** | Los registros de auditoría no contienen texto, llaves, tokens ni IDs en claro (los IDs se seudonimizan con HMAC y una clave que se rota cada 90 días) | `crypto/pseudonym.py` con sus pruebas (✔); falta una prueba automática que busque esos patrones en los registros reales y la configuración del servicio | F (F5) | ◐ |
| **C-10** | Retención: registros 90 días; llaves reemplazadas 90 días; copias de seguridad 30 días con rotación; registro del directorio hasta su cancelación | Tarea programada de borrado y su prueba; documento de retención | F (F4, F5) | ○ |
| **C-11** | Existe un endpoint que cancela el registro de una persona (firmado con su llave) y la borra en el directorio de inmediato y de las copias en ≤ 30 días | Prueba de extremo a extremo del borrado y de la rotación de copias | F (F1, F4) | ○ |
| **C-12** | Las copias de seguridad están cifradas, fuera del servidor del directorio, con restauración probada | Script de restauración con su prueba; documentación de RPO/RTO | F (F4) | ○ |
| **C-13** | Los secretos (token del bot, credenciales OAuth) están en variables de entorno; el repositorio no contiene secretos; el token de la API local solo se envía a `127.0.0.1`/`localhost` | Escaneo con gitleaks en CI sin hallazgos (○); `test/conn.test.ts` del frontend, que solo admite `127.0.0.1`/`localhost` (✔) | F (F6) / E | ◐ |
| **C-14** | Antes de publicar una llave, la persona acepta el aviso de privacidad vigente (casilla desmarcada, finalidad única); se registra la versión y la fecha y el directorio las conserva | Pruebas de `client/` (✔); la columna del directorio y su prueba (○) | E / F (F1) | ◐ |
| **C-15** | El aviso de privacidad completo cumple los elementos de la Ley 29733 y se muestra antes de aceptar; sube de versión si cambia | `frontend/test/notice.test.ts` (secciones exigidas, versión igual en documento, frontend y cliente, coherencia de plazos con esta DPIA); la prueba e2e comprueba que se publica en la aplicación | E (E6) | ✔ |
| **C-16** | Ante un cambio de llave de un contacto verificado: se revoca la verificación, se aborta el handshake y no se ofrece "continuar" | `test_RF8_*` del cliente; prueba unitaria del frontend | E | ✔ |
| **C-17** | Nada de lo que llega de Discord se interpreta como HTML ni se ejecuta | Prueba e2e con `<img onerror=…>`; el código no usa `dangerouslySetInnerHTML` | E | ✔ |
| **C-18** | La API local solo escucha en `127.0.0.1`, exige token, restringe CORS al origen del frontend y valida el `Host` | `test_sin_token_o_con_token_incorrecto…`, `test_host_ajeno…`, `test_cors_solo…` | E | ✔ |
| **C-19** | Existe un plan de respuesta a incidentes con notificación a la ANPD en 48 horas desde que se conoce la brecha, y la rotación y revocación de llaves | Documento revisado por ambos; simulacro en papel | F (F7) | ○ |
| **C-20** | El código pasa SAST (Bandit/Semgrep) y escaneo de dependencias (pip-audit) en CI, y los hallazgos altos están corregidos | Reportes antes y después en `ops/security/` | F (F6) | ○ |
| **C-21** | Existe un botón para borrar localmente la bóveda y el almacén cifrado | Prueba del cliente y del frontend | E | ○ |
| **C-22** | El protocolo está documentado, con tabla de ataques considerados y pruebas negativas por cada defensa; se deja constancia de que no hubo auditoría externa | `docs/README.md` (4.2.7); las pruebas negativas de `crypto/` y `client/`, que se comprobó a mano que detectan defectos introducidos a propósito | E | ✔ |
| **C-23** | El canal de Discord del proyecto es privado y de acceso restringido a los participantes | Revisión de la configuración del servidor antes de la demostración | F (F3) | ○ |
| **C-24** | Antes de ofrecer el servicio fuera del ámbito académico: inscribir el banco de datos ante la ANPD si corresponde, exigir una edad mínima y firmar contrato con el proveedor de alojamiento | Lista de verificación previa al lanzamiento | Ambos | ○ |

### 6.2 Medidas por riesgo

| Riesgo | Medidas | Efecto | Riesgo residual | ¿Aprobada? |
|---|---|---|---|---|
| **R1** Metadatos | C-23 (canal privado y acotado), C-15 (el aviso lo dice con claridad), C-01. Recomendado a futuro: relleno de mensajes a tamaño fijo y un canal por par de contactos (ver las recomendaciones) | Reducido: la exposición sigue existiendo, pero se limita a un público pequeño y la persona lo sabe; **sin la aplicación, Discord vería además el contenido** | Probable × Mínima → **Medio** | Sí, aceptado |
| **R2** Sustitución de llaves | C-07, C-06, C-16, y la ceremonia fuera de banda con *pin* (✔ `test_RF8_*`, `test_RF7_*`) | Reducido; el primer contacto no verificado sigue dependiendo de la confianza en el directorio (TOFU) | Remota × Grave → **Medio** | Sí, aceptado; la interfaz muestra "sin verificar" |
| **R3** Dispositivo | C-02, C-03, C-04. Fuera de alcance: un dispositivo ya comprometido con la aplicación desbloqueada | Reducido: con la aplicación cerrada o bloqueada, el atacante debe romper Argon2id | Remota × Grave → **Medio** | Sí, aceptado |
| **R4** Contraseña | C-03 y mínimo de 10 caracteres (✔ validación del cliente y del frontend); exportación de la identidad como respaldo (RF12); el aviso dice que no hay recuperación | Reducido | Remota × Significativa → **Bajo** | Sí |
| **R5** Brecha del directorio | C-05, C-07, C-08, C-10, C-12 | Reducido: se filtraría solo ID, llave pública y fechas, sin contenido | Remota × Significativa → **Bajo** | Sí |
| **R6** Conservación | C-10, C-11, C-12; el cifrado hace que lo que quede en Discord sea inservible (*borrado criptográfico*, porque las claves de sesión se destruyen) | Reducido | Remota × Significativa → **Bajo** | Sí |
| **R7** Transparencia | C-14, C-15, indicadores del estado de la sesión en la interfaz (✔ pruebas del frontend) y registro de consentimiento por versión | Reducido | Remota × Significativa → **Bajo** | Sí |
| **R8** Registros | C-09, C-10 | Reducido | Remota × Significativa → **Bajo** | Sí |
| **R9** Incumplimiento | C-19, C-24, C-15; documentar la transferencia a Discord y alojar el directorio donde se justifique | Reducido | Remota × Significativa → **Bajo** | Sí |
| **R10** Token del bot | C-13; permisos mínimos del bot y rotación del token ante cualquier sospecha | Reducido | Remota × Significativa → **Bajo** | Sí |
| **R11** Robo de la llave | C-03 y C-04; cambio de llave autorizado por la anterior o por OAuth, que **alerta a los contactos** (RF8); la PFS protege lo pasado | Reducido; lo futuro no queda protegido hasta que la persona cambie de llave | Remota × Grave → **Medio** | Sí, aceptado |
| **R12** Menores | Declaración de mayoría de edad dentro del consentimiento (✔ frontend) y aviso dirigido a mayores de edad; C-24 (edad mínima antes de un uso real); datos mínimos, nada de perfilado ni publicidad, aviso en lenguaje claro | Reducido | Remota × Significativa → **Bajo** | Sí |
| **R13** Defecto del protocolo | C-22, C-20; componentes estándar (`cryptography`, Argon2id), pruebas negativas (comprobadas a mano contra defectos introducidos a propósito); recomendación de auditoría externa | Reducido; **no eliminado** | Remota × Grave → **Medio** | Sí, aceptado; la limitación se declara en el informe |

**Criterio para aceptar un riesgo en nivel medio.** Un riesgo se acepta solo si se cumplen las cuatro condiciones: (1) no puede eliminarse sin dejar de cumplir la finalidad; (2) la aplicación no añade exposición respecto de no usarla (sin ella, Discord vería además el contenido); (3) la persona lo sabe antes de aceptar, por el aviso y por los indicadores de la interfaz; y (4) existe una mejora recomendada para reducirlo más adelante.

| Riesgo aceptado | Por qué no se elimina | Mejora recomendada |
|---|---|---|
| R1 Metadatos | Discord los ve en cualquier uso de la plataforma | Relleno de mensajes a tamaño fijo; un canal por par de contactos |
| R2 Sustitución de llaves | Sin una autoridad confiable, el primer contacto depende de la verificación humana | Registro público de llaves auditable (transparencia de llaves); recordar verificar a quien aún no lo está |
| R3 Dispositivo | Un dispositivo ya comprometido queda fuera de lo que puede garantizar una aplicación | Bloqueo automático por inactividad; llave protegida por hardware |
| R11 Robo de la llave | No hay forma de evitar el robo si el dispositivo se compromete | Mostrar los dispositivos y llaves activos, y facilitar la revocación |
| R13 Defecto del protocolo | Ningún protocolo nuevo es demostrablemente correcto sin una revisión externa | Auditoría externa y verificación formal del protocolo |

**Ningún riesgo residual es Alto**, por lo que no hace falta consulta previa a la autoridad. Cinco quedan en **Medio** (R1, R2, R3, R11, R13) y se aceptan de forma explícita, con las razones de arriba.

### 6.3 Cobertura de LINDDUN

| Categoría | Riesgos | Medidas principales |
|---|---|---|
| Vinculabilidad (L) | R1, R5 | C-23, C-05, C-10 |
| Identificabilidad (I) | R2, R5, R11, R13 | C-05, C-07, C-16 |
| No repudio (N) | R11 | No se firma cada mensaje: no hay pruebas transferibles de autoría |
| Detectabilidad (D) | R1, R5, R8, R10 | C-09, C-13, C-23 |
| Divulgación (Di) | R2, R3, R4, R8, R10, R13 | C-01, C-02, C-03, C-09 |
| Desconocimiento (U) | R7, R12 | C-14, C-15 |
| Incumplimiento (NC) | R6, R9, R12 | C-10, C-11, C-19, C-24 |

---

## Paso 7. Aprobación y registro de resultados

| Elemento | Nombre / cargo / fecha | Notas |
|---|---|---|
| Medidas aprobadas por | _Pendiente de firma_ (Elmer Villegas, Farid Aquino) | Las acciones pendientes entran al plan del proyecto con su responsable (6.1) |
| Riesgos residuales aprobados por | _Pendiente de firma_ | Se aceptan R1, R2, R3, R11 y R13 con las razones del paso 6 |
| Consejo del delegado | No aplica: no hay delegado | La revisión cruzada entre los dos integrantes lo reemplaza |
| Resumen del consejo | — | — |
| Consejo aceptado o rechazado por | — | — |
| Comentarios | — | — |
| Respuestas de la consulta revisadas por | _Pendiente_: aún no se hizo la sesión con personas usuarias (paso 3) | Si la decisión se aparta de lo que opinen, se explicará |
| Esta DPIA será revisada por | Ambos integrantes | Antes de la entrega final y ante cualquier cambio de datos, finalidad, tecnología o proveedor |

### Decisión

> **Se puede lanzar con condiciones.** Para la demostración local basta lo ya implementado (C-01 a C-04, C-15 a C-18, C-22 y la parte del cliente de C-14). **No debe usarse con datos reales de terceros** hasta que se cumplan las restricciones pendientes, en especial C-05 a C-12 (directorio, TLS, registros, retención, cancelación y respaldos), C-19 (plan de incidentes), C-20 (análisis de código) y C-24 (requisitos previos al uso real).

### Plan de acciones pendientes

| Acción | Responsable | Restricción | Para cuándo |
|---|---|---|---|
| Directorio: esquema mínimo, prueba de posesión con OAuth2, roles de base de datos, cancelación | Farid | C-05, C-06, C-08, C-11 | Antes de la entrega |
| TLS 1.3 con CA propia | Farid | C-07 | Antes de la entrega |
| Registros sin datos personales, retención y alertas | Farid | C-09, C-10 | Antes de la entrega |
| Copias cifradas y restauración | Farid | C-12 | Antes de la entrega |
| Escaneo de secretos, SAST y dependencias en CI | Farid | C-13, C-20 | Antes de la entrega |
| Plan de incidentes (48 h) | Farid | C-19 | Antes de la entrega |
| Botón de borrado local | Elmer | C-21 | Antes de la entrega |
| Sesión de prueba con personas usuarias | Ambos | Paso 3 | Durante la demostración |
| Requisitos previos a un uso real | Ambos | C-24 | Fuera del alcance de la entrega |

*Fechas concretas por definir con el equipo; este documento es un **documento vivo**.*

---

## Referencias

* Information Commissioner's Office (ICO). *Sample DPIA template*. Reino Unido.
* Congreso de la República del Perú (2011). *Ley N.° 29733, Ley de Protección de Datos Personales*. Y su reglamento, aprobado por el Decreto Supremo N.° 016-2024-JUS.
* Deng, M., Wuyts, K., Scandariato, R., Preneel, B., & Joosen, W. (2011). A privacy threat analysis framework: supporting the elicitation and fulfillment of privacy requirements. *Requirements Engineering, 16*(1), 3–32. https://doi.org/10.1007/s00766-010-0115-7
* Cavoukian, A. (2009). *Privacy by Design: The 7 Foundational Principles*. Information and Privacy Commissioner of Ontario.
* National Institute of Standards and Technology (2025). *Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile* (SP 800-61 Rev. 3).
