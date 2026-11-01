"""Ensayo contra la API real de Discord: `python -m discord_adapter.smoke` (con `DISCORD_TOKEN` y `DISCORD_CHANNEL_ID`).

Basta con un bot: un segundo cliente con el mismo token hace de "otra persona" que publica en el canal. Deja en
`#e2ee-relay` dos mensajes `E2EE1:prueba-f3-...` y uno de texto normal (el cliente real los descarta).
Sale con código 1 si alguna comprobación falla."""
import asyncio
import os
import secrets
import sys
import time

import discord

from . import DiscordAdapter


def _wait(pred, timeout=20.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.2)
    return False


def _post_raw(token: str, channel_id: int, text: str) -> None:
    """Publica sin pasar por el adaptador, como lo haría una persona u otro bot."""
    async def _run():
        client = discord.Client(intents=discord.Intents(guilds=True))

        @client.event
        async def on_ready():
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
            await client.close()
        await client.start(token)
    asyncio.run(_run())


def _adapter(token: str, channel_id: int) -> tuple[DiscordAdapter, list[str]]:
    got: list[str] = []
    adapter = DiscordAdapter(token, channel_id, start=False)
    adapter.set_receiver(got.append)
    adapter.start()
    if not adapter._ready.wait(30):
        raise SystemExit("no se pudo conectar con Discord")
    return adapter, got


def main() -> None:
    token, channel_id = os.environ["DISCORD_TOKEN"], int(os.environ["DISCORD_CHANNEL_ID"])
    run = secrets.token_hex(4)
    m1, m2 = f"E2EE1:prueba-f3-{run}-1", f"E2EE1:prueba-f3-{run}-2"
    plain = f"mensaje normal escrito en el canal ({run})"
    results: list[tuple[bool, str]] = []

    def check(ok: bool, text: str) -> None:
        results.append((bool(ok), text))
        print(("[OK]    " if ok else "[FALLA] ") + text, flush=True)

    a, got = _adapter(token, channel_id)
    mine = lambda received: [t for t in received if run in t]  # noqa: E731

    a.send(m1)
    check(_wait(lambda: m1 in got), "publica un mensaje E2EE1 y lo recibe por el gateway")

    for text, why in [("hola, texto plano", "texto plano"), ("E2EE1:" + "x" * 2000, "más de 2000 caracteres")]:
        try:
            a.send(text)
            check(False, f"se niega a publicar {why}")
        except ValueError:
            check(True, f"se niega a publicar {why}")

    _post_raw(token, channel_id, plain)
    time.sleep(3)
    check(plain not in got, "ignora un mensaje normal publicado en el canal")

    backend = a._backend  # cortar el websocket: discord.py reconecta solo
    asyncio.run_coroutine_threadsafe(backend._client.ws.close(code=4000), backend._loop).result(10)
    _wait(lambda: not a._ready.is_set(), 10)
    _post_raw(token, channel_id, m2)
    check(_wait(lambda: m2 in got, 60), "reconecta y entrega lo publicado mientras estaba desconectado")
    time.sleep(3)
    check(mine(got) == [m1, m2], f"sin repetidos ({len(mine(got))} mensajes de esta corrida)")
    a.close()

    b, got_b = _adapter(token, channel_id)
    check(_wait(lambda: m1 in got_b and m2 in got_b), "un adaptador nuevo recibe lo atrasado (7 días)")
    check(plain not in got_b, "lo atrasado no incluye el mensaje normal")
    count = len(mine(got_b))
    b.replay_backlog()
    check(_wait(lambda: len(mine(got_b)) == 2 * count, 15), "replay_backlog() vuelve a entregar lo atrasado")
    b.close()

    failed = sum(not ok for ok, _ in results)
    print(f"\n{len(results) - failed}/{len(results)} comprobaciones OK")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
