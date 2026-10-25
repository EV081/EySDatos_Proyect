class CryptoError(Exception):
    """Base de todos los errores de la librería."""


class VaultError(CryptoError):
    """Bóveda corrupta, con parámetros inválidos o contraseña incorrecta."""


class WireError(CryptoError):
    """Mensaje mal formado: no cumple el formato del protocolo."""


class SignatureError(CryptoError):
    """Firma inválida."""


class HandshakeError(CryptoError):
    """El handshake debe abortarse (firma, confirmación de clave, ids, caducidad)."""


class ReplayError(CryptoError):
    """Mensaje o handshake repetido, o fuera de la ventana de recepción."""


class DecryptError(CryptoError):
    """No se pudo autenticar o descifrar el mensaje (RF11, RS5)."""


class SessionExpired(CryptoError):
    """La sesión superó su límite duro y debe renovarse con un nuevo handshake."""
