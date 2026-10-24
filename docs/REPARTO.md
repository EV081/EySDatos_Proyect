# Reparto de trabajo – Entrega Final (alineado con las clases)

Rúbrica final (4 pts c/u): requerimientos de seguridad, requerimientos de funcionalidad, informe escrito (con DPIA y ética), demo en vivo, presentación. La demo puede ser **en local**, con la API real de Discord, backend y frontend corriendo en la laptop.

Material de clase usado: `docs/esquema/ppts/` (S01–S11, L11). Entre paréntesis se indica la sesión que respalda cada decisión; así el informe puede citarla ("como vimos en clase…").

## 0. Qué nos descontaron en la entrega 1 (15/20) y qué dice la clase

| Criterio | Nota | Corrección pedida | Respaldo en clase |
|---|---|---|---|
| Seguridad | 1.5/4 | Faltan **backups, logs, herramienta de análisis de código, políticas de uso, plan de respuesta a incidentes** | S02-L1 (defensa en profundidad, NIST 800-61r3, backups fuera del dominio de falla), S07-Vuln (SAST/SCA, A09 logging), L11 (medidas y política) |
| Diseño | 1.5/4 | (a) "Efímero" con llave pública **de larga vida** del receptor: robar su privada descifra todo el historial. (b) **No se autentica al emisor** | S09: la "trifecta" = autenticación mutua + llave de sesión + **PFS**; TLS 1.3 eliminó el RSA/DH estático justo por esto. S09: firmar `[contexto ‖ …]`, identidades dentro del mensaje (Abadi–Needham), orden firmar/cifrar (Davis) |

Además, el esquema final exige y hoy no tenemos: análisis con herramienta, riesgos, plan de incidentes, recomendaciones futuras, **DPIA**, ética/privacidad, certificados (CA propia), lecciones aprendidas y retrospectiva, frontend + backend funcionando.

## 1. Decisión de diseño recomendada (para cerrar el punto de "Diseño")

Reemplazar el "ECDH contra la llave estática del receptor" por un **handshake autenticado con DH efímero en ambos lados** (patrón SSH/TLS 1.3 de S09, diap. 31/44/48). Es la clase misma aplicada a Discord, sin agregar nada que no hayamos visto.

- **Identidad**: solo un par **Ed25519 (firma)**. Ya no hay llave DH estática. El directorio publica únicamente esta llave. (S09: *un par de llaves por propósito*; S05: firma ≠ cifrado.)
- **Handshake** (mensajes sobre Discord; ids en claro, firmas cubren toda la transcripción):
  1. A→B: `"Alice", R_A, gᵃ`
  2. B→A: `R_B, gᵇ, [ctx ‖ "Bob" ‖ "Alice" ‖ R_A ‖ R_B ‖ gᵃ ‖ gᵇ]_Bob`
  3. A→B: `[ctx ‖ "Alice" ‖ "Bob" ‖ R_A ‖ R_B ‖ gᵃ ‖ gᵇ]_Alice`
  - `a`, `b` efímeros, **destruidos** al derivar la clave → **PFS en ambos extremos** (S09 diap. 28–31).
  - `ctx` fija el propósito de la firma (**separación de dominio**, TLS 1.3 "CertificateVerify", S09 diap. 25).
  - Los roles son **asimétricos** y cada firma incluye la identidad de quien firma y del destinatario (evita reflexión y oráculo, S09 diap. 18–19, principio 3 de Abadi–Needham).
  - Transcripción completa firmada: un MITM que degrade algo invalida las firmas (S09 diap. 44, SSH).
- **Clave de sesión**: `K = HKDF-SHA256(gᵃᵇ, hash(transcripción))` → **AES-256-GCM**, AAD = ids + contador (S03: AEAD por defecto; nonce nunca repetido).
- **Mensajes**: contador monótono + caché de vistos → anti-replay (S09 diap. 22: timestamps/nonces + caché). Si GCM no valida → "mensaje no descifrable".
- **Rotación (RS9)**: nuevo handshake cada N mensajes o T tiempo; la clave anterior se borra.
- **Verificación OOB**: huella `SHA-256(pk_A ‖ pk_B)` ordenada, comparada fuera de Discord. Es la defensa contra **TOFU** (S09 diap. 45, SSH) y contra la sustitución de llaves del directorio. Pin de llave + alerta de cambio (RF8).
- **Limitación honesta**: el handshake es interactivo (ambos online al establecer sesión); Discord persiste los mensajes, así que un mensaje queda en cola hasta que el handshake se complete. Documentarlo en 5.6.

