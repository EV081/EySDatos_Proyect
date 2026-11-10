"""Crea los roles y aplica las migraciones: `python -m directory.migrations.apply`.

Se conecta con `DATABASE_ADMIN_URL` (superusuario, solo para esto) y crea:
* `directory_owner` (NOLOGIN): dueño del esquema `directory`; las migraciones corren con `SET ROLE`.
* `directory_app` (LOGIN, contraseña `DIRECTORY_APP_PASSWORD`): solo lee y escribe filas (C-08).
* `directory_backup` (LOGIN solo si hay `DIRECTORY_BACKUP_PASSWORD`): solo lee, para `pg_dump` (F4).
"""
import os
from pathlib import Path

import psycopg
from psycopg import sql

MIGRATIONS = sorted(Path(__file__).parent.glob("[0-9][0-9][0-9]_*.sql"))


def _role_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
    return cur.fetchone() is not None


def apply(admin_url: str, app_password: str, backup_password: str | None = None) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn, conn.cursor() as cur:
        if not _role_exists(cur, "directory_owner"):
            cur.execute("CREATE ROLE directory_owner NOLOGIN")
        if not _role_exists(cur, "directory_app"):
            cur.execute("CREATE ROLE directory_app LOGIN")
        cur.execute(sql.SQL("ALTER ROLE directory_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                            "NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Literal(app_password)))
        if not _role_exists(cur, "directory_backup"):
            cur.execute("CREATE ROLE directory_backup NOLOGIN")
        if backup_password:
            cur.execute(sql.SQL("ALTER ROLE directory_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT "
                                "NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Literal(backup_password)))
        dbname = conn.info.dbname
        cur.execute(sql.SQL("REVOKE CREATE, TEMPORARY ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
        cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO directory_app, directory_backup")
                    .format(sql.Identifier(dbname)))
        cur.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        # En bases administradas (Supabase) el usuario admin no es superusuario y no puede asumir el rol sin esto.
        cur.execute(sql.SQL("GRANT directory_owner TO {}").format(sql.Identifier(conn.info.user)))
        # Evita depender del parámetro de conexión `search_path`, que algunos poolers rechazan.
        cur.execute("ALTER ROLE directory_app SET search_path = directory")
        cur.execute("CREATE SCHEMA IF NOT EXISTS directory AUTHORIZATION directory_owner")
        cur.execute("REVOKE ALL ON SCHEMA directory FROM PUBLIC")
    with psycopg.connect(admin_url) as conn, conn.cursor() as cur:
        cur.execute("SET ROLE directory_owner")
        cur.execute("SET search_path = directory")
        for path in MIGRATIONS:
            cur.execute(path.read_text(encoding="utf-8"))


def main() -> None:
    apply(os.environ["DATABASE_ADMIN_URL"], os.environ["DIRECTORY_APP_PASSWORD"],
          os.environ.get("DIRECTORY_BACKUP_PASSWORD"))
    print(f"migraciones aplicadas: {', '.join(p.name for p in MIGRATIONS)}")


if __name__ == "__main__":
    main()
