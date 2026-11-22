# Reparto de trabajo y estado

Organizamos el trabajo para la entrega final por módulos. Cada uno se encarga de una parte para avanzar sin depender del otro; acordamos las interfaces compartidas en los contratos de la sección 3. El directorio está en EC2, Virginia del Norte (`us-east-1`), y PostgreSQL está en Supabase; los clientes y el frontend siguen en cada dispositivo. Desplegamos y probamos el MFA con Microsoft Authenticator.

Leyenda de estado: Hecho = implementado con evidencia; Parcial = faltan acciones; Pendiente = sin completar. Distinguimos las pruebas con los servicios reales de las pruebas automáticas.

## 1. Diseño de seguridad (resumen)

El diseño completo y su justificación están en el documento de la [primera entrega](primera-entrega.md) (secciones 2 y 4.2). En una línea: identidad Ed25519 que solo firma; *handshake* autenticado de tres mensajes con Diffie-Hellman efímero en ambos extremos (X25519), claves de sesión distintas por dirección con HKDF-SHA256, mensajes con AES-256-GCM, contador anti-*replay* y rotación a los 100 mensajes o 8 h; ceremonia de verificación fuera de banda con *pin* de llaves. El desbloqueo habitual exige contraseña, desafío firmado y TOTP; la sesión local vence a los 30 minutos por defecto.

**Discord como transporte.** La API oficial no permite escribir en nombre de un usuario, así que cada persona usa su propio bot en un canal privado del servidor del proyecto. El autor que muestra Discord siempre es un bot y no se usa: el emisor y el receptor viajan dentro del mensaje y se autentican con el *handshake*.

## 2. Reparto

### Elmer — Criptografía, cliente local, frontend, diseño, privacidad y ética

Informe: Motivación, Trasfondo Teórico, Diseño, privacidad y ética (DPIA incluida), riesgos y recomendaciones.

| ID | Tarea | Estado |
|---|---|---|
| E1 | Protocolo (*handshake* autenticado con PFS), secciones 2, 4.2 y 5.1 de la [primera entrega](primera-entrega.md), diagramas y tabla de ataques considerados | Hecho |
| E2 | Librería `crypto/`: identidad y bóveda (Argon2id + AES-GCM), exportación/importación, *handshake*, sesión, huella. Con pruebas de los caminos de rechazo | Hecho (129 pruebas de criptografía) |
| E3 | API local del cliente (`client/`): orquesta crypto, directorio y Discord; cola, reintentos, rotación, alertas, desbloqueo con MFA y vencimiento local de sesión | Hecho (91 pruebas del cliente) |
| E4 | Frontend en Next.js (`frontend/`): identidad, contactos, chat, QR de verificación, alertas y campo TOTP al desbloquear | Hecho (39 pruebas unitarias; QR y sección "Mis datos" (ARCO) implementados; ver `frontend/e2e/smoke.mjs`). MFA desplegado y probado con Microsoft Authenticator |
| E5 | DPIA con la plantilla de siete pasos ([dpia/DPIA.md](dpia/DPIA.md)); consentimiento por versión en cliente y frontend | Hecho (aprobación y correos como firma en el paso 7) |
| E6 | Ética y privacidad: aviso de privacidad completo ([privacidad/aviso-de-privacidad.md](privacidad/aviso-de-privacidad.md), publicado también en la aplicación), cumplimiento de la Ley 29733 ([política de privacidad](privacidad/politica-de-privacidad.md)) y consideraciones éticas (informe, sección 6.2) | Hecho (correos publicados; falta domicilio postal antes de ampliar el uso) |
| E7 | Clasificación de datos y técnicas de privacidad (informe, sección 6.3); seudonimización con HMAC y enmascarado de referencia en `crypto/pseudonym.py` | Hecho (16 pruebas) |
| E8 | Riesgos de una brecha y entidades afectadas ([plan de incidentes](politicas/respuesta-incidentes.md), secciones 2.1 a 2.3) y recomendaciones futuras (informe, sección 7) | Hecho |
| E9 | Lecciones aprendidas y retrospectiva (parte de Elmer; informe, sección 10) y su parte de las conclusiones (sección 9) | Parcial borrador, falta que Elmer lo ajuste |

### Farid — Directorio, Discord, operaciones y herramientas

Informe: Requerimientos, Implementación lograda, operaciones, políticas e incidentes.