Si prefieren no cambiar tanto, la alternativa es X3DH/prekeys (asíncrono), pero **no se vio en clase**; se justificaría peor ante la rúbrica.

## 2. Reparto (módulos disjuntos)

### Elmer — Criptografía, cliente local, frontend, informe de diseño, privacidad y ética
Informe: Motivación, Trasfondo Teórico, Diseño, DPIA, ética/legal, riesgos, recomendaciones.

| ID | Tarea | Clase |
|---|---|---|
| E1 | Especificar el protocolo de §1 y actualizar secciones 2, 4.2 y 5.2 + los 3 diagramas excalidraw (arquitectura, mensaje, verificación). Agregar una **tabla de ataques considerados** (replay, reflexión, oráculo de firma/descifrado, MitM en el directorio, degradación, harvest-now-decrypt-later) y por qué cada uno falla | S09 (ejercicio "rompe el protocolo"), S05 (DH sin auth ⇒ MitM) |
| E2 | Librería `crypto/` (Python, `cryptography` + `argon2-cffi`): keygen Ed25519, bóveda de identidad (Argon2id + salt, AES-GCM), export/import (RF12), handshake, HKDF, AEAD, huella, rotación. **Tests**: tag GCM inválido, **firma inválida debe rechazar** (lección *goto fail*), replay, nonce único, orden de roles | S03, S04 (Argon2id, salt), S05, S09 (goto fail, Heartbleed: pruebas de caminos negativos) |
| E3 | **API local del cliente** (FastAPI en localhost) que orquesta crypto + directorio + Discord; sin exponer tokens ni llaves privadas (RS10, RS1) | S06 (authn/authz), S07-Vuln |
| E4 | **Frontend web** simple: registro/desbloqueo con contraseña maestra, lista de chats, candado, insignia de verificado, alerta de cambio de llave, "no descifrable", huella/QR. Se desarrolla contra mock de la API local | S09 (advertencias de certificado: no dar botón de "continuar" ante cambio de llave, ejemplo HSTS) |
| E5 | **DPIA con la plantilla `esquema/ppts/dpia-template (1).docx`** (formato ICO, 7 pasos), llenada en el informe (sección Privacidad y Ética): 1 necesidad de DPIA → 2 descripción (naturaleza, alcance, contexto, propósito; con el diagrama de flujo de datos de `img/arquitectura.png`) → 3 consulta (usuarios, procesadores como Discord, expertos en seguridad; o justificar por qué no) → 4 necesidad y proporcionalidad (base legal, minimización, prevención de *function creep*, derechos, transferencias internacionales) → 5 riesgos (probabilidad × severidad → riesgo global; **≥5 riesgos, recorriendo LINDDUN y el ciclo de vida incl. backups y logs**) → 6 medidas (efecto, riesgo residual, aprobada sí/no), redactadas como **restricciones verificables** (C-01, C-02…) → 7 aprobación (nosotros como responsables; documentar que no hay DPO y quién revisa). Si queda un riesgo residual alto, no se lanza. Nota: la plantilla es del ICO (UK/GDPR); adaptar la base legal y la notificación a Ley 29733 (ANPD, 48 h) | L11, S11 |
| E6 | **Ética y privacidad / cumplimiento**: Ley 29733 y reglamento DS 016-2024-JUS (finalidad, proporcionalidad, derechos ARCO + portabilidad como requisitos de diseño: exportar identidad = RF12, borrar llave del directorio = cancelación, plazos de retención), aviso de privacidad (art. 18), registro de consentimiento por finalidad y versión, notificación de brecha en **48 h** (ANPD), extraterritorialidad GDPR si hay usuarios en la UE, dónde corre el servidor. Dilemas éticos de S09: acceso excepcional / key escrow (**decisión explícita: no hay backdoor**), quién controla las llaves, interceptación TLS | S11, L11, S09 diap. 60 |
| E7 | **Clasificación de datos y técnicas de privacidad**: tabla de campos (llave pública, discord_id, metadatos, texto plano, ciphertext, logs) con nivel de sensibilidad y técnica (minimización, seudonimización con HMAC para logs, enmascarado). Mencionar que los metadatos quedan expuestos (límite reconocido) y el riesgo de re-identificación (caso Netflix) | S10 |
| E8 | **Riesgos** (brecha de Discord, del directorio, robo de dispositivo; entidades afectadas) y **Recomendaciones futuras** (ZK/credenciales anónimas, ratchet por mensaje, transparencia de llaves/auditoría externa, HSM, MFA/passkeys, protección de metadatos) | S02-L1, S09 (ZK), S06 |
| E9 | Lecciones aprendidas y retrospectiva (parte de Elmer) | — |

