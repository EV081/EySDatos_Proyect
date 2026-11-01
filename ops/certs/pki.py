"""CA propia del proyecto (F2): emite el certificado del directorio y publica la lista de revocación (CRL).

    python -m ops.certs.pki init                  # CA (5 años) + certificado del servidor (90 días) + CRL vacía
    python -m ops.certs.pki issue                 # renueva el certificado del servidor
    python -m ops.certs.pki revoke <serial hex>   # revoca un certificado y regenera la CRL

La llave privada de la CA se guarda cifrada con `CA_KEY_PASSWORD` en `ops/certs/private/` (no se versiona).
Lo único que se distribuye a los clientes es `ca.pem` y `crl.pem`. Ver ops/certs/README.md.
"""
import datetime as dt
import ipaddress
import json
import os
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

DEFAULT_DIR = Path(__file__).parent
CA_DAYS, SERVER_DAYS, CRL_DAYS = 5 * 365, 90, 30
DEFAULT_HOSTS = ("localhost", "127.0.0.1")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "E2EE Discord (proyecto UTEC)"),
                      x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        path.chmod(0o600)
    except OSError:
        pass


class Pki:
    def __init__(self, base: Path = DEFAULT_DIR, password: bytes | None = None):
        self.base = Path(base)
        self.password = password if password is not None else os.environ.get("CA_KEY_PASSWORD", "").encode()
        if len(self.password) < 12:
            raise ValueError("CA_KEY_PASSWORD debe tener al menos 12 caracteres")
        self.ca_cert, self.ca_key = self.base / "ca.pem", self.base / "private" / "ca.key"
        self.server_cert, self.server_key = self.base / "server.pem", self.base / "private" / "server.key"
        self.crl, self.revoked = self.base / "crl.pem", self.base / "revoked.json"

    # --- CA -------------------------------------------------------------------------

    def init_ca(self, days: int = CA_DAYS) -> x509.Certificate:
        if self.ca_key.exists():
            raise FileExistsError("la CA ya existe; no se sobrescribe")
        key = ec.generate_private_key(ec.SECP256R1())
        now = _now()
        cert = (x509.CertificateBuilder()
                .subject_name(_name("CA del directorio de llaves")).issuer_name(_name("CA del directorio de llaves"))
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=days))
                .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
                .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False,
                                             key_encipherment=False, data_encipherment=False, key_agreement=False,
                                             key_cert_sign=True, crl_sign=True, encipher_only=False,
                                             decipher_only=False), critical=True)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
                .sign(key, hashes.SHA256()))
        _write_private(self.ca_key, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                      serialization.BestAvailableEncryption(self.password)))
        self.ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        self.revoked.write_text("[]", encoding="utf-8")
        self.write_crl()
        return cert

    def _load_ca(self):
        cert = x509.load_pem_x509_certificate(self.ca_cert.read_bytes())
        key = serialization.load_pem_private_key(self.ca_key.read_bytes(), self.password)
        return cert, key

    # --- certificado del servidor ---------------------------------------------------

    def issue_server(self, hosts=DEFAULT_HOSTS, days: int = SERVER_DAYS, not_before: dt.datetime | None = None,
                     cert_path: Path | None = None, key_path: Path | None = None) -> x509.Certificate:
        ca_cert, ca_key = self._load_ca()
        key = ec.generate_private_key(ec.SECP256R1())
        start = not_before or _now() - dt.timedelta(minutes=5)
        alt = [x509.IPAddress(ipaddress.ip_address(h)) if h.replace(".", "").isdigit() or ":" in h
               else x509.DNSName(h) for h in hosts]
        cert = (x509.CertificateBuilder()
                .subject_name(_name(hosts[0])).issuer_name(ca_cert.subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(start).not_valid_after(start + dt.timedelta(days=days))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName(alt), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                             key_encipherment=False, data_encipherment=False, key_agreement=False,
                                             key_cert_sign=False, crl_sign=False, encipher_only=False,
                                             decipher_only=False), critical=True)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                               critical=False)
                .sign(ca_key, hashes.SHA256()))
        _write_private(key_path or self.server_key,
                       key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
        (cert_path or self.server_cert).write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return cert

    # --- revocación -----------------------------------------------------------------

    def revoke(self, serial: int) -> None:
        serials = set(json.loads(self.revoked.read_text(encoding="utf-8")))
        serials.add(serial)
        self.revoked.write_text(json.dumps(sorted(serials)), encoding="utf-8")
        self.write_crl()

    def write_crl(self, days: int = CRL_DAYS) -> None:
        """La CRL caduca a los 30 días: hay que regenerarla (`issue` o `revoke` lo hacen) antes de que venza."""
        ca_cert, ca_key = self._load_ca()
        now = _now()
        builder = (x509.CertificateRevocationListBuilder().issuer_name(ca_cert.subject)
                   .last_update(now - dt.timedelta(minutes=5)).next_update(now + dt.timedelta(days=days)))
        for serial in json.loads(self.revoked.read_text(encoding="utf-8")):
            builder = builder.add_revoked_certificate(
                x509.RevokedCertificateBuilder().serial_number(serial).revocation_date(now).build())
        self.crl.write_bytes(builder.sign(ca_key, hashes.SHA256()).public_bytes(serialization.Encoding.PEM))


def main(argv: list[str]) -> None:
    pki = Pki()
    command = argv[0] if argv else ""
    if command == "init":
        pki.init_ca()
        cert = pki.issue_server()
    elif command == "issue":
        cert = pki.issue_server()
        pki.write_crl()
    elif command == "revoke" and len(argv) == 2:
        pki.revoke(int(argv[1], 16))
        print(f"revocado {argv[1]}; distribuye {pki.crl}")
        return
    else:
        raise SystemExit(__doc__)
    print(f"certificado del servidor {cert.serial_number:x}, vence {cert.not_valid_after_utc:%Y-%m-%d}")


if __name__ == "__main__":
    main(sys.argv[1:])
