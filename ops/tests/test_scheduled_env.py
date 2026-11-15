"""Carga de URLs entre comillas sin ejecutar código ni reemplazar el entorno de la tarea."""
from ops.scheduled import load_env


def test_archivo_env_acepta_urls_entre_comillas(tmp_path, monkeypatch):
    monkeypatch.delenv("BACKUP_DATABASE_URL", raising=False)
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)
    path = tmp_path / "backup.env"
    path.write_text("# configuración ficticia\n"
                    "BACKUP_DATABASE_URL='postgresql://user:example@host/postgres?sslmode=verify-full'\n"
                    'BACKUP_S3_BUCKET="bucket-ficticio"\n')
    load_env(path)
    import os
    assert os.environ["BACKUP_DATABASE_URL"].startswith("postgresql://")
    assert os.environ["BACKUP_S3_BUCKET"] == "bucket-ficticio"


def test_archivo_env_no_sobrescribe_las_variables_del_proceso(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("BACKUP_S3_BUCKET", "bucket-de-la-tarea")
    path = tmp_path / "backup.env"
    path.write_text("BACKUP_S3_BUCKET=bucket-del-archivo\n")
    load_env(path)
    assert os.environ["BACKUP_S3_BUCKET"] == "bucket-de-la-tarea"
