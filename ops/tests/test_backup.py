"""F4 / C-12: copias cifradas, fuera del repositorio, con restauración probada y rotación de 30 días."""
import datetime as dt
import os

import psycopg
import pytest

from ops.backup import backup
from ops.backup.backup import BackupError

ALICE, BOB = "111111111111111111", "222222222222222222"


@pytest.fixture
def key():
    return os.urandom(32)


@pytest.fixture
def dest(tmp_path_factory):
    return tmp_path_factory.mktemp("copias")  # fuera del repositorio


@pytest.fixture
def seeded(database):
    with psycopg.connect(database["admin"], autocommit=True) as conn:
        conn.execute("TRUNCATE directory.keys, directory.replaced_keys, directory.auth_tokens CASCADE")
        for uid in (ALICE, BOB):
            conn.execute("INSERT INTO directory.keys (discord_id, public_key, consent_version) VALUES (%s, %s, '1.0')",
                         (uid, os.urandom(32)))
        conn.execute("INSERT INTO directory.replaced_keys (discord_id, public_key) VALUES (%s, %s)",
                     (ALICE, os.urandom(32)))
        conn.execute("INSERT INTO directory.auth_tokens (token_hash, discord_id, expires_at) "
                     "VALUES (%s, %s, now() + interval '1 hour')", (os.urandom(32), ALICE))
    return database


def test_C12_copia_cifrada_sin_datos_en_claro(seeded, key, dest):
    path = backup.create(seeded["backup"], key, dest)
    blob = path.read_bytes()
    assert blob.startswith(backup.MAGIC)
    assert ALICE.encode() not in blob and b"PGDMP" not in blob
    assert list(dest.iterdir()) == [path]  # ni archivos temporales ni volcados en claro


def test_C12_restauracion_probada(seeded, key, dest):
    path = backup.create(seeded["backup"], key, dest)
    assert backup.verify(path, key, seeded["admin"], scratch="ops_restore_check") == {"keys": 2, "replaced_keys": 1}


def test_C12_restaurar_recupera_el_servicio_tras_perder_datos(seeded, key, dest):
    path = backup.create(seeded["backup"], key, dest)
    with psycopg.connect(seeded["admin"], autocommit=True) as conn:
        conn.execute("DELETE FROM directory.keys")
    backup.restore(path, key, seeded["admin"])
    with psycopg.connect(seeded["app"]) as conn:  # la app vuelve a leer con sus permisos mínimos
        assert conn.execute("SELECT count(*) FROM directory.keys").fetchone()[0] == 2
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("CREATE TABLE directory.otra (x int)")


def test_no_se_copian_datos_efimeros(seeded, key, dest):
    path = backup.create(seeded["backup"], key, dest)
    backup.restore(path, key, seeded["admin"])
    with psycopg.connect(seeded["admin"]) as conn:
        assert conn.execute("SELECT count(*) FROM directory.auth_tokens").fetchone()[0] == 0


def test_copia_alterada_o_clave_incorrecta_se_rechaza(seeded, key, dest):
    path = backup.create(seeded["backup"], key, dest)
    with pytest.raises(BackupError):
        backup.decrypt(os.urandom(32), path.read_bytes(), path.name)
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 1
    with pytest.raises(BackupError):
        backup.decrypt(key, bytes(blob), path.name)


def test_renombrar_una_copia_vieja_se_detecta(seeded, key, dest):
    path = backup.create(seeded["backup"], key, dest)
    with pytest.raises(BackupError):
        backup.decrypt(key, path.read_bytes(), "directory-20990101T000000Z.dump.enc")


def test_C10_rotacion_de_30_dias(key, dest):
    now = dt.datetime(2026, 10, 31, tzinfo=dt.timezone.utc)
    names = {d: f"directory-{now - dt.timedelta(days=d):%Y%m%dT%H%M%SZ}.dump.enc" for d in (0, 29, 31, 90)}
    for name in names.values():
        (dest / name).write_bytes(b"x")
    (dest / "otra-cosa.txt").write_text("no se toca")
    removed = {p.name for p in backup.rotate(dest, now)}
    assert removed == {names[31], names[90]}
    assert {p.name for p in dest.iterdir()} == {names[0], names[29], "otra-cosa.txt"}


def test_destino_dentro_del_repositorio_se_rechaza(seeded, key):
    with pytest.raises(BackupError):
        backup.create(seeded["backup"], key, backup.REPO_ROOT / "backups")


def test_rol_de_copias_es_de_solo_lectura(seeded):
    with psycopg.connect(seeded["backup"], autocommit=True) as conn:
        for statement in ("DELETE FROM directory.keys", "CREATE TABLE directory.otra (x int)"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)


def test_clave_invalida():
    with pytest.raises(BackupError):
        backup.load_key("corta")
