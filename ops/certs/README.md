# TLS 1.3 con CA propia (F2, RS6, C-07)

## Cadena de confianza

```
CA del directorio de llaves  (ECDSA P-256, 5 años, pathlen 0, solo firma certificados y CRL)
 └── localhost / 127.0.0.1    (ECDSA P-256, 90 días, solo serverAuth)
```

* El cliente **solo** confía en `ca.pem`: `directory.client_lib.tls_context` crea un contexto vacío (sin las CA del sistema), carga esa CA, verifica el nombre del host y exige **TLS 1.3 como mínimo**. El servidor (`python -m directory.serve`) tampoco acepta nada por debajo de TLS 1.3.
* Ante cualquier fallo (otra CA, certificado vencido, nombre distinto, revocado, TLS 1.2) la conexión se corta y el cliente lanza `DirectoryError`, que el orquestador convierte en "no se pudo consultar el directorio". **No existe opción de continuar** ni parámetro para desactivar la verificación.
* ¿Por qué una CA propia y no una pública? El directorio es la pieza que podría sustituir llaves (R2). Si el cliente confiara en todas las CA públicas, cualquiera de ellas podría emitir un certificado para el directorio. Con una CA propia, la superficie se reduce a una sola llave que controla el equipo.
* `ca.pem` y `crl.pem` se distribuyen junto con el cliente (o se copian a mano en la demo). La llave de la CA nunca sale del equipo del responsable.

## Operación

```bash
set -a; . ./.env; set +a                  # CA_KEY_PASSWORD
python -m ops.certs.pki init               # una vez: CA + certificado del servidor + CRL vacía
python -m ops.certs.pki issue              # cada 60 días como máximo (vence a los 90); renueva también la CRL
python -m ops.certs.pki revoke <serial>    # revocación; el serial lo imprime `issue`
python -m directory.serve                  # https://localhost:8443
```

| Archivo | Contenido | ¿Se versiona? |
|---|---|---|
| `ca.pem`, `crl.pem` | Certificado de la CA y lista de revocación (públicos) | No: se generan por instalación |
| `server.pem` | Certificado del directorio | No |
| `private/ca.key` | Llave de la CA, **cifrada** con `CA_KEY_PASSWORD` | Nunca |
| `private/server.key` | Llave del servidor (sin cifrar para que arranque solo; permisos 600) | Nunca |
| `revoked.json` | Seriales revocados, para regenerar la CRL | No |

## Revocación

* **Certificado del servidor comprometido** (por ejemplo, se filtró `server.key`): `revoke <serial>`, `issue` y distribuir el nuevo `crl.pem`. Con `DIRECTORY_CRL_FILE` configurado, el cliente rechaza el certificado revocado (`VERIFY_CRL_CHECK_LEAF`).
* **La CRL vence a los 30 días.** Si el cliente tiene configurada una CRL vencida, falla cerrado. `issue` y `revoke` la regeneran. Programar `issue` mensualmente cubre ambos plazos.
* **Llave de la CA comprometida:** no se puede revocar a sí misma. Se crea una CA nueva (`init` en otra carpeta), se reemplaza `ca.pem` en todos los clientes y se trata como incidente (ver `docs/politicas/respuesta-incidentes.md`). Como la llave de la CA está cifrada y fuera del servidor del directorio, robar el servidor no basta para emitir certificados.
* No se usa OCSP: con un solo servidor y clientes conocidos, una CRL distribuida a mano es más simple y no filtra a un tercero qué clientes consultan el directorio.

## Notas

* `curl` en Windows (schannel) intenta además su propia comprobación de revocación y falla con certificados sin punto de distribución. Para probar a mano: `curl --ssl-no-revoke --cacert ops/certs/ca.pem https://localhost:8443/v1/keys/<id>`.
* La URI de redirección de OAuth2 en el portal de Discord pasa a ser `https://localhost:8443/auth/callback`.
