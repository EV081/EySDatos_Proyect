"""Revisión del canal antes de la demostración (C-23): `python -m discord_adapter.check`.

Conecta con el bot (`DISCORD_TOKEN`, `DISCORD_CHANNEL_ID`) y comprueba que el canal sea privado y que el bot no
tenga más permisos de los necesarios. Sale con código 1 si encuentra un problema."""
import json
import os
import sys

from . import DiscordAdapter


def problems(report: dict) -> list[str]:
    found = []
    if report["everyone_can_view"]:
        found.append("@everyone puede ver el canal: debe ser privado")
    if report["bot_is_admin"]:
        found.append("el bot es administrador: quítale ese permiso")
    if report["bot_extra_permissions"]:
        found.append("el bot tiene permisos de más: " + ", ".join(report["bot_extra_permissions"]))
    if len(report["roles_with_access"]) > 3:
        found.append("demasiados roles con acceso al canal: " + ", ".join(report["roles_with_access"]))
    return found


def main() -> None:
    adapter = DiscordAdapter(os.environ["DISCORD_TOKEN"], int(os.environ["DISCORD_CHANNEL_ID"]))
    if not adapter._ready.wait(30):
        raise SystemExit("no se pudo conectar con Discord")
    report = adapter._backend.channel_report()
    adapter.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    found = problems(report)
    for p in found:
        print("PROBLEMA:", p)
    print("OK: el canal es privado y el bot tiene permisos mínimos" if not found else "")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
