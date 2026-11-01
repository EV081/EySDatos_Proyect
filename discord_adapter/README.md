# `discord_adapter/` — Discord como transporte (F3)

Implementa `client.ports.DiscordPort` (`send`, `set_receiver`) con un **bot por persona** que publica y lee mensajes `E2EE1:` en un canal privado. El autor que muestra Discord se ignora: siempre es un bot y el protocolo autentica al emisor real.

## Preparar Discord (una vez, antes de la demo)

1. **Servidor privado** del proyecto, solo con los participantes (C-23).
2. **Canal `#e2ee-relay`**: en *Permisos*, quitar *Ver canal* a `@everyone` y dárselo solo a un rol `e2ee` (personas y bots).
3. **Un bot por persona** (Developer Portal → *New Application* → *Bot*):
   * Activar **Message Content Intent**. Sin él, Discord entrega vacío el contenido de los mensajes de los otros bots.
   * Desactivar *Public Bot*.
   * Invitarlo (OAuth2 → URL Generator → `bot`) solo con **Ver canales, Enviar mensajes y Leer el historial**. Nunca *Administrador*.
4. **Variables de entorno** (nunca en el código ni en git, RS10): `DISCORD_TOKEN` (el token de *tu* bot) y `DISCORD_CHANNEL_ID` (clic derecho en el canal → *Copiar ID*, con el modo desarrollador activo).
5. **Revisión:** `python -m discord_adapter.check` muestra quién puede ver el canal y qué permisos tiene el bot, y sale con error si el canal es público o el bot tiene permisos de más. Guardar su salida como evidencia de C-23.

## Comportamiento

| Situación | Qué hace |
|---|---|
| `send(texto)` que no empieza con `E2EE1:` o pasa de 2000 caracteres | `ValueError`: el adaptador **nunca** publica texto plano |
| Discord caído o rechaza el mensaje | `ConnectionError` (el cliente reintenta con su cola de salida) |
| Mensaje de otro canal o que no es del protocolo | Se ignora |
| Primera conexión | Entrega lo publicado en los últimos 7 días (el cliente descarta repetidos y *handshakes* vencidos) |
| Reconexión | Entrega lo publicado desde el último mensaje visto, sin repetir |
| `replay_backlog()` | Vuelve a entregar los últimos 7 días. **Para el cliente:** llamarlo al desbloquear la identidad, porque con la identidad bloqueada se descarta lo que llega |

Los mensajes se entregan al cliente desde un hilo propio, no desde el bucle de discord.py: el cliente responde con `send()` mientras procesa un mensaje, y entregar desde el bucle lo bloquearía.

Pruebas: `cd discord_adapter && ../.venv/Scripts/python -m pytest -q`. Usan un Discord simulado con el mismo contrato que el backend real, e incluyen una conversación completa entre dos clientes reales.
