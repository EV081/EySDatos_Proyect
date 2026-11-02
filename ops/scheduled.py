"""Tarea diaria del directorio: `python -m ops.scheduled daily [--env .env]`.

1. Copia de seguridad cifrada + rotación de 30 días (F4).
2. Purga de la base: llaves reemplazadas de más de 90 días y estado efímero vencido (C-10).
3. Retención de registros: borra los de más de 90 días (F5).

Cada paso es independiente: si uno falla, los demás siguen y la tarea termina con código 1. El resumen queda en
el registro de auditoría."""
import logging
import os
import sys
from pathlib import Path

from directory.app.audit import audit_log, purge_logs, setup_logging


def load_env(path: str | Path) -> None:
    """Carga `CLAVE=valor` sin pisar lo que ya está en el entorno (el Programador de tareas no lee .env)."""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip())


def daily() -> int:
    from directory.app.repo import Repo
    from ops.backup import backup

    failures = 0
    summary: dict[str, object] = {"event": "mantenimiento"}
    try:
        path = backup.create(os.environ["BACKUP_DATABASE_URL"], backup.load_key(), Path(os.environ["BACKUP_DIR"]))
        summary["copia"] = path.name
        summary["copias_rotadas"] = len(backup.rotate(Path(os.environ["BACKUP_DIR"])))
    except Exception as exc:
        failures += 1
        summary["copia_error"] = type(exc).__name__
    try:
        repo = Repo(os.environ["DATABASE_URL"], min_size=1, max_size=1)
        try:
            summary.update({f"purga_{k}": v for k, v in repo.purge().items()})
        finally:
            repo.close()
    except Exception as exc:
        failures += 1
        summary["purga_error"] = type(exc).__name__
    try:
        summary["registros_borrados"] = len(purge_logs(os.environ.get("AUDIT_LOG_DIR", "logs")))
    except Exception as exc:
        failures += 1
        summary["registros_error"] = type(exc).__name__
    audit_log.log(logging.ERROR if failures else logging.INFO, "mantenimiento", extra={"fields": summary})
    return 1 if failures else 0


def main(argv: list[str]) -> None:
    if "--env" in argv:
        load_env(argv[argv.index("--env") + 1])
    if not argv or argv[0] != "daily":
        raise SystemExit(__doc__)
    setup_logging(os.environ.get("AUDIT_LOG_DIR", "logs"))
    sys.exit(daily())


if __name__ == "__main__":
    main(sys.argv[1:])
