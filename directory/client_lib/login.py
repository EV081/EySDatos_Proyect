"""Obtiene un token de registro: `python -m directory.client_lib.login`.

Abre `/auth/login` del directorio en el navegador; tras iniciar sesión con Discord, la página muestra el token,
que se pega aquí y se guarda en `DIRECTORY_AUTH_TOKEN_FILE` (vale 10 minutos y una sola publicación).
"""
import getpass
import os
import webbrowser
from pathlib import Path

from . import DirectoryError, _b64d

TOKEN_LEN = 32


def clean_token(text: str) -> str:
    """Valida el token pegado. Como getpass no muestra nada, es fácil pegarlo dos o tres veces: se detecta."""
    token = text.strip()
    try:
        _b64d(token, TOKEN_LEN)
    except DirectoryError:
        raise SystemExit("eso no parece un token de registro (43 caracteres); vuelve a copiarlo y pégalo una sola vez")
    return token


def main() -> None:
    url = os.environ.get("DIRECTORY_URL", "https://localhost:8443").rstrip("/") + "/auth/login"
    target = Path(os.environ.get("DIRECTORY_AUTH_TOKEN_FILE", "./data/directory-token"))
    print(f"Abriendo {url} ...")
    webbrowser.open(url)
    token = getpass.getpass("Pega el token de registro una sola vez (no se muestra) y presiona Enter: ").strip()
    if not token:
        raise SystemExit("no se ingresó ningún token")
    token = clean_token(token)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(token, encoding="ascii")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print(f"Token guardado en {target}. Ahora crea o importa tu identidad en la aplicación.")


if __name__ == "__main__":
    main()