### Farid — Directorio, Discord, seguridad operacional y herramientas
Informe: Requerimientos, Implementación lograda, operaciones, políticas e incidentes.

| ID | Tarea | Clase |
|---|---|---|
| F1 | **Directorio de llaves** FastAPI + PostgreSQL. **Authn**: publicar/rotar una llave exige **prueba de posesión** (challenge-response con nonce, firmando `[ctx ‖ nonce]`) y vincular el `discord_id` vía OAuth2 (scope `identify`). **Authz**: solo el dueño modifica su registro; los demás solo leen. Consultas parametrizadas (SQLAlchemy), rate-limit anti-enumeración, errores genéricos con correlation id. **Roles de BD con GRANT/REVOKE mínimo** (app no es owner) | S06 (authn≠authz, confused deputy), S07-BD (SQLi, GRANT/REVOKE, RBAC), S07-Vuln (A01, A05, A10), S09 (challenge-response, separación de dominio) |
| F2 | **TLS 1.3 + certificados**: CA raíz propia + certificado del directorio (openssl/mkcert), el cliente valida contra esa CA y **no permite continuar** si falla (RS6). Documentar la cadena de confianza, expiración y revocación (cómo se invalida un cert comprometido) | S05 (PKI, revocación), S09 (TLS 1.3, CA raíz, HSTS) |
| F3 | **Adaptador Discord** (`discord.py`): enviar/recibir texto cifrado con prefijo `E2EE1:`, cola de mensajes pendientes hasta completar handshake, token en `.env` (RS10), OAuth2/bot (RF10). Trabajar contra stub de crypto hasta que llegue E2 | S07-Vuln (A02/A07 secretos, A03 cadena de suministro) |
| F4 | **Backups y recuperación**: `pg_dump` programado y **cifrado** (AES-GCM, llave fuera del repo y del servidor), **copia fuera del dominio de falla** (no en el mismo host/red), script de restauración **probado**, documentar RPO/RTO y plazo de retención del backup (cuenta para el derecho de cancelación) | S02-L1 ("el backup en la misma red que el ransomware"), S07-BD (cifrado en BD y gestión de llaves), L11 |
| F5 | **Logs de auditoría y alertas**: eventos de publicar/rotar/cambiar llave, fallos de firma, intentos de enumeración; **sin texto plano, sin llaves, ids seudonimizados** (RS3). Alertas básicas (p.ej. N fallos seguidos, cambio de llave masivo) | S07-Vuln (A09 Logging & Alerting), S02-L1 (MTTD/MTTR), L11 (logs sin datos personales) |
| F6 | **Herramientas de análisis**: SAST (**Bandit**/Semgrep), SCA (**pip-audit**/Trivy) + **SBOM**, escaneo de secretos (gitleaks) y **tests de "acceso ajeno"** por endpoint. Ejecutar en CI (GitHub Actions), guardar reportes antes/después, corregir hallazgos y mapear a OWASP Top 10:2025 (checklist A01–A10) | S07-Vuln, S02-L1 |
| F7 | **Políticas de uso seguro** (contraseña maestra, secretos, rotación, concientización/formación del equipo, mínimo privilegio) y **Plan de respuesta a incidentes** según **NIST SP 800-61r3**: preparación → detección/análisis → contención → erradicación → recuperación → lecciones; roles, **notificación a la ANPD en 48 h** (el reloj corre desde el conocimiento), revocación y rotación de llaves, preservación de evidencia con hash | S02-L1, S11, L11 |
| F8 | Informe: **Requerimientos actualizados**, **Implementación lograda** y **tabla de trazabilidad** RF/RS ↔ evidencia (archivo, test, captura, reporte) | — |
| F9 | Lecciones aprendidas y retrospectiva (parte de Farid) | — |

### Compartido (al final, ~1 día)
- Integración end-to-end y ensayo de la demo.
- Presentación (Elmer: motivación, diseño, DPIA/ética; Farid: implementación, operaciones, seguridad y resultados de herramientas).
- **Revisión cruzada**: cada uno revisa la sección del otro con el criterio de la rúbrica. Si hay otro grupo disponible, intercambiar DPIAs como en el Lab 11.
- Publicar en GitHub Pages (el informe ya vive en `docs/README.md`).

