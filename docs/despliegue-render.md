# Desplegar el directorio en Render (para chatear desde redes distintas)

Solo el **directorio** va a Render, y su base de datos va en **Supabase**. `client/` y el frontend siguen en la laptop de cada quien (ahí están las llaves privadas y el texto plano); los mensajes viajan cifrados por Discord, así que no depende de que estén en la misma red.

```
laptop A: frontend ─► client ─► Discord (#e2ee-relay) ◄─ client ◄─ frontend :laptop B
                        └──────► directorio en Render (https://<servicio>.onrender.com) ◄──────┘
```

Render pone el TLS (certificado público); el contenedor recibe HTTP en `$PORT` (`DIRECTORY_BEHIND_PROXY=1`). El cliente confía en las CA del sistema solo si pones `DIRECTORY_PUBLIC_CA=1`, siempre con TLS 1.3 y nombre verificado.

## 1. Crear servicios (una sola persona)
1. Subir el repo a GitHub (ya está) → Render → **New > Blueprint** → elegir el repo. Crea `e2ee-directory` (web, Docker). La base no va en Render.
2. Anotar la URL pública: `https://e2ee-directory-XXXX.onrender.com`.

## 2. Base de datos (Supabase)
1. Crear un proyecto en Supabase y guardar la contraseña de la base.
2. **Connect > Session pooler** (no la conexión directa: es solo IPv6 y Render gratis sale por IPv4). La URL se ve así:
   `postgresql://postgres.<ref>:<contraseña>@aws-0-<región>.pooler.supabase.com:5432/postgres`
3. Desde tu laptop:
```bash
export DATABASE_ADMIN_URL='<esa URL>'
export DIRECTORY_APP_PASSWORD=<contraseña nueva y larga>
python -m directory.migrations.apply
```
4. La `DATABASE_URL` del servicio es la misma URL pero con usuario **`directory_app.<ref>`** y la contraseña `DIRECTORY_APP_PASSWORD`.

## 3. Variables del servicio (Render > Environment)
`DATABASE_URL` (la de `directory_app`), `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `PSEUDONYM_KEY`, y
`DISCORD_REDIRECT_URI=https://<servicio>.onrender.com/auth/callback`.
En el Developer Portal de Discord (OAuth2 > Redirects) agrega esa misma redirección.

## 4. En cada laptop (tú y tu amigo)
```
DIRECTORY_URL=https://<servicio>.onrender.com
DIRECTORY_PUBLIC_CA=1
DISCORD_TOKEN=<token de SU bot>
DISCORD_CHANNEL_ID=<canal #e2ee-relay, con ambos bots invitados>
```
(sin `DIRECTORY_CA_FILE`/`DIRECTORY_CRL_FILE`). Luego `python -m directory.client_lib.login`, `make client`, `make frontend`.

## 5. Comprobación
```bash
curl https://<servicio>.onrender.com/v1/keys/111111111111111111   # 404 = vivo
```

## Limitaciones del plan gratuito
- **Se duerme a los 15 min** sin tráfico; la primera petición tarda ~1 min. Abre la URL antes de empezar a chatear.
- El plan gratuito de Supabase pausa el proyecto tras una semana sin actividad (se reactiva desde su panel).
- Los registros de auditoría van a disco efímero (`/tmp`) y se pierden en cada reinicio; para la entrega, copia lo necesario desde Render > Logs.
- Las migraciones ya se otorgan `directory_owner` y fijan el `search_path` en el rol, pensando en Supabase; no se han probado contra él. Si fallan, revisa el error.
