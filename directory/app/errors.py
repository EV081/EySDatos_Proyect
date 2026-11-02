"""Errores genéricos: la respuesta no dice qué falló (ID inexistente, firma mala, token vencido...), para no
ayudar a enumerar usuarios ni a afinar un ataque. El detalle queda, seudonimizado, en el registro de auditoría."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("directory")

MESSAGES = {400: "solicitud inválida", 401: "solicitud rechazada", 404: "no encontrado",
            429: "demasiadas solicitudes", 500: "error interno"}


class ApiError(Exception):
    def __init__(self, status: int):
        self.status = status


def _reply(status: int) -> JSONResponse:
    status = status if status in MESSAGES else 400
    return JSONResponse({"error": MESSAGES[status]}, status_code=status, headers={"Cache-Control": "no-store"})


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return _reply(exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError):
        return _reply(400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _reply(404 if exc.status_code in (404, 405) else exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        log.error("error inesperado: %s", type(exc).__name__)  # sin el mensaje: podría llevar datos
        return _reply(500)