## 3. Contratos para no depender del otro (definir el día 1, ~1 h)

1. **Formato de mensaje en Discord** (`E2EE1:<base64(JSON)>`): tipos `hs1`, `hs2`, `hs3`, `msg` con `{v, type, from, to, session_id, ctr, nonce, ct, …}`. Usan E2 y F3.
2. **API del directorio** (`docs/api/directory.yaml`, OpenAPI): `GET /challenge`, `PUT /keys/{discord_id}` (llave pública + firma del challenge), `GET /keys/{discord_id}`, `GET /keys/{discord_id}/history`. Usan F1 y el cliente (E3).
3. **Interfaz de `crypto/`** (`crypto/API.md`): `create_identity(pw)`, `unlock(pw)`, `start_handshake(peer)`, `handle(wire)`, `encrypt(session, msg)`, `decrypt(wire)`, `fingerprint(pk_a, pk_b)`, `export/import`. F3 usa un stub passthrough hasta que E2 termine.
4. **Interfaz del adaptador Discord**: `send(user_id, text)`, `on_message(callback)`. E3 lo consume; F3 lo implementa. Y un cliente HTTP del directorio (`DirectoryClient`) que F1 entrega para E3.
5. **API local ↔ frontend** (`docs/api/client.yaml`): `/identity`, `/contacts`, `/conversations/{id}/messages`, `/verify`. E4 usa un mock.

### Estructura del proyecto

Monorepo en la raíz de `EySDatos_Proyect/`. Cada carpeta tiene un solo dueño, para que casi no haya conflictos de git. `docs/` ya existe y cada uno edita solo sus secciones.

```
EySDatos_Proyect/
├── README.md                    # cómo levantar todo en local (ambos)
├── .env.example                 # variables sin valores; el .env real va en .gitignore (RS10)
├── docker-compose.yml           # Postgres + directorio (+ proxy TLS); demo con un solo comando (Farid)
├── Makefile                     # make dev | test | scan | backup | restore (ambos)
├── .github/workflows/ci.yml     # tests + Bandit + pip-audit + gitleaks (Farid, F6)
│
├── crypto/                      # ── ELMER ── librería pura, sin red ni Discord (E2)
│   ├── API.md                   # contrato de funciones (§3.3)
│   ├── identity.py              # Ed25519, bóveda Argon2id+AES-GCM, export/import
│   ├── handshake.py             # hs1/hs2/hs3, firmas con ctx, HKDF
│   ├── session.py               # AES-256-GCM, contador, anti-replay, rotación
│   ├── fingerprint.py           # SHA-256(pk_A‖pk_B) -> 60 dígitos, QR
│   └── tests/                   # vectores, firma inválida, tag inválido, replay, roles
├── client/                      # ── ELMER ── API local (FastAPI, solo localhost) (E3)
│   ├── main.py                  # rutas de client.yaml
│   ├── orchestrator.py          # une crypto + DirectoryClient + DiscordAdapter
│   ├── store.py                 # contactos, pines de llave, estado verificado
│   └── tests/
├── frontend/                    # ── ELMER ── web simple (E4)
│   ├── src/                     # candado, insignia, alerta de llave, "no descifrable"
│   └── mocks/                   # mock de client.yaml para trabajar sin el backend
│
├── directory/                   # ── FARID ── servicio de llaves (F1)
│   ├── app/                     # main.py, routes/, models.py, auth.py (challenge + OAuth2)
│   ├── migrations/              # esquema + roles de BD con GRANT/REVOKE mínimos
│   ├── client_lib/              # DirectoryClient en Python que importa client/ (F1 entrega)
│   └── tests/                   # incluye "acceso ajeno" por endpoint
├── discord_adapter/             # ── FARID ── send / on_message / cola de pendientes (F3)
│   ├── adapter.py
│   ├── stub_crypto.py           # passthrough hasta que exista crypto/
│   └── tests/
├── ops/                         # ── FARID ──
│   ├── certs/                   # script de CA propia y emisión (F2); *.key en .gitignore
│   ├── backup/                  # backup.sh, restore.sh, retención (F4)
│   ├── logging/                 # config de logs de auditoría y alertas (F5)
│   └── security/                # reportes Bandit/pip-audit/SBOM antes y después (F6)
│
└── docs/                        # informe en GitHub Pages
    ├── README.md                # el informe (secciones repartidas según §2)
    ├── REPARTO.md
    ├── api/                     # directory.yaml, client.yaml, wire-format.md (día 1, juntos)
    ├── dpia/                    # DPIA llenada con la plantilla ICO (Elmer, E5)
    ├── politicas/               # políticas de uso y plan de incidentes (Farid, F7)
    ├── img/                     # diagramas y excalidraw
    └── esquema/                 # enunciado, rúbrica y ppts (solo lectura)
```