| ID | Tarea | Estado |
|---|---|---|
| F1 | **Directorio de llaves** (FastAPI + PostgreSQL). Publicar o cambiar una llave exige **prueba de posesión** (`verify_registration` ya está en `crypto/`) y vincular el ID con OAuth2 (`identify`) y TOTP; solo el dueño modifica su registro. Consultas parametrizadas, *rate-limit*, errores genéricos, **rol de base de datos con permisos mínimos**. Publica ID y llave pública; guarda también fechas, aviso y datos privados mínimos de MFA (secreto cifrado y hashes de recuperación). Endpoint de cancelación | Hecho (101 pruebas contra Postgres, incluidos MFA, la consulta del registro propio y el cambio de llave para los derechos ARCO; [directory/README.md](../directory/README.md)). Falta `sign_cancellation` con contexto propio en `crypto/` |
| F2 | **TLS 1.3 con CA propia**: el cliente valida contra esa CA y no permite continuar si falla. Documentar la cadena de confianza y la revocación | Hecho (10 pruebas; [ops/certs/README.md](../ops/certs/README.md)) |
| F3 | **Adaptador de Discord** (`discord.py`): servidor privado, canal `#e2ee-relay` y un bot por persona; publicar y leer mensajes `E2EE1:` ignorando el autor; token en variables de entorno | Hecho (14 pruebas con Discord simulado; ensayo con la API real en [ops/reports/discord-smoke.txt](../ops/reports/discord-smoke.txt); conversación entre dos cuentas, cada una con su bot) |
| F4 | **Copias de seguridad**: `pg_dump` programado y cifrado, fuera del servidor, con restauración probada y rotación de 30 días | Parcial: primera copia real a S3 verificada ([evidencia](../ops/reports/f4-s3-smoke.txt)); cron configurado y activo; restauración desde S3 ensayada con 2 registros y 1 factor MFA descifrable; falta observar una ejecución automática ([guía](guia/despliegue-ec2.md#8-activar-el-respaldo-diario-de-supabase-en-s3)) |
| F5 | **Registros de auditoría y alertas**: eventos de registro y cambio de llave, fallos de firma, enumeración; sin texto, llaves ni IDs en claro (usar `Pseudonymizer` de `crypto/pseudonym.py` con la clave en `PSEUDONYM_KEY`); retención de 90 días | Hecho (10 pruebas; tarea diaria `ops.scheduled`) |
| F6 | **Análisis de código**: Bandit o Semgrep, pip-audit con SBOM, gitleaks y pruebas de acceso ajeno por endpoint, en CI; reportes antes y después | Hecho ([ops/reports/README.md](../ops/reports/README.md)) |
| F7 | **Políticas de uso seguro** y **plan de respuesta a incidentes** (NIST SP 800-61 rev. 3), con notificación a la ANPD en 48 h | Hecho ([politicas/](politicas/), plan v1.5 y uso seguro v1.3; primer incidente real registrado, INC-2026-01); falta registrar el simulacro |
| F8 | Informe: requerimientos actualizados, implementación lograda y tabla de trazabilidad requerimiento <-> evidencia | Hecho (informe 3.1, 5.1, 5.2 y 8; [trazabilidad.md](trazabilidad/trazabilidad.md), generada y comprobada en CI) |
| F9 | Lecciones aprendidas y retrospectiva (parte de Farid): informe, sección 10.1 | Hecho (falta la revisión de Elmer) |

### Compartido (al final)

- Integración de extremo a extremo y ensayo de la demostración.
- Presentación (Elmer: motivación, diseño y DPIA; Farid: implementación, operaciones y resultados de las herramientas).
- Completamos la revisión cruzada: cada uno revisó la sección del otro. Si hay otro grupo disponible, podemos intercambiar DPIAs con la lista de revisión (inventario, riesgos que faltan, puntuación).
- Publicar el informe en GitHub Pages (vive en `docs/README.md`).

## 3. Contratos entre las dos partes

| Contrato | Dónde | Lo usan |
|---|---|---|
| Formato de mensaje en Discord (`E2EE1:<base64url(JSON)>`, tipos `hs1`, `hs2`, `hs3`, `msg`) | [`crypto/API.md`](../crypto/API.md) | `client/`, adaptador de Discord |
| Interfaz de la librería | [`crypto/API.md`](../crypto/API.md) | `client/`; el directorio solo usa `verify_registration`, `verify_key_change`, `verify_unlock`, `Pseudonymizer` y `mask_id` |
| Puertos del directorio y de Discord | [`client/ports.py`](../client/ports.py) y [`client/README.md`](../client/README.md) | Farid los implementa; `client/fakes.py` es la referencia de comportamiento |
| API local cliente <-> frontend | [`api/client.openapi.json`](api/client.openapi.json) | `frontend/` |
| API del directorio | [`api/directory.yaml`](api/directory.yaml) | `client/`, directorio |

Puntos que el directorio debe cumplir y que el cliente ya asume:

- `register(discord_id, public_key, sign, consent_version)` guarda la versión del aviso aceptado y la fecha.
- `authenticate_session(discord_id, code, sign)` verifica el desafío firmado y el TOTP sin emitir un token reutilizable para próximos desbloqueos.
- `get_key(discord_id)` devuelve `None` si la persona no está registrada, y cualquier fallo se lanza como `DirectoryError`.
- Para trabajar sin esperar: `python -m client.dev` levanta dos clientes con un directorio y un canal en memoria.

## 4. Estructura del proyecto

Trabajamos en un monorepo y asignamos un responsable por carpeta para evitar conflictos de git.

```
EySDatos_Proyect/
├── README.md
├── .env.example                 # desarrollo con PostgreSQL y directorio locales
├── .env.example.local           # cliente de cada laptop conectado a EC2
├── .env.example.ec2             # directorio, Supabase y respaldos en S3
├── docker-compose.yml           # Postgres + directorio (Farid)
├── Makefile                     # make dev | test | scan | backup | restore
├── .github/workflows/ci.yml     # pruebas + Bandit + pip-audit + gitleaks (Farid, F6)
│
├── crypto/                      # ── ELMER ── librería pura, sin red ni Discord
├── client/                      # ── ELMER ── API local (FastAPI, solo localhost)
├── frontend/                    # ── ELMER ── Next.js, sitio estático
│
├── directory/                   # ── FARID ── servicio de llaves
│   ├── app/  migrations/  client_lib/  tests/
├── discord_adapter/             # ── FARID ── send / set_receiver
├── ops/                         # ── FARID ── certificados, copias, registros, reportes de seguridad
│
└── docs/
    ├── README.md                # el informe (GitHub Pages)
    ├── REPARTO.md
    ├── api/                     # contratos
    ├── dpia/                    # DPIA (Elmer)
    ├── guia/                    # ejecución local y despliegue en EC2
    ├── trazabilidad/            # tabla generada por ops.trazabilidad
    ├── politicas/               # políticas y plan de incidentes (Farid)
    └── img/                     # diagramas
```

**Dependencias permitidas** (sin ciclos, para trabajar en paralelo):

```
frontend ──HTTP──▶ client ──▶ crypto
                     ├──▶ directory/client_lib ──TLS──▶ directory ──▶ Postgres
                     └──▶ discord_adapter ──API──▶ Discord
```

- `crypto/` no importa otros componentes del proyecto. El texto plano queda en el dispositivo: el cliente lo procesa y el frontend lo muestra.
- `directory/` y `discord_adapter/` no importan `crypto/` (salvo la verificación de firmas y la seudonimización de IDs en el directorio). El directorio maneja también datos privados de autenticación, pero no la contraseña maestra ni el texto de los chats.
- Ninguno de los servicios registra contenido de mensajes ni llaves.

**Convenciones.** Ramas `elmer/<tarea>` y `farid/<tarea>`, con revisión del otro. Commits al estilo `feat(crypto): …` y `docs(informe): …`. Nunca versionamos `.env`, llaves, la bóveda ni volcados de base de datos. Python 3.12, dependencias con versión fija por componente. Nombramos las pruebas por requerimiento (`test_RS4_nonce_unico`) para armar la tabla de trazabilidad. Ejecutamos las pruebas por carpeta (`cd crypto && ../.venv/bin/python -m pytest`).

## 5. Orden de trabajo

1. Implementamos la criptografía, el cliente, el frontend, el directorio, el transporte por Discord y las operaciones; desplegamos y probamos el MFA con Microsoft Authenticator.
2. Mantener el informe, la DPIA, el inventario de autenticación y las instrucciones de recuperación al día.
3. Observar una ejecución automática de los respaldos en S3, registrar el simulacro de incidentes y probar el inicio de sesión del servicio recuperado con su clave de cifrado TOTP.
4. Completar la parte de Elmer de las lecciones aprendidas y de las conclusiones, la presentación y el ensayo conjunto. Aprobamos la DPIA y consignamos nuestros correos como firma en el paso 7.

## 6. Lista de comprobación de la demostración (clientes locales y directorio en EC2)

- [ ] **Escenario principal:** Elmer y Farid, cada uno en su laptop con su cliente y su bot, en el canal `#e2ee-relay`. Pantalla dividida: Discord (se ven `hs1`, `hs2`, `hs3` y luego solo `E2EE1:…` ilegible) frente a la aplicación (texto plano).
- [ ] Elmer envía un mensaje; Farid lo ve descifrado en su aplicación y responde; en Discord ambos son texto cifrado publicado por bots.
- [ ] Mostrar que un tercero con acceso al canal (o el propio Discord) no puede leerlo.
- [ ] Mensaje alterado o repetido: aparece como "no descifrable" o se ignora.
- [ ] Directorio por HTTPS con la CA propia; un certificado inválido se bloquea sin opción de continuar.
- [ ] Verificación de la huella fuera de banda e insignia; cambio de llave: alerta y revocación automática.
- [ ] *Forward secrecy*: tras rotar la sesión, un mensaje antiguo no se descifra con las claves actuales.
- [ ] Un usuario no puede sobrescribir la llave de otro (prueba de acceso ajeno).
- [ ] Registros de auditoría, una copia de seguridad cifrada con su restauración, y el reporte del análisis de código (antes y después).
- [ ] Mostrar desbloqueo con contraseña y Authenticator, rechazo de un código reutilizado y bloqueo por vencimiento de la sesión local.
- [ ] Mostrar que una caída del directorio impide nuevos desbloqueos; no confundirlo con la demo offline sin MFA.
- [ ] La DPIA, la recuperación del autenticador y el plan de incidentes.
