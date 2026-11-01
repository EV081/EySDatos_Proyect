"""Backend real con discord.py. Permisos mínimos del bot: ver el canal, enviar mensajes y leer el historial.

Requiere activar el *Message Content Intent* del bot en el Developer Portal: sin él, Discord entrega el contenido
vacío de los mensajes de los demás bots y no se podría leer el protocolo."""
import asyncio
import datetime as dt
import threading

import discord


def make_intents() -> discord.Intents:
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True
    return intents


class DiscordPyBackend:
    def __init__(self, token: str, channel_id: int):
        self._token, self._channel_id = token, channel_id
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: discord.Client | None = None
        self._first = True
        self._started = threading.Event()

    def run(self, adapter) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        client = discord.Client(intents=make_intents())
        self._client = client

        @client.event
        async def on_ready():
            adapter.on_connect(self._first)
            self._first = False

        @client.event
        async def on_resumed():
            adapter.on_connect(False)

        @client.event
        async def on_disconnect():
            adapter.on_disconnect()

        @client.event
        async def on_message(message: discord.Message):
            adapter.on_message(message.channel.id, message.id, message.content)

        self._started.set()
        try:
            self._loop.run_until_complete(client.start(self._token, reconnect=True))
        finally:
            self._loop.run_until_complete(client.close())
            self._loop.close()

    async def _channel(self) -> discord.abc.Messageable:
        channel = self._client.get_channel(self._channel_id)
        return channel or await self._client.fetch_channel(self._channel_id)

    def _call(self, coro, timeout: float):
        if self._loop is None or not self._started.is_set():
            coro.close()
            raise ConnectionError("Discord no está conectado")
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def send(self, text: str, timeout: float) -> None:
        async def _send():
            channel = await self._channel()
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        self._call(_send(), timeout)

    def history(self, after, limit: int) -> list[tuple[int, int, str]]:
        marker = discord.Object(id=after) if isinstance(after, int) else after

        async def _history():
            channel = await self._channel()
            return [(m.channel.id, m.id, m.content)
                    async for m in channel.history(after=marker, oldest_first=True, limit=limit)]
        return self._call(_history(), 60)

    def channel_report(self) -> dict:
        """Datos para revisar que el canal sea privado (C-23); ver `python -m discord_adapter.check`."""
        async def _report():
            channel = await self._channel()
            guild = channel.guild
            everyone = channel.permissions_for(guild.default_role)
            me = channel.permissions_for(guild.me)
            # Sin el intent privilegiado de miembros no se ve la lista de personas; se revisan los roles.
            roles = [r.name for r in guild.roles if not r.is_default() and channel.permissions_for(r).view_channel]
            return {
                "guild": guild.name, "channel": channel.name,
                "everyone_can_view": everyone.view_channel,
                "roles_with_access": roles,
                "bot_is_admin": me.administrator,
                "bot_extra_permissions": sorted(p for p, on in me if on and p not in {
                    "view_channel", "send_messages", "read_message_history", "read_messages"}),
            }
        return self._call(_report(), 30)

    def close(self) -> None:
        if self._loop is not None and self._client is not None and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._client.close(), self._loop)
