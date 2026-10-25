class ClientError(Exception):
    """Error que la API local traduce a un código HTTP sin revelar detalles internos."""

    status = 400
    code = "bad_request"

    def __init__(self, message: str = ""):
        super().__init__(message or self.code)


class Locked(ClientError):
    status, code = 423, "locked"


class BadPassword(ClientError):
    status, code = 401, "bad_password"


class TooManyAttempts(ClientError):
    status, code = 429, "too_many_attempts"


class NotFound(ClientError):
    status, code = 404, "not_found"


class Conflict(ClientError):
    status, code = 409, "conflict"


class KeyChanged(Conflict):
    """La llave del contacto verificado cambió: hay que repetir la verificación."""

    code = "key_changed"


class PeerUnavailable(ClientError):
    """No se pudo obtener la llave del contacto (directorio caído o contacto sin registrar)."""

    status, code = 502, "peer_key_unavailable"
