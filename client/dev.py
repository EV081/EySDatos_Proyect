"""Entorno de desarrollo sin Discord ni directorio reales: dos clientes (Alice y Bob) que comparten un
directorio y un canal en memoria. Sirve para desarrollar el frontend y para ensayar la demo.

    python -m client.dev          # Alice en :8001, Bob en :8002, token "dev-token"
"""
import tempfile
import threading
import time

import uvicorn

from crypto import KdfParams

from .api import create_app
from .fakes import FakeChannel, FakeDirectory, FakeDiscord
from .orchestrator import Orchestrator

TOKEN = "dev-token"


def main() -> None:
    directory, channel = FakeDirectory(), FakeChannel()
    servers = []
    for port in (8001, 8002):
        orch = Orchestrator(tempfile.mkdtemp(prefix=f"e2ee-dev-{port}-"), directory, FakeDiscord(channel),
                            kdf=KdfParams(1, 1024, 1))
        app = create_app(orch, TOKEN, ["http://127.0.0.1:5173", "http://localhost:5173"])
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=server.run, daemon=True).start()
        servers.append(server)

    print("Alice -> http://127.0.0.1:8001   Bob -> http://127.0.0.1:8002   Authorization: Bearer", TOKEN)
    while True:
        channel.flush()
        time.sleep(0.2)


if __name__ == "__main__":
    main()
