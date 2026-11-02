"""Arranque del directorio con TLS 1.3 y el certificado de la CA propia (F2): `python -m directory.serve`.

Usa `DIRECTORY_CERT_FILE` y `DIRECTORY_KEY_FILE` (por defecto, los que genera `python -m ops.certs.pki init`),
`DIRECTORY_HOST` (127.0.0.1) y `DIRECTORY_PORT` (8443). Sin registro de acceso: escribiría IPs e IDs en claro.
"""
import os
import ssl

import uvicorn

CERT_DIR = os.path.join(os.path.dirname(__file__), "..", "ops", "certs")


def build_config(app="directory.app.main:create_app_from_env", cert_file: str | None = None,
                 key_file: str | None = None, host: str | None = None, port: int | None = None) -> uvicorn.Config:
    config = uvicorn.Config(
        app, factory=isinstance(app, str), access_log=False,
        host=host or os.environ.get("DIRECTORY_HOST", "127.0.0.1"),
        port=port or int(os.environ.get("DIRECTORY_PORT", "8443")),
        ssl_certfile=cert_file or os.environ.get("DIRECTORY_CERT_FILE", os.path.join(CERT_DIR, "server.pem")),
        ssl_keyfile=key_file or os.environ.get("DIRECTORY_KEY_FILE", os.path.join(CERT_DIR, "private", "server.key")),
    )
    config.load()
    config.ssl.minimum_version = ssl.TLSVersion.TLSv1_3  # RS6: nada por debajo de TLS 1.3
    return config


def main() -> None:
    uvicorn.Server(build_config()).run()


if __name__ == "__main__":
    main()
