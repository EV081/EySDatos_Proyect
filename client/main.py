"""Arranque real: `uvicorn client.main:app --host 127.0.0.1`. Toda la configuración sale del entorno."""
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

    directory = DirectoryClient(os.environ["DIRECTORY_URL"], ca_file=os.environ["DIRECTORY_CA_FILE"])
    discord = DiscordAdapter(token=os.environ["DISCORD_TOKEN"], channel_id=int(os.environ["DISCORD_CHANNEL_ID"]))
    orchestrator = Orchestrator(os.environ.get("CLIENT_DATA_DIR", "./data"), directory, discord)
    token = os.environ.get("CLIENT_API_TOKEN") or secrets.token_urlsafe(32)
    if "CLIENT_API_TOKEN" not in os.environ:
        print(f"CLIENT_API_TOKEN (generado para esta ejecución): {token}")
    origin = os.environ.get("CLIENT_ALLOWED_ORIGIN", "http://127.0.0.1:5173")
    return create_app(orchestrator, token, [origin]), discord


app, _discord = _build()
