# Reparto de trabajo y estado

Plan de trabajo del equipo para la entrega final. Cada persona es dueña de módulos distintos para avanzar sin depender de la otra; lo compartido se acuerda como contratos (sección 3). La demostración puede ser **en local**, con la API real de Discord.

Leyenda de estado: ✔ hecho y probado · ◐ a medias · ○ pendiente.

## 1. Diseño de seguridad (resumen)

El diseño completo y su justificación están en el informe ([README.md](README.md), secciones 2 y 4.2). En una línea: identidad Ed25519 que solo firma; *handshake* autenticado de tres mensajes con Diffie-Hellman efímero en ambos extremos (X25519), claves de sesión distintas por dirección con HKDF-SHA256, mensajes con AES-256-GCM, contador anti-*replay* y rotación a los 100 mensajes o 8 h; ceremonia de verificación fuera de banda con *pin* de llaves.

**Discord como transporte.** La API oficial no permite escribir en nombre de un usuario, así que cada persona usa su propio bot en un canal privado del servidor del proyecto. El autor que muestra Discord siempre es un bot y no se usa: el emisor y el receptor viajan dentro del mensaje y se autentican con el *handshake*.

## 2. Reparto

### Elmer — Criptografía, cliente local, frontend, diseño, privacidad y ética

Informe: Motivación, Trasfondo Teórico, Diseño, privacidad y ética (DPIA incluida), riesgos y recomendaciones.

| ID | Tarea | Estado |
|---|---|---|
| E1 | Protocolo (*handshake* autenticado con PFS), secciones 2, 4.2 y 5.2 del informe, diagramas y tabla de ataques considerados | ✔ |
| E2 | Librería `crypto/`: identidad y bóveda (Argon2id + AES-GCM), exportación/importación, *handshake*, sesión, huella. Con pruebas de los caminos de rechazo | ✔ (110 pruebas) |
| E3 | API local del cliente (`client/`): orquesta crypto, directorio y Discord; cola de salida, reintentos, rotación, alerta de cambio de llave | ✔ (55 pruebas) |
| E4 | Frontend en Next.js (`frontend/`): identidad, contactos, chat, verificación, alertas | ✔ (18 pruebas + 15 en navegador). Falta dibujar el código QR |
| E5 | DPIA con la plantilla de siete pasos ([dpia/DPIA.md](dpia/DPIA.md)); consentimiento por versión en cliente y frontend | ✔ (firmas pendientes) |
| E6 | Ética y privacidad: aviso de privacidad completo ([privacidad/aviso-de-privacidad.md](privacidad/aviso-de-privacidad.md), publicado también en la aplicación), cumplimiento de la Ley 29733 y consideraciones éticas (informe, secciones 6.2 y 6.3) | ✔ (falta completar domicilio y correo del equipo antes de un uso real) |
| E7 | Clasificación de datos y técnicas de privacidad (informe, sección 6.4); seudonimización con HMAC y enmascarado de referencia en `crypto/pseudonym.py` | ✔ (16 pruebas) |
| E8 | Riesgos de una brecha y entidades afectadas (informe, sección 7) y recomendaciones futuras (sección 8) | ✔ |
| E9 | Lecciones aprendidas y retrospectiva (parte de Elmer) | ○ |

### Farid — Directorio, Discord, operaciones y herramientas

Informe: Requerimientos, Implementación lograda, operaciones, políticas e incidentes.

| ID | Tarea | Estado |
|---|---|---|
| F1 | **Directorio de llaves** (FastAPI + PostgreSQL). Publicar o cambiar una llave exige **prueba de posesión** (`verify_registration` ya está en `crypto/`) y vincular el ID con OAuth2 (`identify`); solo el dueño modifica su registro. Consultas parametrizadas, *rate-limit*, errores genéricos, **rol de base de datos con permisos mínimos**. Guarda solo ID, llave pública, fechas y **la versión del aviso aceptado**. Endpoint de cancelación | ○ |
| F2 | **TLS 1.3 con CA propia**: el cliente valida contra esa CA y no permite continuar si falla. Documentar la cadena de confianza y la revocación | ○ |
| F3 | **Adaptador de Discord** (`discord.py`): servidor privado, canal `#e2ee-relay` y un bot por persona; publicar y leer mensajes `E2EE1:` ignorando el autor; token en variables de entorno | ○ |
| F4 | **Copias de seguridad**: `pg_dump` programado y cifrado, fuera del servidor, con restauración probada y rotación de 30 días | ○ |
| F5 | **Registros de auditoría y alertas**: eventos de registro y cambio de llave, fallos de firma, enumeración; sin texto, llaves ni IDs en claro (usar `Pseudonymizer` de `crypto/pseudonym.py` con la clave en `PSEUDONYM_KEY`); retención de 90 días | ○ |
| F6 | **Análisis de código**: Bandit o Semgrep, pip-audit con SBOM, gitleaks y pruebas de acceso ajeno por endpoint, en CI; reportes antes y después | ○ |
| F7 | **Políticas de uso seguro** y **plan de respuesta a incidentes** (NIST SP 800-61 rev. 3), con notificación a la ANPD en 48 h | ○ |
| F8 | Informe: requerimientos actualizados, implementación lograda y tabla de trazabilidad requerimiento ↔ evidencia | ○ |
| F9 | Lecciones aprendidas y retrospectiva (parte de Farid) | ○ |

