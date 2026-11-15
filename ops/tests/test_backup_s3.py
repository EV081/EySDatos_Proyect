"""C-12: subida cifrada, verificación y retención S3 sin tocar AWS ni una base real."""
import base64
import datetime as dt
import hashlib
import json
from types import SimpleNamespace

import pytest

from ops.backup import backup

NOW = dt.datetime(2026, 11, 14, tzinfo=dt.timezone.utc)
BUCKET = "eysd-backups-test"


@pytest.fixture
def archive(tmp_path):
    path = tmp_path / "directory-20261114T000000Z.dump.enc"
    path.write_bytes(backup.encrypt(bytes(range(32)), b"contenido ficticio", path.name))
    return path


@pytest.fixture
def s3(monkeypatch, archive):
    state = SimpleNamespace(calls=[], deleted=[], public=False, version=None,
                            wrong_hash=False, wrong_size=False, failure=None)
    monkeypatch.setattr(backup.shutil, "which", lambda name: "/usr/bin/aws")

    def run(command, **kwargs):
        assert kwargs["capture_output"] and not kwargs.get("shell")
        action = command[2]
        state.calls.append(command)
        if action == state.failure:
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"detalle privado de credenciales")
        if action == "get-public-access-block":
            data = {"PublicAccessBlockConfiguration": {
                key: not state.public for key in (
                    "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")}}
        elif action == "get-bucket-versioning":
            data = {"Status": state.version} if state.version else {}
        elif action == "put-object":
            body = command[command.index("--body") + 1]
            assert body == str(archive)
            assert archive.read_bytes().startswith(backup.MAGIC)
            assert command[command.index("--server-side-encryption") + 1] == "AES256"
            assert command[command.index("--if-none-match") + 1] == "*"
            data = {}
        elif action == "head-object":
            digest = base64.b64encode(hashlib.sha256(archive.read_bytes()).digest()).decode()
            data = {"ContentLength": archive.stat().st_size + int(state.wrong_size),
                    "ChecksumSHA256": "incorrecto" if state.wrong_hash else digest}
        elif action == "list-objects-v2":
            data = {"Contents": [{"Key": key} for key in (
                "directory/directory-20261001T000000Z.dump.enc",
                "directory/directory-20261101T000000Z.dump.enc",
                "directory/" + archive.name,
                "directory/notas.txt",
                "directory/subcarpeta/directory-20261001T000000Z.dump.enc",
                "otro/directory-20261001T000000Z.dump.enc",
                "directory/directory-20260231T000000Z.dump.enc",
            )]}
        elif action == "delete-object":
            state.deleted.append(command[command.index("--key") + 1])
            data = {}
        else:
            raise AssertionError(action)
        return SimpleNamespace(returncode=0, stdout=json.dumps(data).encode(), stderr=b"")

    monkeypatch.setattr(backup.subprocess, "run", run)
    return state


def test_C12_subida_cifrada_y_retencion_limitada_a_las_copias_propias(archive, s3):
    uri, removed = backup.sync_s3(archive, BUCKET, now=NOW)
    assert uri == f"s3://{BUCKET}/directory/{archive.name}"
    assert removed == 1
    assert s3.deleted == ["directory/directory-20261001T000000Z.dump.enc"]
    actions = [c[2] for c in s3.calls]
    assert actions.index("head-object") < actions.index("list-objects-v2") < actions.index("delete-object")
    assert archive.exists()


def test_C12_no_subir_si_el_bucket_no_bloquea_acceso_publico(archive, s3):
    s3.public = True
    with pytest.raises(backup.BackupError, match="acceso público"):
        backup.sync_s3(archive, BUCKET, now=NOW)
    assert [c[2] for c in s3.calls] == ["get-public-access-block"]


@pytest.mark.parametrize("version", ["Enabled", "Suspended"])
def test_C10_rechazar_versionado_para_no_conservar_versiones_ocultas(archive, s3, version):
    s3.version = version
    with pytest.raises(backup.BackupError, match="sin versionado"):
        backup.sync_s3(archive, BUCKET, now=NOW)
    assert not any(c[2] == "put-object" for c in s3.calls)


@pytest.mark.parametrize("field", ["wrong_hash", "wrong_size"])
def test_C12_no_borrar_ninguna_copia_si_no_coincide_la_subida(archive, s3, field):
    setattr(s3, field, True)
    with pytest.raises(backup.BackupError, match="no coincide"):
        backup.sync_s3(archive, BUCKET, now=NOW)
    assert not s3.deleted
    assert not any(c[2] == "list-objects-v2" for c in s3.calls)


