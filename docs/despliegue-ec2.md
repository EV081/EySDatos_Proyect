# Desplegar el directorio en EC2 (AWS Academy) con la base en Supabase

Solo el **directorio** va al servidor; la base ya está en Supabase y `client/` + frontend siguen en cada laptop. El directorio sirve **TLS 1.3 con la CA propia del proyecto** (F2): el certificado se emite en tu laptop, la llave de la CA nunca sube al servidor.

```
laptop A: frontend ─► client ─► Discord (#e2ee-relay) ◄─ client ◄─ frontend :laptop B
                        └──────► directorio  https://<IP-elástica>:8443  ◄──────┘
                                        └──► Postgres (Supabase)
```

Requisitos previos: instancia Ubuntu 24.04 con **Elastic IP** asociada, grupo de seguridad con **22 desde tu IP** y **8443 desde 0.0.0.0/0**, y el `.pem` del key pair.

## 1. En tu laptop: certificado con la IP elástica
```bash
export DIRECTORY_EXTRA_HOSTS=<IP-elástica>
export CA_KEY_PASSWORD=<la contraseña de tu CA>
.venv/bin/python -m ops.certs.pki issue      # nuevo server.pem/server.key con localhost, 127.0.0.1 y la IP
chmod 644 ops/certs/private/server.key       # el contenedor corre como uid 10001 y debe poder leerla
```
(`issue`, no `init`: la CA ya existe y es la que tienen que seguir confiando las laptops.)

## 2. Copiar al servidor
```bash
IP=<IP-elástica>; KEY=~/Descargas/<keypair>.pem; chmod 400 $KEY
ssh -i $KEY ubuntu@$IP 'sudo apt-get update -qq && sudo apt-get install -y -qq docker.io docker-compose-v2 git && sudo usermod -aG docker ubuntu'
ssh -i $KEY ubuntu@$IP 'git clone https://github.com/EV081/EySDatos_Proyect.git && mkdir -p EySDatos_Proyect/ops/certs/private'
scp -i $KEY ops/certs/{ca.pem,crl.pem,server.pem} ubuntu@$IP:EySDatos_Proyect/ops/certs/
scp -i $KEY ops/certs/private/server.key       ubuntu@$IP:EySDatos_Proyect/ops/certs/private/
```
No se copia `private/ca.key` ni `revoked.json`.

## 3. `.env` del servidor
`ssh -i $KEY ubuntu@$IP`, luego `cd EySDatos_Proyect && nano .env` con **solo** esto:
```
DATABASE_URL=postgresql://directory_app.<ref>:<DIRECTORY_APP_PASSWORD>@aws-1-us-east-1.pooler.supabase.com:5432/postgres
DISCORD_CLIENT_ID=<id>
DISCORD_CLIENT_SECRET=<secreto vigente>
DISCORD_REDIRECT_URI=https://<IP-elástica>:8443/auth/callback
PSEUDONYM_KEY=<la misma que usabas en Render>
POSTGRES_PASSWORD=no-se-usa
```
(`POSTGRES_PASSWORD` solo está para que compose no se queje del servicio `db`, que aquí no se levanta.)

## 4. Levantar
```bash
docker compose --profile deploy up -d --build directory
docker compose logs -f directory        # debe decir "Uvicorn running on https://0.0.0.0:8443"
```
Se reinicia solo (`restart: unless-stopped`) cuando el lab vuelve a arrancar.

## 5. Discord
Developer Portal → OAuth2 → Redirects → añadir `https://<IP-elástica>:8443/auth/callback` (puedes borrar la de Render).

## 6. En cada laptop
```
DIRECTORY_URL=https://<IP-elástica>:8443
DIRECTORY_CA_FILE=ops/certs/ca.pem
DIRECTORY_CRL_FILE=ops/certs/crl.pem
DISCORD_TOKEN=<token del bot de cada uno>
DISCORD_CHANNEL_ID=<canal #e2ee-relay>
CLIENT_API_TOKEN=<cadena larga>
```
Quita `DIRECTORY_PUBLIC_CA`. Tu amigo necesita tu `ca.pem` y `crl.pem` (mándaselos; no son secretos) en su `ops/certs/`. Luego `python -m directory.client_lib.login`, `make client`, `make frontend`.

## 7. Comprobar
```bash
curl --cacert ops/certs/ca.pem https://<IP-elástica>:8443/v1/keys/111111111111111111   # 404 = vivo, TLS válido, base conectada
curl https://<IP-elástica>:8443/                                                       # debe FALLAR: el navegador no confía en nuestra CA
```
El segundo fallo es el esperado: en el login, el navegador mostrará advertencia de certificado; acéptala solo para esa IP (es tu propia CA).

## Cuidados en AWS Academy
- El lab se apaga a las ~4 h y hay que volver a **Start Lab**; con Elastic IP la dirección se conserva y el contenedor arranca solo.
- Si alguna vez la IP cambia, repite el paso 1 (nuevo `issue`), copia `server.pem`/`server.key`, y actualiza `DISCORD_REDIRECT_URI`, Discord y los `DIRECTORY_URL`.
- Renueva el certificado antes de 90 días (`issue` + copiar) y, si `server.key` se filtra, revócalo (`ops/certs/README.md`).
