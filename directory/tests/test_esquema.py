"""Revisión automática del esquema (C-05) y de los permisos del rol de la aplicación (C-08)."""
import psycopg
import pytest


def test_C05_columnas_del_esquema(admin_db):
    rows = admin_db.execute("SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = 'directory' AND table_name = 'keys'").fetchall()
    assert {r[0] for r in rows} == {"discord_id", "public_key", "registered_at", "key_changed_at",
                                    "consent_version", "consent_at"}


def test_C05_ninguna_tabla_guarda_ip_ni_datos_de_perfil(admin_db):
    rows = admin_db.execute("SELECT table_name, column_name FROM information_schema.columns "
                            "WHERE table_schema = 'directory'").fetchall()
    forbidden = ("ip", "addr", "user_agent", "username", "email", "avatar", "name")
    assert not [r for r in rows if any(f in r[1] for f in forbidden)]


@pytest.fixture
def app_db(urls):
    with psycopg.connect(urls["app"], autocommit=True) as conn:
        yield conn


@pytest.mark.parametrize("statement", [
    "CREATE TABLE directory.otra (x int)",
    "CREATE TABLE public.otra (x int)",
    "CREATE TEMP TABLE otra (x int)",
    "DROP TABLE directory.keys",
    "ALTER TABLE directory.keys ADD COLUMN ip text",
    "TRUNCATE directory.keys",
    "CREATE ROLE intruso",
])
def test_C08_rol_app_sin_ddl(app_db, statement):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_db.execute(statement)


def test_C08_rol_app_no_es_superusuario(app_db):
    row = app_db.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles "
                         "WHERE rolname = current_user").fetchone()
    assert row == (False, False, False, False)
