"""Arranque real: `make client` (o `uvicorn client.main:app --host 127.0.0.1`). Toda la configuración sale del entorno.

`DIRECTORY_CRL_FILE` y `DIRECTORY_AUTH_TOKEN_FILE` los lee directamente `directory.client_lib`."""
import atexit
import os
import secrets

from .api import create_app
from .orchestrator import Orchestrator


def _build():
    try:
        from directory.client_lib import DirectoryClient  # lo entrega Farid (F1)
        from discord_adapter import DiscordAdapter  # lo entrega Farid (F3)
    except ImportError as exc:
        raise SystemExit(f"Faltan los componentes de Farid ({exc.name}). Para desarrollar sin ellos: python -m client.dev")

    # DIRECTORY_PUBLIC_CA=1: el directorio está en Render (certificado público); si no, solo vale la CA del proyecto.
    public_ca = os.environ.get("DIRECTORY_PUBLIC_CA") == "1"
    directory = DirectoryClient(os.environ["DIRECTORY_URL"], public_ca=public_ca,
                                ca_file=os.environ.get("DIRECTORY_CA_FILE") or None if not public_ca else None)
    discord = DiscordAdapter(token=os.environ["DISCORD_TOKEN"], channel_id=int(os.environ["DISCORD_CHANNEL_ID"]))
    orchestrator = Orchestrator(os.environ.get("CLIENT_DATA_DIR", "./data"), directory, discord)
    token = os.environ.get("CLIENT_API_TOKEN") or secrets.token_urlsafe(32)
    if "CLIENT_API_TOKEN" not in os.environ:
        print(f"CLIENT_API_TOKEN (generado para esta ejecución): {token}")
    origin = os.environ.get("CLIENT_ALLOWED_ORIGIN", "http://127.0.0.1:5173")
    app = create_app(orchestrator, token, [origin])
    atexit.register(discord.close)  # cierra la conexión con Discord al apagar
    if hasattr(directory, "close"):
        atexit.register(directory.close)
    return app, discord


app, _discord = _build()