### Compartido (al final)

- Integración de extremo a extremo y ensayo de la demostración.
- Presentación (Elmer: motivación, diseño y DPIA; Farid: implementación, operaciones y resultados de las herramientas).
- Revisión cruzada: cada uno revisa la sección del otro. Si hay otro grupo disponible, intercambiar DPIAs con la lista de revisión (inventario, riesgos que faltan, puntuación).
- Publicar el informe en GitHub Pages (vive en `docs/README.md`).

## 3. Contratos entre las dos partes

| Contrato | Dónde | Lo usan |
|---|---|---|
| Formato de mensaje en Discord (`E2EE1:<base64url(JSON)>`, tipos `hs1`, `hs2`, `hs3`, `msg`) | [`crypto/API.md`](../crypto/API.md) | `client/`, adaptador de Discord |
| Interfaz de la librería | [`crypto/API.md`](../crypto/API.md) | `client/`; el directorio solo usa `verify_registration`, `verify_key_change`, `Pseudonymizer` y `mask_id` |
| Puertos del directorio y de Discord | [`client/ports.py`](../client/ports.py) y [`client/README.md`](../client/README.md) | Farid los implementa; `client/fakes.py` es la referencia de comportamiento |
| API local cliente ↔ frontend | [`api/client.openapi.json`](api/client.openapi.json) | `frontend/` |
| API del directorio | `api/directory.yaml` (○ a definir por Farid) | `client/`, directorio |

Puntos que el directorio debe cumplir y que el cliente ya asume:

- `register(discord_id, public_key, sign, consent_version)` guarda la versión del aviso aceptado y la fecha.
- `get_key(discord_id)` devuelve `None` si la persona no está registrada, y cualquier fallo se lanza como `DirectoryError`.
- Para trabajar sin esperar: `python -m client.dev` levanta dos clientes con un directorio y un canal en memoria.

## 4. Estructura del proyecto

Monorepo. Cada carpeta tiene un solo dueño para evitar conflictos de git.

```
EySDatos_Proyect/
├── README.md
├── .env.example                 # variables sin valores; el .env real va en .gitignore
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
    ├── politicas/               # políticas y plan de incidentes (Farid)
    └── img/                     # diagramas
```

**Dependencias permitidas** (sin ciclos, para trabajar en paralelo):

```
frontend ──HTTP──▶ client ──▶ crypto
                     ├──▶ directory/client_lib ──TLS──▶ directory ──▶ Postgres
                     └──▶ discord_adapter ──API──▶ Discord
```

- `crypto/` no importa a nadie y es lo único que ve texto plano y llaves privadas.
- `directory/` y `discord_adapter/` no importan `crypto/` (salvo la verificación de firmas y la seudonimización de IDs en el directorio): solo manejan texto cifrado y llaves públicas.
- Ninguno de los servicios registra contenido de mensajes ni llaves.

**Convenciones.** Ramas `elmer/<tarea>` y `farid/<tarea>`, con revisión del otro. Commits al estilo `feat(crypto): …` y `docs(informe): …`. Nunca se versiona `.env`, llaves, la bóveda ni volcados de base de datos. Python 3.12, dependencias con versión fija por componente. Los tests se nombran por requerimiento (`test_RS4_nonce_unico`) para armar la tabla de trazabilidad. Las pruebas se corren por carpeta (`cd crypto && ../.venv/bin/python -m pytest`).

## 5. Orden de trabajo

1. Hecho: diseño, `crypto/`, `client/`, `frontend/`, DPIA y aviso de privacidad.
2. Ahora, en paralelo: **E9** (Elmer, al final) ‖ **F1, F2, F3** (Farid).
3. Luego: **F4, F5, F6** y **F7** (Farid); integración.
4. Al final: lecciones aprendidas, presentación y ensayo.

## 6. Lista de comprobación de la demostración (local)

- [ ] **Escenario principal:** Elmer y Farid, cada uno en su laptop con su cliente y su bot, en el canal `#e2ee-relay`. Pantalla dividida: Discord (se ven `hs1`, `hs2`, `hs3` y luego solo `E2EE1:…` ilegible) frente a la aplicación (texto plano).
- [ ] Elmer envía un mensaje; Farid lo ve descifrado en su aplicación y responde; en Discord ambos son texto cifrado publicado por bots.
- [ ] Mostrar que un tercero con acceso al canal (o el propio Discord) no puede leerlo.
- [ ] Mensaje alterado o repetido: aparece como "no descifrable" o se ignora.
- [ ] Directorio por HTTPS con la CA propia; un certificado inválido se bloquea sin opción de continuar.
- [ ] Verificación de la huella fuera de banda e insignia; cambio de llave: alerta y revocación automática.
- [ ] *Forward secrecy*: tras rotar la sesión, un mensaje antiguo no se descifra con las claves actuales.
- [ ] Un usuario no puede sobrescribir la llave de otro (prueba de acceso ajeno).
- [ ] Registros de auditoría, una copia de seguridad cifrada con su restauración, y el reporte del análisis de código (antes y después).
- [ ] La DPIA y el plan de incidentes (48 h).
