"""Pruebas de operaciones contra el Postgres de docker-compose, en bases propias que se recrean."""
import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from directory.migrations.apply import apply


def env(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == name:
                return value.strip()
    return None


@pytest.fixture(scope="session")
def database():
    """Base `ops_test` con el esquema del directorio; devuelve las URLs de admin, app y backup."""
    admin, app_pw, backup_pw = env("DATABASE_ADMIN_URL"), env("DIRECTORY_APP_PASSWORD"), env("DIRECTORY_BACKUP_PASSWORD")
    if not (admin and app_pw and backup_pw):
        pytest.skip("faltan DATABASE_ADMIN_URL, DIRECTORY_APP_PASSWORD y DIRECTORY_BACKUP_PASSWORD (.env)")
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS ops_test WITH (FORCE)"))
            conn.execute(sql.SQL("CREATE DATABASE ops_test"))
    except psycopg.OperationalError:
        pytest.skip("no hay Postgres: docker compose up -d db")
    test_admin = make_conninfo(admin, dbname="ops_test")
    apply(test_admin, app_pw, backup_pw)
    return {"admin": test_admin, "app": make_conninfo(test_admin, user="directory_app", password=app_pw),
            "backup": make_conninfo(test_admin, user="directory_backup", password=backup_pw)}