def test_C12_fallo_de_aws_no_expone_su_salida_privada_ni_borra_copias(archive, s3):
    s3.failure = "put-object"
    with pytest.raises(backup.BackupError, match="put-object") as caught:
        backup.sync_s3(archive, BUCKET, now=NOW)
    assert "credenciales" not in str(caught.value)
    assert archive.exists() and not s3.deleted


def test_C12_no_subir_un_volcado_en_texto_plano(archive, s3):
    archive.write_bytes(b"PGDMP sin cifrar")
    with pytest.raises(backup.BackupError, match="no está cifrada"):
        backup.sync_s3(archive, BUCKET, now=NOW)
    assert not s3.calls


@pytest.mark.parametrize("prefix", ["../otro", "directory/../otro", "", "a.b"])
def test_C10_no_permitir_prefijos_ambiguos(archive, s3, prefix):
    with pytest.raises(backup.BackupError, match="PREFIX"):
        backup.sync_s3(archive, BUCKET, prefix, now=NOW)
    assert not s3.calls


def test_C12_un_respaldo_remoto_no_continua_si_falta_el_bucket(monkeypatch):
    monkeypatch.setenv("BACKUP_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode())
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)
    monkeypatch.setattr(backup, "create", lambda *a: pytest.fail("no debe iniciar pg_dump"))
    with pytest.raises(SystemExit, match="BACKUP_S3_BUCKET"):
        backup.main(["create-remote"])


def test_C12_no_rotar_las_copias_locales_si_la_remota_falla(monkeypatch, archive, s3):
    s3.wrong_hash = True
    monkeypatch.setenv("BACKUP_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode())
    monkeypatch.setenv("BACKUP_S3_BUCKET", BUCKET)
    monkeypatch.setenv("BACKUP_DATABASE_URL", "postgresql://no-se-usa")
    monkeypatch.setattr(backup, "create", lambda *a: archive)
    monkeypatch.setattr(backup, "rotate", lambda *a: pytest.fail("no debe borrar copias locales"))
    with pytest.raises(SystemExit, match="no coincide"):
        backup.main(["create-remote"])


def test_C12_pg_dump_y_pg_restore_conservan_la_verificacion_tls(monkeypatch):
    monkeypatch.setenv("PGSSLMODE", "disable")
    env = backup._pg_env("postgresql://user:example@db.example/postgres?"
                         "sslmode=verify-full&sslrootcert=/tmp/certificado-publico.pem")
    assert env["PGSSLMODE"] == "verify-full"
    assert env["PGSSLROOTCERT"] == "/tmp/certificado-publico.pem"


@pytest.mark.parametrize("upload_fails", [False, True])
def test_C12_tarea_diaria_registra_el_resultado_remoto_y_no_omite_la_purga(
        monkeypatch, archive, s3, upload_fails):
    from ops import scheduled
    from directory.app import repo

    observed = {"purge": False, "summary": None}

    class FakeRepo:
        def __init__(self, *args, **kwargs):
            pass

        def purge(self):
            observed["purge"] = True
            return {"expired": 0}

        def close(self):
            pass

    monkeypatch.setattr(repo, "Repo", FakeRepo)
    monkeypatch.setattr(scheduled, "purge_logs", lambda *a: [])
    monkeypatch.setattr(scheduled.audit_log, "log", lambda *a, **kw: observed.update(summary=kw["extra"]["fields"]))
    monkeypatch.setenv("BACKUP_DATABASE_URL", "postgresql://no-se-usa")
    monkeypatch.setenv("DATABASE_URL", "postgresql://no-se-usa")
    monkeypatch.setenv("BACKUP_S3_BUCKET", BUCKET)
    monkeypatch.setenv("BACKUP_S3_PREFIX", "directory")
    monkeypatch.setenv("BACKUP_DIR", str(archive.parent))
    monkeypatch.setattr(backup, "create", lambda *a: archive)
    monkeypatch.setattr(backup, "load_key", lambda: bytes(range(32)))
    s3.wrong_hash = upload_fails
    result = scheduled.daily()
    assert observed["purge"]
    assert result == int(upload_fails)
    if upload_fails:
        assert observed["summary"]["copia_error"] == "BackupError"
        assert "copia_remota" not in observed["summary"]
    else:
        assert observed["summary"]["copia_remota"] == f"s3://{BUCKET}/directory/{archive.name}"
