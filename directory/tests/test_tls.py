"""F2 / C-07: el directorio solo se sirve con TLS 1.3 y la CA propia, y el cliente rechaza cualquier certificado
inválido (otra CA, vencido, otro nombre, revocado) sin ofrecer continuar. Servidores reales en hilos."""
import datetime as dt
import http.server
import json
import socket
import ssl
import threading
import time

import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI

from directory.client_lib import DirectoryClient, DirectoryError, tls_context
from directory.serve import build_config
from ops.certs.pki import Pki, server_hosts

ALICE = "111111111111111111"
PASSWORD = b"contrasena-de-la-ca-de-prueba"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    p = Pki(tmp_path_factory.mktemp("pki"), PASSWORD)
    p.init_ca()
    p.issue_server()
    return p


@pytest.fixture(scope="module")
def other_pki(tmp_path_factory):
    p = Pki(tmp_path_factory.mktemp("otra"), PASSWORD)
    p.init_ca()
    p.issue_server()
    return p


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"error": "no encontrado"}).encode()
        self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _serve(cert: str, key: str, max_version=ssl.TLSVersion.TLSv1_3) -> str:
    """Servidor HTTPS mínimo en un hilo; devuelve su URL."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.maximum_version = max_version
    ctx.load_cert_chain(cert, key)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"https://127.0.0.1:{server.server_address[1]}"


@pytest.fixture(scope="module")
def directory_url(pki):
    """El directorio arrancado con la misma configuración que `python -m directory.serve`."""
    app = FastAPI()

    @app.get("/v1/keys/{discord_id}")
    def lookup(discord_id: str):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "no encontrado"}, status_code=404)

    port = _free_port()
    server = uvicorn.Server(build_config(app, str(pki.server_cert), str(pki.server_key), "127.0.0.1", port))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"https://127.0.0.1:{port}"
    server.should_exit = True


def test_RS6_cliente_conecta_con_la_ca_propia(pki, directory_url):
    assert DirectoryClient(directory_url, ca_file=str(pki.ca_cert)).get_key(ALICE) is None


def test_RS6_servidor_solo_acepta_tls13(pki, directory_url):
    ctx = ssl.create_default_context(cafile=str(pki.ca_cert))
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    port = int(directory_url.rsplit(":", 1)[1])
    with pytest.raises(ssl.SSLError), socket.create_connection(("127.0.0.1", port)) as sock:
        ctx.wrap_socket(sock, server_hostname="127.0.0.1")


def test_RS6_negocia_tls13(pki, directory_url):
    port = int(directory_url.rsplit(":", 1)[1])
    with socket.create_connection(("127.0.0.1", port)) as sock, \
            tls_context(str(pki.ca_cert)).wrap_socket(sock, server_hostname="127.0.0.1") as tls:
        assert tls.version() == "TLSv1.3"


def test_C07_certificado_de_otra_ca_se_rechaza(pki, other_pki):
    url = _serve(str(other_pki.server_cert), str(other_pki.server_key))
    with pytest.raises(DirectoryError):
        DirectoryClient(url, ca_file=str(pki.ca_cert)).get_key(ALICE)


def test_C07_certificado_vencido_se_rechaza(pki, tmp_path):
    cert, key = tmp_path / "old.pem", tmp_path / "old.key"
    pki.issue_server(days=1, not_before=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=10),
                     cert_path=cert, key_path=key)
    url = _serve(str(cert), str(key))
    with pytest.raises(DirectoryError):
        DirectoryClient(url, ca_file=str(pki.ca_cert)).get_key(ALICE)


def test_C07_nombre_distinto_se_rechaza(pki, tmp_path):
    cert, key = tmp_path / "other.pem", tmp_path / "other.key"
    pki.issue_server(hosts=("directorio.example.com",), cert_path=cert, key_path=key)
    url = _serve(str(cert), str(key))
    with pytest.raises(DirectoryError):
        DirectoryClient(url, ca_file=str(pki.ca_cert)).get_key(ALICE)


def test_C07_cliente_no_acepta_tls12(pki):
    url = _serve(str(pki.server_cert), str(pki.server_key), max_version=ssl.TLSVersion.TLSv1_2)
    with pytest.raises(DirectoryError):
        DirectoryClient(url, ca_file=str(pki.ca_cert)).get_key(ALICE)


def test_C07_certificado_revocado_se_rechaza_con_la_crl(tmp_path):
    pki = Pki(tmp_path, PASSWORD)
    pki.init_ca()
    cert = pki.issue_server()
    url = _serve(str(pki.server_cert), str(pki.server_key))
    assert DirectoryClient(url, ca_file=str(pki.ca_cert), crl_file=str(pki.crl)).get_key(ALICE) is None
    pki.revoke(cert.serial_number)
    with pytest.raises(DirectoryError):
        DirectoryClient(url, ca_file=str(pki.ca_cert), crl_file=str(pki.crl)).get_key(ALICE)


def test_llave_de_la_ca_cifrada_y_no_se_sobrescribe(pki):
    with pytest.raises((TypeError, ValueError)):
        serialization.load_pem_private_key(pki.ca_key.read_bytes(), None)
    with pytest.raises(FileExistsError):
        pki.init_ca()


def test_certificado_del_servidor_es_de_90_dias_y_solo_servidor(pki):
    cert = x509.load_pem_x509_certificate(pki.server_cert.read_bytes())
    assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days == 90
    assert not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    assert list(eku) == [x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]


def test_RS6_el_certificado_puede_incluir_la_ip_publica_del_servidor(pki, monkeypatch):
    """Para desplegar el directorio: `DIRECTORY_EXTRA_HOSTS` agrega nombres o IP al certificado (SAN)."""
    monkeypatch.setenv("DIRECTORY_EXTRA_HOSTS", "203.0.113.10, directorio.example.org")
    hosts = server_hosts()
    assert hosts == ("localhost", "127.0.0.1", "203.0.113.10", "directorio.example.org")
    cert = pki.issue_server(hosts)
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert [str(ip) for ip in san.get_values_for_type(x509.IPAddress)] == ["127.0.0.1", "203.0.113.10"]
    assert san.get_values_for_type(x509.DNSName) == ["localhost", "directorio.example.org"]


def test_RS6_sin_hosts_extra_el_certificado_es_solo_local(monkeypatch):
    monkeypatch.delenv("DIRECTORY_EXTRA_HOSTS", raising=False)
    assert server_hosts() == ("localhost", "127.0.0.1")