**Dependencias permitidas** (evitan ciclos y permiten trabajar en paralelo):

```
frontend -> client -> crypto
                  \-> directory/client_lib  -> (HTTPS) -> directory -> Postgres
                  \-> discord_adapter       -> (API) -> Discord
```

- `crypto/` no importa a nadie. Es lo único que ve texto plano y llaves privadas.
- `directory/` y `discord_adapter/` nunca importan `crypto/`: solo manejan ciphertext y llaves públicas. Es la separación que defendemos en el límite de confianza (4.2.1).
- Ni `directory/` ni `discord_adapter/` registran contenido de mensajes ni llaves (RS3).

**Convenciones**
- Ramas `elmer/<tarea>` y `farid/<tarea>` (p. ej. `elmer/E2-crypto`), PR cortos a `main`, y el otro revisa.
- Commits como los actuales: `feat(crypto): ...`, `docs(informe): ...`.
- Nunca se versiona `.env`, `*.key`, la bóveda de identidad ni los volcados de BD.
- Python 3.12 con `uv` o `venv` por componente (`requirements.txt` con versiones fijadas, que alimenta el SBOM y pip-audit).
- Un test por requerimiento: nombrarlos `test_RS4_nonce_unico` para que la tabla de trazabilidad (F8) salga casi sola.

## 4. Cambios en requerimientos (acordar el día 1)

- **RF**: autenticación mutua por firma en el handshake; rechazo de sesión si la firma o el challenge no valida; restaurar identidad desde export.
- **RS**: PFS (efímeros destruidos tras derivar clave); firma con separación de dominio y transcripción completa; anti-replay (contador + caché); llaves por propósito (solo Ed25519 de identidad); prueba de posesión para publicar en el directorio; roles de BD con mínimo privilegio y consultas parametrizadas; backups cifrados fuera del dominio de falla; logs de auditoría sin datos sensibles; SAST/SCA en CI; CA propia con validación estricta (sin "continuar de todos modos").
- **Corregir del informe actual**: 5.3 dice "alerta de RF9" pero es **RF8**; la sección 2 menciona RSA/ECC pero el diseño solo usa X25519 efímero + Ed25519; RS9 y forward secrecy deben apuntar al nuevo mecanismo de rotación; 3.2 y modelo de amenaza: aclarar qué hace cada adversario con el nuevo protocolo.

## 5. Orden sugerido

1. Día 1 (juntos): §1 aprobado, contratos §3, requerimientos §4.
2. En paralelo: **E1→E2** ‖ **F1, F2, F3**.
3. Luego: **E3, E4** ‖ **F4, F5, F6**.
4. Documentos: **E5–E8** ‖ **F7, F8**.
5. Integración, pruebas negativas, ensayo de demo, presentación.

## 6. Checklist de la demo en vivo (local)

- [ ] Dos usuarios (dos perfiles de navegador) con identidad generada localmente y protegida por contraseña maestra.
- [ ] Mensaje real por Discord: Discord muestra solo `E2EE1:…`; el front muestra el texto plano.
- [ ] Mensaje alterado o firma inválida → "no descifrable"; replay del mismo mensaje → rechazado.
- [ ] Handshake con MITM simulado (directorio devuelve otra llave) → la huella no coincide / alerta de cambio.
- [ ] Verificación de huella fuera de banda + insignia; cambio de llave → revocación automática.
- [ ] **PFS**: tras rotar y destruir efímeros, la llave de identidad robada no descifra tráfico viejo.
- [ ] Directorio por HTTPS (TLS 1.3) con CA propia; certificado inválido → bloqueado sin opción de continuar.
- [ ] Un usuario no puede sobrescribir la llave de otro (test de acceso ajeno).
- [ ] Mostrar logs de auditoría, un backup cifrado + restauración, y el reporte de Bandit/pip-audit (antes/después).
- [ ] Mostrar la DPIA y el plan de incidentes (48 h).
