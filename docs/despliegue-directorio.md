# Desplegar el directorio en un servidor (opcional)

Solo el **directorio** (con su Postgres) se despliega. `client/` y el frontend siguen en la laptop de cada persona: ahí están las llaves privadas y el texto plano. El servidor solo guarda ID de Discord, llave pública, fechas y la versión del aviso aceptado.

```
laptop de cada persona:  frontend ─► client ─► Discord (#e2ee-relay)
                                        └────► directorio (servidor, https://<IP>:8443)
```

## 1. En el servidor (una instancia con Docker, p. ej. EC2)

1. Grupo de seguridad: abrir **solo el 8443** (TCP). Postgres no se expone: en `docker-compose.yml` solo escucha en `127.0.0.1`.
2. Clonar el repositorio y crear el `.env` desde `.env.example` (contraseñas, `PSEUDONYM_KEY`, `CA_KEY_PASSWORD` y la aplicación OAuth2 de Discord). El `.env` nunca se versiona.
3. Certificado con la IP o el nombre público en el SAN (el cliente verifica el nombre):
   ```bash
   export DIRECTORY_EXTRA_HOSTS=<IP-pública-o-dominio>
   set -a; . ./.env; set +a
   python -m ops.certs.pki init        # CA propia + certificado (localhost, 127.0.0.1 y lo de arriba)
   chmod 644 ops/certs/private/server.key   # el contenedor corre como uid 10001; ver nota
   ```
4. Base de datos y servicio:
   ```bash
   docker compose up -d db
   python -m directory.migrations.apply
   docker compose --profile deploy up -d --build directory
   ```
5. OAuth2: en el Developer Portal agregar la redirección `https://<IP-o-dominio>:8443/auth/callback` y poner el mismo valor en `DISCORD_REDIRECT_URI`.

> **Nota sobre `server.key`:** el contenedor no corre como root, así que necesita poder leer la llave del servidor. Es la llave del certificado del directorio, **no** la de la CA (que va cifrada y se queda fuera del servidor en lo posible). Si se filtra, se revoca (`ops/certs/README.md`).

## 2. En cada laptop

Copiar solo `ca.pem` (y `crl.pem`) desde el servidor y poner en el `.env` de la persona:

```
DIRECTORY_URL=https://<IP-o-dominio>:8443
DIRECTORY_CA_FILE=ops/certs/ca.pem
DIRECTORY_CRL_FILE=ops/certs/crl.pem
DISCORD_TOKEN=<token de SU bot>          # nunca el de otra persona
DISCORD_CHANNEL_ID=<ID del canal #e2ee-relay>
```

Luego `python -m directory.client_lib.login`, `make client` y `make frontend`. El frontend se abre contra el cliente **local** (`?api=http://127.0.0.1:8001&token=<CLIENT_API_TOKEN>`); nunca contra la IP del servidor.

## 3. Comprobación

```bash
curl --cacert ops/certs/ca.pem https://<IP-o-dominio>:8443/v1/keys/111111111111111111   # 404 = vivo y con TLS válido
```

Un cliente con una CA distinta, un certificado sin la IP en el SAN o uno vencido debe fallar sin ofrecer continuar (F2). Renovar con `python -m ops.certs.pki issue` antes de 90 días y programar las copias (`make backup`).
