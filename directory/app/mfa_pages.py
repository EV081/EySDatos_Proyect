"""Páginas del segundo factor: sin scripts ni servicios QR externos."""
import html

from fastapi.responses import HTMLResponse

from .mfa import Authenticator

PAGE_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                               "frame-ancestors 'none'; base-uri 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def document(title: str, content: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        '<!doctype html><html lang="es"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)}</title><body style="font-family:sans-serif;max-width:40rem;'
        'margin:3rem auto;padding:0 1rem;line-height:1.6;overflow-wrap:anywhere">'
        f'<h1>{html.escape(title)}</h1>{content}</body></html>', status_code=status, headers=PAGE_HEADERS)


def verification(csrf: str, authenticator: Authenticator, discord_id: str = "",
                 ciphertext: str | None = None, error: bool = False) -> HTMLResponse:
    setup = ""
    if ciphertext:
        secret, svg = authenticator.provisioning(ciphertext, discord_id)
        setup = (
            '<p>En Microsoft Authenticator, pulsa <b>+</b>, elige <b>Otra cuenta '
            '(Google, Facebook, etc.)</b> y escanea este QR.</p>'
            f'<div aria-label="QR para vincular Microsoft Authenticator">{svg}</div>'
            '<details><summary>Introducir la clave manualmente</summary>'
            f'<code id="setup-secret">{html.escape(secret)}</code></details>'
            '<p>No compartas este QR ni su clave. La vinculación se activa al confirmar tu primer código.</p>')
    message = ('<p role="alert">No se pudo verificar el código. Si ya lo usaste, espera al siguiente. '
               'Si venció el intento o agotaste los intentos, espera cinco minutos y vuelve a iniciar '
               'sesión con Discord.</p>' if error else "")
    return document("Configurar Microsoft Authenticator" if ciphertext else "Verificación en dos pasos",
                    setup + message + '<form method="post" action="/auth/mfa/verify">'
                    f'<input type="hidden" name="csrf" value="{html.escape(csrf, quote=True)}">'
                    '<label for="code">Código de Microsoft Authenticator</label><br>'
                    '<input id="code" name="code" type="text" autocomplete="one-time-code" '
                    'maxlength="35" required autofocus spellcheck="false" autocapitalize="off"><br>'
                    '<button type="submit">Verificar y continuar</button></form>'
                    '<p>Ingresa los seis dígitos de la app. Si perdiste el dispositivo, usa un código de '
                    'recuperación para vincular un nuevo autenticador.</p>', 401 if error else 200)


def success(token: str, recovery_codes: list[str]) -> HTMLResponse:
    recovery = ""
    if recovery_codes:
        recovery = ('<h2>Guarda tus códigos de recuperación</h2>'
                    '<p>Solo se muestran una vez. Guárdalos fuera de este dispositivo. Cada código '
                    'permite reemplazar un autenticador perdido e invalida los códigos anteriores.</p>'
                    '<ul id="recovery-codes">'
                    + "".join(f'<li><code>{html.escape(c)}</code></li>' for c in recovery_codes) + '</ul>')
    return document("Token de registro", '<p>Verificación completada. Pega este token en tu cliente. '
                    'Vale diez minutos y una sola publicación. No lo compartas.</p>'
                    f'<pre style="user-select:all;word-break:break-all">{html.escape(token)}</pre>' + recovery)
